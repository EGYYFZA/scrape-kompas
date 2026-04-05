"""Core scraping logic for Kompas.com."""

import json
import logging
import time
from typing import List, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .models import Article
from .utils import clean_text

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Category → base URL mapping
# ---------------------------------------------------------------------------
CATEGORIES = {
    "terkini": "https://www.kompas.com/terkini/",
    "nasional": "https://nasional.kompas.com/",
    "internasional": "https://internasional.kompas.com/",
    "megapolitan": "https://megapolitan.kompas.com/",
    "regional": "https://regional.kompas.com/",
    "jawa-tengah": "https://regional.kompas.com/jawa-tengah",
    "money": "https://money.kompas.com/",
    "tekno": "https://tekno.kompas.com/",
    "bola": "https://bola.kompas.com/",
    "lifestyle": "https://lifestyle.kompas.com/",
    "otomotif": "https://otomotif.kompas.com/",
    "sains": "https://sains.kompas.com/",
    "travel": "https://travel.kompas.com/",
    "properti": "https://properti.kompas.com/",
    "edukasi": "https://edukasi.kompas.com/",
    "food": "https://food.kompas.com/",
    "health": "https://health.kompas.com/",
    "entertainment": "https://entertainment.kompas.com/",
    "homey": "https://homey.kompas.com/",
    "hype": "https://hype.kompas.com/",
}

# ---------------------------------------------------------------------------
# Default request headers that mimic a real browser
# ---------------------------------------------------------------------------
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


class KompasScraper:
    """Scraper for Kompas.com news articles.

    Example usage::

        scraper = KompasScraper()
        articles = scraper.scrape_category("tekno", max_articles=20)
        for article in articles:
            print(article)

    Args:
        delay: Seconds to wait between HTTP requests (default 1.0).
        timeout: HTTP request timeout in seconds (default 20).
        headers: Optional dict of additional / override HTTP headers.
    """

    def __init__(
        self,
        delay: float = 1.0,
        timeout: int = 20,
        headers: Optional[dict] = None,
    ) -> None:
        self.delay = delay
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        if headers:
            self.session.headers.update(headers)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def scrape_category(
        self,
        category: str,
        max_articles: int = 10,
        max_pages: int = 5,
        include_content: bool = True,
    ) -> List[Article]:
        """Scrape articles from a Kompas.com category.

        Args:
            category: One of the keys in ``CATEGORIES`` or a full URL string.
            max_articles: Maximum number of articles to return.
            max_pages: Maximum number of listing pages to crawl.
            include_content: Whether to fetch full article content
                             (requires an extra HTTP request per article).

        Returns:
            List of :class:`Article` objects.
        """
        base_url = CATEGORIES.get(category, category)
        if not base_url.startswith("http"):
            raise ValueError(
                f"Unknown category '{category}'. "
                f"Valid categories: {', '.join(CATEGORIES.keys())}"
            )

        logger.info("Scraping category '%s' (max %d articles)", category, max_articles)
        article_urls = self._collect_article_urls(base_url, max_articles, max_pages)

        articles: List[Article] = []
        for url in article_urls:
            try:
                article = self.scrape_article(url, include_content=include_content)
                if article:
                    articles.append(article)
                    logger.info("Scraped: %s", article.title[:80])
            except Exception as exc:
                logger.warning("Failed to scrape %s: %s", url, exc)
            time.sleep(self.delay)

        logger.info("Scraped %d articles from '%s'", len(articles), category)
        return articles

    def scrape_article(
        self, url: str, include_content: bool = True
    ) -> Optional[Article]:
        """Scrape a single article from its URL.

        Args:
            url: Full URL of the Kompas.com article.
            include_content: If False, skip fetching the full body text.

        Returns:
            An :class:`Article` instance or ``None`` on failure.
        """
        soup = self._get_soup(url)
        if soup is None:
            return None

        # Try JSON-LD structured data first (most reliable)
        article = self._parse_jsonld(soup, url)

        # Fall back to HTML parsing
        if article is None:
            article = self._parse_article_html(soup, url)

        if article and include_content and not article.content:
            article.content = self._parse_content(soup)

        return article

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get(self, url: str) -> Optional[requests.Response]:
        """Perform an HTTP GET request and return the response or None."""
        try:
            resp = self.session.get(url, timeout=self.timeout)
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:
            logger.warning("HTTP error for %s: %s", url, exc)
            return None

    def _get_soup(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch a URL and return a BeautifulSoup object or None."""
        resp = self._get(url)
        if resp is None:
            return None
        return BeautifulSoup(resp.text, "lxml")

    # ------------------------------------------------------------------
    # Article URL collection (listing pages)
    # ------------------------------------------------------------------

    def _collect_article_urls(
        self, base_url: str, max_articles: int, max_pages: int
    ) -> List[str]:
        """Crawl listing pages and collect unique article URLs."""
        urls: List[str] = []
        seen: set = set()

        for page in range(1, max_pages + 1):
            if len(urls) >= max_articles:
                break

            page_url = base_url if page == 1 else f"{base_url}?page={page}"
            logger.debug("Fetching listing page: %s", page_url)

            soup = self._get_soup(page_url)
            if soup is None:
                break

            new_urls = self._extract_article_urls(soup, base_url)
            added = 0
            for u in new_urls:
                if u not in seen:
                    seen.add(u)
                    urls.append(u)
                    added += 1
                    if len(urls) >= max_articles:
                        break

            logger.debug("Page %d: found %d new URLs (total %d)", page, added, len(urls))
            if not new_urls:
                logger.debug("No articles found on page %d, stopping.", page)
                break

            time.sleep(self.delay)

        return urls[:max_articles]

    def _extract_article_urls(
        self, soup: BeautifulSoup, base_url: str
    ) -> List[str]:
        """Extract article URLs from a listing page soup."""
        urls: List[str] = []
        domain = urlparse(base_url).netloc  # e.g. tekno.kompas.com

        # Strategy 1: articleItem links
        for item in soup.select(".articleItem, .articlePost, .latest--indeks"):
            a = item.find("a", href=True)
            if a:
                href = a["href"]
                full_url = href if href.startswith("http") else urljoin(base_url, href)
                if self._is_article_url(full_url):
                    urls.append(full_url)

        # Strategy 2: generic links within article list containers
        if not urls:
            for container in soup.select(
                ".articleList, .latestArticle, [data-type='article']"
            ):
                for a in container.find_all("a", href=True):
                    href = a["href"]
                    full_url = href if href.startswith("http") else urljoin(base_url, href)
                    if self._is_article_url(full_url):
                        urls.append(full_url)

        # Strategy 3: any /read/ link on the page
        if not urls:
            for a in soup.find_all("a", href=True):
                href = a["href"]
                full_url = href if href.startswith("http") else urljoin(base_url, href)
                if self._is_article_url(full_url):
                    urls.append(full_url)

        # Deduplicate while preserving order
        seen: set = set()
        unique: List[str] = []
        for u in urls:
            if u not in seen:
                seen.add(u)
                unique.append(u)
        return unique

    @staticmethod
    def _is_article_url(url: str) -> bool:
        """Return True if the URL looks like a Kompas.com article."""
        parsed = urlparse(url)
        netloc = parsed.netloc
        is_kompas = netloc == "kompas.com" or netloc.endswith(".kompas.com")
        return is_kompas and "/read/" in parsed.path

    # ------------------------------------------------------------------
    # Article parsing
    # ------------------------------------------------------------------

    def _parse_jsonld(self, soup: BeautifulSoup, url: str) -> Optional[Article]:
        """Attempt to extract article metadata from JSON-LD structured data."""
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
            except (json.JSONDecodeError, TypeError):
                continue

            # Handle both a single object and a list
            items = data if isinstance(data, list) else [data]
            for item in items:
                if item.get("@type") not in ("NewsArticle", "Article", "WebPage"):
                    continue

                author = None
                author_raw = item.get("author")
                if isinstance(author_raw, dict):
                    author = author_raw.get("name")
                elif isinstance(author_raw, list) and author_raw:
                    author = author_raw[0].get("name")
                elif isinstance(author_raw, str):
                    author = author_raw

                # Category / section
                category = item.get("articleSection") or item.get("section")
                if isinstance(category, list):
                    category = category[0] if category else None

                # Tags / keywords
                keywords = item.get("keywords", "")
                tags: List[str] = []
                if isinstance(keywords, str) and keywords:
                    tags = [k.strip() for k in keywords.split(",") if k.strip()]
                elif isinstance(keywords, list):
                    tags = [k.strip() for k in keywords if k.strip()]

                # Image
                image_url = None
                img = item.get("image")
                if isinstance(img, dict):
                    image_url = img.get("url")
                elif isinstance(img, str):
                    image_url = img

                return Article(
                    url=item.get("url") or url,
                    title=clean_text(item.get("headline") or item.get("name") or ""),
                    author=clean_text(author) if author else None,
                    published_at=item.get("datePublished"),
                    category=clean_text(category) if category else None,
                    content=clean_text(item.get("articleBody") or "") or None,
                    image_url=image_url,
                    tags=tags,
                )
        return None

    def _parse_article_html(self, soup: BeautifulSoup, url: str) -> Article:
        """Parse article metadata directly from HTML when JSON-LD is absent."""
        # Title
        title_tag = (
            soup.find("h1", class_="read__title")
            or soup.find("h1", itemprop="headline")
            or soup.find("h1")
        )
        title = clean_text(title_tag.get_text()) if title_tag else ""

        # Author
        author_tag = (
            soup.find(class_="creditName")
            or soup.find(itemprop="author")
            or soup.find(class_="read__credit--name")
        )
        author = clean_text(author_tag.get_text()) if author_tag else None

        # Editor
        editor_tag = soup.find(class_="read__credit--editor")
        editor = clean_text(editor_tag.get_text()) if editor_tag else None

        # Published date
        date_tag = (
            soup.find(class_="read__time")
            or soup.find(itemprop="datePublished")
            or soup.find("meta", {"name": "content_publishdate"})
        )
        if date_tag:
            published_at = (
                date_tag.get("content")
                or date_tag.get("datetime")
                or clean_text(date_tag.get_text())
            )
        else:
            published_at = None

        # Category (breadcrumb)
        category = None
        breadcrumb = soup.find(class_="read__breadcrumb")
        if breadcrumb:
            crumb_links = breadcrumb.find_all("a")
            if crumb_links:
                category = clean_text(crumb_links[-1].get_text())

        # Image
        image_url = None
        img_tag = (
            soup.find("img", itemprop="image")
            or soup.find(class_="photo__image")
        )
        if img_tag:
            image_url = img_tag.get("src") or img_tag.get("data-src")

        # Tags
        tags: List[str] = []
        for tag_el in soup.select(".tag__article a, .tagList__link, .tag a"):
            t = clean_text(tag_el.get_text())
            if t:
                tags.append(t)

        return Article(
            url=url,
            title=title,
            author=author,
            published_at=published_at,
            category=category,
            image_url=image_url,
            tags=tags,
            editor=editor,
        )

    def _parse_content(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract and clean the article body text."""
        content_div = (
            soup.find(class_="read__content")
            or soup.find(itemprop="articleBody")
            or soup.find(class_="article__content")
        )
        if content_div is None:
            return None

        # Remove unwanted child elements (ads, related article blocks, etc.)
        for unwanted in content_div.select(
            ".readsection, .inner-article-recom, .inner-banner, "
            ".recom__box, script, style, .ads"
        ):
            unwanted.decompose()

        paragraphs = [
            clean_text(p.get_text())
            for p in content_div.find_all("p")
            if clean_text(p.get_text())
        ]
        return "\n\n".join(paragraphs) if paragraphs else clean_text(content_div.get_text())
