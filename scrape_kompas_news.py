#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scraper Kompas kanal NASIONAL (https://nasional.kompas.com/)
Strategi:
1) Coba sitemap seperti sebelumnya (kadang cuma ~100 URL terakhir).
2) Fallback besar: halaman INDEKS date-based:
   https://indeks.kompas.com/?site=nasional&date=YYYY-MM-DD&page=N
   -> ekstrak semua link artikel ke nasional.kompas.com/read/YYYY/MM/DD/slug
Etika: batasi concurrency, retry, dan resume.
Output CSV: title,date,author,category,url,image_url,tags,body,word_count,label(0)
"""

import asyncio, re, sys, csv, os, random, argparse
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, urlencode
import httpx
from selectolax.parser import HTMLParser
from lxml import etree
import pandas as pd
from dateutil import parser as dtparser
from tenacity import retry, stop_after_attempt, wait_exponential
import urllib.robotparser as robotparser
from tqdm import tqdm

BASES = [
    "https://www.kompas.com",
    "https://nasional.kompas.com",
    "https://kompas.com",
    "https://indeks.kompas.com",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0.0.0 Safari/537.36 (+polite academic crawler)"
}

CANDIDATE_SITEMAPS = [
    "https://www.kompas.com/sitemap.xml",
    "https://www.kompas.com/sitemap-index.xml",
    "https://nasional.kompas.com/sitemap.xml",
    "https://nasional.kompas.com/sitemap-index.xml",
    "https://www.kompas.com/sitemaps.xml",
    "https://www.kompas.com/sitemap-news.xml",
]

ARTICLE_PAT = re.compile(
    r"https?://(?:nasional\.|www\.)?kompas\.com/(?:read/)?\d{4}/\d{2}/\d{2}/[a-z0-9\-]+",
    re.I
)

def is_nasional(url: str) -> bool:
    u = url.lower()
    return ("nasional.kompas.com" in u) or ("/nasional-" in u)  # kompas sering pakai prefix kategori di slug

def normalize_url(u: str) -> str:
    return re.sub(r"[#?].*$", "", u.strip())

def clean_text(t: str) -> str:
    t = re.sub(r"\s+", " ", t, flags=re.UNICODE).strip()
    t = re.sub(r"(Baca juga:.*)$", "", t, flags=re.IGNORECASE)
    return t.strip()

def extract_meta(tree: HTMLParser, name: str, attr: str = "property") -> str|None:
    node = tree.css_first(f'meta[{attr}="{name}"]')
    return node.attributes.get("content") if node else None

def parse_article(html: str, url: str) -> dict|None:
    tree = HTMLParser(html)

    title = extract_meta(tree, "og:title") or (tree.css_first("h1") and tree.css_first("h1").text())
    if not title:
        return None
    title = clean_text(title)

    pub = (extract_meta(tree, "article:published_time") or
           extract_meta(tree, "og:updated_time") or
           extract_meta(tree, "publication_date", "name") or
           (tree.css_first("time") and (tree.css_first("time").attributes.get("datetime") or tree.css_first("time").text())))
    pub_dt = None
    if pub:
        try:
            pub_dt = dtparser.parse(pub)
        except Exception:
            pub_dt = None

    author = (extract_meta(tree, "author", "name") or
              extract_meta(tree, "og:author") or
              (tree.css_first(".read__author, .author, a[rel=author]") and tree.css_first(".read__author, .author, a[rel=author]").text()))
    if author:
        author = clean_text(author)

    section = (extract_meta(tree, "article:section") or "nasional")

    image_url = extract_meta(tree, "og:image")

    tags = []
    for meta in tree.css("meta[property='article:tag']"):
        c = meta.attributes.get("content")
        if c:
            tags.append(c.strip())
    for a in tree.css(".tag__wrapper a, .tags a, .read__tags a"):
        t = a.text().strip()
        if t and t not in tags:
            tags.append(t)

    body_nodes = (tree.css("div.read__content p") or
                  tree.css("div#read__content p") or
                  tree.css("article p") or
                  tree.css("div[itemprop='articleBody'] p") or
                  [])
    paras = []
    for p in body_nodes:
        txt = p.text(separator=" ", strip=True)
        if not txt:
            continue
        if any(x in txt.lower() for x in ["baca juga", "kompas.com", "penulis:", "editor:", "artikel ini telah tayang"]):
            continue
        paras.append(txt)
    body = clean_text(" ".join(paras))
    if not body or len(body.split()) < 80:
        return None

    return {
        "title": title,
        "date": pub_dt.isoformat() if pub_dt else "",
        "author": author or "",
        "category": section or "nasional",
        "url": url,
        "image_url": image_url or "",
        "tags": "|".join(tags) if tags else "",
        "body": body,
        "word_count": len(body.split()),
        "label": 0
    }

async def fetch_text(client: httpx.AsyncClient, url: str) -> str:
    r = await client.get(url, timeout=30.0, headers=HEADERS, follow_redirects=True)
    r.raise_for_status()
    return r.text

def parse_robots_sitemaps(robots_txt: str) -> list[str]:
    sitemaps = []
    for line in robots_txt.splitlines():
        if line.lower().startswith("sitemap:"):
            sm = line.split(":", 1)[1].strip()
            if sm:
                sitemaps.append(sm)
    return sitemaps

async def discover_sitemaps() -> list[str]:
    out = []
    async with httpx.AsyncClient(http2=True, headers=HEADERS) as client:
        for base in BASES:
            robots_url = base.rstrip("/") + "/robots.txt"
            try:
                txt = await fetch_text(client, robots_url)
                out.extend(parse_robots_sitemaps(txt))
            except Exception:
                pass
    out.extend(CANDIDATE_SITEMAPS)
    # unik
    uniq, seen = [], set()
    for s in out:
        s = s.strip()
        if s and s not in seen:
            uniq.append(s); seen.add(s)
    return uniq

def parse_sitemap_xml(xml_text: str) -> list[str]:
    try:
        root = etree.fromstring(xml_text.encode("utf-8"))
    except Exception:
        root = etree.XML(xml_text.encode("utf-8"), parser=etree.XMLParser(recover=True))
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls = []
    for loc in root.findall(".//sm:sitemap/sm:loc", ns):
        if loc.text:
            urls.append(loc.text.strip())
    for loc in root.findall(".//sm:url/sm:loc", ns):
        if loc.text:
            urls.append(loc.text.strip())
    for loc in root.findall(".//loc"):
        if loc.text:
            urls.append(loc.text.strip())
    return urls

async def harvest_from_sitemaps(max_urls_hint: int = 5000) -> list[str]:
    sitemaps = await discover_sitemaps()
    urls = []
    async with httpx.AsyncClient(http2=True, headers=HEADERS) as client:
        for sm in sitemaps:
            try:
                r = await client.get(sm, timeout=30.0)
                if r.status_code != 200 or "xml" not in r.headers.get("content-type",""):
                    continue
                locs = parse_sitemap_xml(r.text)
                children = [u for u in locs if u.endswith(".xml")]
                if children:
                    for ch in children:
                        try:
                            rc = await client.get(ch, timeout=30.0)
                            if rc.status_code == 200 and "xml" in rc.headers.get("content-type",""):
                                locs2 = parse_sitemap_xml(rc.text)
                                for u in locs2:
                                    u = normalize_url(u)
                                    if ARTICLE_PAT.search(u) and is_nasional(u):
                                        urls.append(u)
                        except Exception:
                            continue
                else:
                    for u in locs:
                        u = normalize_url(u)
                        if ARTICLE_PAT.search(u) and is_nasional(u):
                            urls.append(u)
            except Exception:
                continue
            if len(urls) >= max_urls_hint:
                break
    urls = list(dict.fromkeys(urls))
    random.shuffle(urls)
    return urls

async def harvest_from_indeks(days: int, start_date: datetime|None = None, per_date_pages: int = 50, budget: int = 20000) -> list[str]:
    """
    Enumerasi halaman indeks harian:
    https://indeks.kompas.com/?site=nasional&date=YYYY-MM-DD&page=N
    Ambil semua link artikel nasional.*.com/read/YYYY/MM/DD/slug
    """
    if start_date is None:
        start_date = datetime.now()
    all_urls, seen = [], set()
    async with httpx.AsyncClient(http2=True, headers=HEADERS, timeout=30.0) as client:
        for d in range(days):
            if len(all_urls) >= budget:
                break
            date_str = (start_date - timedelta(days=d)).strftime("%Y-%m-%d")
            got_today = 0
            for page in range(1, per_date_pages+1):
                if len(all_urls) >= budget:
                    break
                q = {"site": "nasional", "date": date_str, "page": page}
                url = f"https://indeks.kompas.com/?{urlencode(q)}"
                try:
                    html = await fetch_text(client, url)
                except Exception:
                    # kalau 404/403, lanjut tanggal berikutnya
                    break
                tree = HTMLParser(html)
                # ambil semua href lalu filter pola artikel nasional
                links = set()
                for a in tree.css("a"):
                    href = a.attributes.get("href") if a.attributes else None
                    if not href:
                        continue
                    href = normalize_url(href)
                    if ARTICLE_PAT.search(href) and is_nasional(href):
                        links.add(href)
                # stop kalau halaman ini kosong
                if not links:
                    break
                new = [u for u in links if u not in seen]
                if not new:
                    # kalau sudah tidak ada yang baru, mungkin paginasi habis
                    break
                for u in new:
                    seen.add(u)
                    all_urls.append(u)
                got_today += len(new)
            # print(f"[INDEKS] {date_str}: +{got_today}")
    random.shuffle(all_urls)
    return all_urls

def load_seen(path: str) -> set[str]:
    if not os.path.exists(path): return set()
    with open(path, "r", encoding="utf-8") as f:
        return set([normalize_url(x.strip()) for x in f if x.strip()])

def append_seen(path: str, urls: list[str]):
    with open(path, "a", encoding="utf-8") as f:
        for u in urls:
            f.write(normalize_url(u) + "\n")

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=20))
async def fetch_one(client: httpx.AsyncClient, url: str) -> tuple[str, str|None]:
    r = await client.get(url, timeout=30.0, headers=HEADERS, follow_redirects=True)
    if r.status_code in (403, 429):
        raise httpx.HTTPStatusError(f"status {r.status_code}", request=r.request, response=r)
    r.raise_for_status()
    return url, r.text

async def scrape(urls: list[str], out_csv: str, max_rows: int, concurrency: int = 3,
                 seen_file: str = "urls_seen_news.txt"):
    import csv, os, random, asyncio
    is_new = not os.path.exists(out_csv)
    f = open(out_csv, "a", encoding="utf-8", newline="")
    writer = csv.DictWriter(f, fieldnames=[
        "title","date","author","category","url","image_url","tags","body","word_count","label"
    ])
    if is_new:
        writer.writeheader()

    seen = load_seen(seen_file)
    done = 0

    # hanya proses URL yang belum pernah diambil
    todo = [u for u in urls if normalize_url(u) not in seen]
    todo = list(dict.fromkeys(todo))

    target = min(max_rows, len(todo))
    print(f"[INFO] Mulai scrape: {len(todo)} URL (skip {len(seen)} sudah diambil). Target rows: {max_rows}")

    # progress bar menampilkan JUMLAH ARTIKEL TERSIMPAN (done)
    pbar = tqdm(total=target, desc="Scraping articles", unit="art", ncols=100)

    sem = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient(http2=True, headers=HEADERS, timeout=30.0) as client:
        async def worker(u: str):
            nonlocal done
            async with sem:
                try:
                    url, html = await fetch_one(client, u)
                    art = parse_article(html, url)
                    # jeda kecil agar sopan
                    await asyncio.sleep(random.uniform(0.3, 0.8))
                    # hanya update progress kalau artikelnya valid & ditulis ke CSV
                    if art:
                        writer.writerow(art)
                        done += 1
                        pbar.update(1)
                        if done % 50 == 0:
                            f.flush()
                        append_seen(seen_file, [u])
                except Exception:
                    # tetap tandai sudah dicoba agar tidak diulang
                    append_seen(seen_file, [u])

        tasks = []
        for u in todo:
            if done >= max_rows:
                break
            tasks.append(asyncio.create_task(worker(u)))

        CHUNK = 500
        try:
            for i in range(0, len(tasks), CHUNK):
                chunk = tasks[i:i+CHUNK]
                await asyncio.gather(*chunk)
                if done >= max_rows:
                    break
        finally:
            pbar.close()

    f.flush(); f.close()
    print(f"[DONE] Tersimpan {done} artikel ke {out_csv}")

async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=10000, help="Target jumlah artikel")
    ap.add_argument("--out", type=str, default="kompas_nasional.csv", help="CSV output")
    ap.add_argument("--concurrency", type=int, default=3, help="Jumlah koneksi paralel (2-3 disarankan)")
    ap.add_argument("--days", type=int, default=1200, help="Mundur berapa hari (fallback INDEKS)")
    ap.add_argument("--start", type=str, default=None, help="Tanggal mulai (YYYY-MM-DD). Default=hari ini")
    args = ap.parse_args()

    start_dt = datetime.strptime(args.start, "%Y-%m-%d") if args.start else datetime.now()

    print("[STEP] Mengumpulkan URL dari sitemap (jika ada banyak)…")
    urls_sitemap = await harvest_from_sitemaps(max_urls_hint=args.max*2)
    print(f"[INFO] Dari sitemap: {len(urls_sitemap)} URL")

    need_more = max(0, args.max*2 - len(urls_sitemap))
    print("[STEP] Mengumpulkan URL dari halaman INDEKS (date-based)…")
    urls_indeks = await harvest_from_indeks(days=args.days, start_date=start_dt, budget=max(args.max*2, 20000))
    print(f"[INFO] Dari indeks: {len(urls_indeks)} URL")

    urls = list(dict.fromkeys(urls_sitemap + urls_indeks))
    random.shuffle(urls)
    if not urls:
        print("[ERROR] Tidak menemukan URL. Coba perbesar --days atau cek koneksi.")
        return

    await scrape(urls, out_csv=args.out, max_rows=args.max, concurrency=args.concurrency)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[INTERRUPTED] Dihentikan oleh pengguna.")