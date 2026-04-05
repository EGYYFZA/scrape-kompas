"""Tests for KompasScraper using mocked HTTP responses."""

import json
from unittest.mock import MagicMock, patch

import pytest
from bs4 import BeautifulSoup

from kompas.scraper import KompasScraper, CATEGORIES, DEFAULT_HEADERS


# ---------------------------------------------------------------------------
# HTML fixtures
# ---------------------------------------------------------------------------

LISTING_HTML = """
<html>
<body>
  <div class="articleList">
    <div class="articleItem">
      <div class="articlePost">
        <a href="https://tekno.kompas.com/read/2024/01/01/001/berita-satu">
          <h3 class="articlePost--title">Berita Satu</h3>
        </a>
      </div>
    </div>
    <div class="articleItem">
      <div class="articlePost">
        <a href="https://tekno.kompas.com/read/2024/01/02/002/berita-dua">
          <h3 class="articlePost--title">Berita Dua</h3>
        </a>
      </div>
    </div>
  </div>
</body>
</html>
"""

ARTICLE_HTML = """
<html>
<head>
  <script type="application/ld+json">
  {
    "@type": "NewsArticle",
    "headline": "Judul Artikel Kompas",
    "url": "https://tekno.kompas.com/read/2024/01/01/001/judul",
    "datePublished": "2024-01-01T08:00:00+07:00",
    "author": {"@type": "Person", "name": "Nama Penulis"},
    "articleSection": "Tekno",
    "keywords": "teknologi, ai, kompas",
    "image": {"@type": "ImageObject", "url": "https://cdn.kompas.com/thumb.jpg"},
    "articleBody": "Ini adalah isi artikel teknologi."
  }
  </script>
</head>
<body>
  <h1 class="read__title">Judul Artikel Kompas</h1>
  <div class="read__content">
    <p>Paragraf pertama artikel.</p>
    <p>Paragraf kedua artikel.</p>
  </div>
</body>
</html>
"""

ARTICLE_HTML_NO_JSONLD = """
<html>
<body>
  <h1 class="read__title">Judul Tanpa JSON-LD</h1>
  <a class="creditName" href="#">Penulis B</a>
  <div class="read__time">Minggu, 1 Januari 2024 08.00 WIB</div>
  <div class="read__breadcrumb">
    <a href="/">Kompas.com</a>
    <a href="/tekno/">Tekno</a>
  </div>
  <img class="photo__image" src="https://cdn.kompas.com/img2.jpg" />
  <div class="tag__article">
    <a href="#">python</a>
    <a href="#">scraping</a>
  </div>
  <div class="read__content">
    <p>Isi artikel tanpa JSON-LD.</p>
  </div>
</body>
</html>
"""


def _make_response(html: str, status_code: int = 200) -> MagicMock:
    """Build a mock requests.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = html
    resp.raise_for_status = MagicMock()
    return resp


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCategories:
    def test_known_categories(self):
        assert "terkini" in CATEGORIES
        assert "nasional" in CATEGORIES
        assert "tekno" in CATEGORIES
        assert all(v.startswith("https://") for v in CATEGORIES.values())

    def test_all_categories_end_with_kompas_com(self):
        for name, url in CATEGORIES.items():
            assert "kompas.com" in url, f"{name} URL does not contain kompas.com"


class TestIsArticleUrl:
    def test_valid_article_url(self):
        assert KompasScraper._is_article_url(
            "https://tekno.kompas.com/read/2024/01/01/001/judul"
        )

    def test_non_article_url(self):
        assert not KompasScraper._is_article_url("https://tekno.kompas.com/")
        assert not KompasScraper._is_article_url("https://example.com/read/123")

    def test_spoofed_domain_rejected(self):
        # Domain that merely *contains* "kompas.com" but is not kompas.com
        assert not KompasScraper._is_article_url(
            "https://evilkompas.com/read/2024/01/01/001/attack"
        )
        assert not KompasScraper._is_article_url(
            "https://fake-kompas.com/read/2024/01/01/001/attack"
        )

    def test_kompas_read_url(self):
        assert KompasScraper._is_article_url(
            "https://nasional.kompas.com/read/2024/06/15/12345678/berita"
        )


class TestExtractArticleUrls:
    def test_extracts_from_listing(self):
        scraper = KompasScraper()
        soup = BeautifulSoup(LISTING_HTML, "lxml")
        urls = scraper._extract_article_urls(soup, "https://tekno.kompas.com/")
        assert len(urls) == 2
        assert all("/read/" in u for u in urls)

    def test_deduplication(self):
        """Duplicate links in HTML should only appear once."""
        html = """
        <div class="articleItem">
          <a href="https://tekno.kompas.com/read/2024/01/01/001/dup">Dup</a>
          <a href="https://tekno.kompas.com/read/2024/01/01/001/dup">Dup</a>
        </div>
        """
        scraper = KompasScraper()
        soup = BeautifulSoup(html, "lxml")
        urls = scraper._extract_article_urls(soup, "https://tekno.kompas.com/")
        assert len(urls) == 1


class TestParseJsonld:
    def test_parses_jsonld_article(self):
        scraper = KompasScraper()
        soup = BeautifulSoup(ARTICLE_HTML, "lxml")
        article = scraper._parse_jsonld(
            soup, "https://tekno.kompas.com/read/2024/01/01/001/judul"
        )
        assert article is not None
        assert article.title == "Judul Artikel Kompas"
        assert article.author == "Nama Penulis"
        assert article.published_at == "2024-01-01T08:00:00+07:00"
        assert article.category == "Tekno"
        assert article.image_url == "https://cdn.kompas.com/thumb.jpg"
        assert "teknologi" in article.tags
        assert "ai" in article.tags

    def test_returns_none_for_no_jsonld(self):
        scraper = KompasScraper()
        soup = BeautifulSoup("<html><body></body></html>", "lxml")
        assert scraper._parse_jsonld(soup, "https://kompas.com/read/1") is None


class TestParseArticleHtml:
    def test_parses_html_fallback(self):
        scraper = KompasScraper()
        soup = BeautifulSoup(ARTICLE_HTML_NO_JSONLD, "lxml")
        article = scraper._parse_article_html(
            soup, "https://tekno.kompas.com/read/2024/01/01/001/judul"
        )
        assert article.title == "Judul Tanpa JSON-LD"
        assert article.author == "Penulis B"
        assert "2024" in article.published_at
        assert article.category == "Tekno"
        assert article.image_url == "https://cdn.kompas.com/img2.jpg"
        assert "python" in article.tags
        assert "scraping" in article.tags


class TestParseContent:
    def test_extracts_paragraphs(self):
        scraper = KompasScraper()
        soup = BeautifulSoup(ARTICLE_HTML, "lxml")
        content = scraper._parse_content(soup)
        assert content is not None
        assert "Paragraf pertama" in content
        assert "Paragraf kedua" in content

    def test_returns_none_for_missing_content(self):
        scraper = KompasScraper()
        soup = BeautifulSoup("<html><body></body></html>", "lxml")
        assert scraper._parse_content(soup) is None


class TestScrapeArticle:
    def test_scrape_article_with_jsonld(self):
        scraper = KompasScraper()
        mock_resp = _make_response(ARTICLE_HTML)
        with patch.object(scraper.session, "get", return_value=mock_resp):
            article = scraper.scrape_article(
                "https://tekno.kompas.com/read/2024/01/01/001/judul"
            )
        assert article is not None
        assert article.title == "Judul Artikel Kompas"
        assert article.author == "Nama Penulis"

    def test_scrape_article_no_jsonld(self):
        scraper = KompasScraper()
        mock_resp = _make_response(ARTICLE_HTML_NO_JSONLD)
        with patch.object(scraper.session, "get", return_value=mock_resp):
            article = scraper.scrape_article(
                "https://tekno.kompas.com/read/2024/01/01/001/judul"
            )
        assert article is not None
        assert article.title == "Judul Tanpa JSON-LD"

    def test_scrape_article_http_error_returns_none(self):
        scraper = KompasScraper()
        import requests as _requests
        with patch.object(
            scraper.session,
            "get",
            side_effect=_requests.exceptions.ConnectionError("connection error"),
        ):
            article = scraper.scrape_article("https://tekno.kompas.com/read/x")
        assert article is None


class TestScrapeCategory:
    def test_unknown_category_raises(self):
        scraper = KompasScraper()
        with pytest.raises(ValueError, match="Unknown category"):
            scraper.scrape_category("nonexistent_category")

    def test_scrape_category_returns_articles(self):
        scraper = KompasScraper(delay=0)
        listing_resp = _make_response(LISTING_HTML)
        article_resp = _make_response(ARTICLE_HTML)

        call_count = [0]

        def mock_get(url, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return listing_resp
            return article_resp

        with patch.object(scraper.session, "get", side_effect=mock_get):
            articles = scraper.scrape_category("tekno", max_articles=2, max_pages=1)

        assert len(articles) == 2
        assert all(a.title == "Judul Artikel Kompas" for a in articles)
