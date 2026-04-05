# scrape-kompas

**Data Mining News Indonesia** — a Python web scraper for [Kompas.com](https://www.kompas.com), one of Indonesia's largest online news portals.

---

## Features

- Scrape articles from **20 categories** (national, technology, sports, economy, travel, …)
- Extracts: title, author, editor, published date, category, full content, image URL, and tags
- Prefers structured **JSON-LD** data; falls back to HTML parsing
- Configurable request **delay** and article / page limits
- Export results to **CSV** and/or **JSON**
- Clean CLI interface

---

## Installation

```bash
pip install -r requirements.txt
```

Requirements: Python 3.8+ · `requests` · `beautifulsoup4` · `lxml`

---

## Quick Start

### Command-line

```bash
# Scrape 10 latest articles (default)
python main.py

# Scrape 20 technology articles, save to CSV and JSON
python main.py tekno -n 20 --output-csv tekno.csv --output-json tekno.json

# Scrape national news, skip full content (faster listing-only mode)
python main.py nasional -n 50 --no-content

# Use verbose logging
python main.py money -n 5 -v
```

### Python API

```python
from kompas import KompasScraper
from kompas.utils import save_csv, save_json

scraper = KompasScraper(delay=1.0)

# Scrape up to 15 articles from the Technology section
articles = scraper.scrape_category("tekno", max_articles=15)

for article in articles:
    print(article)

# Export
save_csv(articles, "articles.csv")
save_json(articles, "articles.json")

# Scrape a single article by URL
article = scraper.scrape_article(
    "https://tekno.kompas.com/read/2024/01/01/001/judul-berita"
)
print(article.title, article.author, article.published_at)
```

---

## Available Categories

| Key | URL |
|---|---|
| `terkini` | https://www.kompas.com/terkini/ |
| `nasional` | https://nasional.kompas.com/ |
| `internasional` | https://internasional.kompas.com/ |
| `megapolitan` | https://megapolitan.kompas.com/ |
| `regional` | https://regional.kompas.com/ |
| `money` | https://money.kompas.com/ |
| `tekno` | https://tekno.kompas.com/ |
| `bola` | https://bola.kompas.com/ |
| `lifestyle` | https://lifestyle.kompas.com/ |
| `otomotif` | https://otomotif.kompas.com/ |
| `sains` | https://sains.kompas.com/ |
| `travel` | https://travel.kompas.com/ |
| `properti` | https://properti.kompas.com/ |
| `edukasi` | https://edukasi.kompas.com/ |
| `food` | https://food.kompas.com/ |
| `health` | https://health.kompas.com/ |
| `entertainment` | https://entertainment.kompas.com/ |
| `homey` | https://homey.kompas.com/ |
| `hype` | https://hype.kompas.com/ |
| `jawa-tengah` | https://regional.kompas.com/jawa-tengah |

You can also pass a full URL directly:

```bash
python main.py https://tekno.kompas.com/ -n 10
```

---

## Article Object Fields

| Field | Description |
|---|---|
| `url` | Full article URL |
| `title` | Article headline |
| `author` | Author name |
| `editor` | Editor name |
| `published_at` | Publication datetime (ISO 8601 or as printed) |
| `category` | News category / section |
| `content` | Full article body text |
| `image_url` | URL of the main article image |
| `tags` | List of article tags / keywords |

---

## Project Structure

```
scrape-kompas/
├── kompas/
│   ├── __init__.py      # Package exports
│   ├── models.py        # Article dataclass
│   ├── scraper.py       # Core scraping logic (KompasScraper)
│   └── utils.py         # Text cleaning, CSV/JSON export
├── tests/
│   ├── test_models.py
│   ├── test_scraper.py
│   └── test_utils.py
├── main.py              # CLI entry point
└── requirements.txt
```

---

## Running Tests

```bash
pip install pytest
python -m pytest tests/ -v
```

---

## Notes

- The scraper respects a configurable delay between requests (default **1 second**).
- Kompas.com may return different HTML layouts over time; the scraper tries JSON-LD structured data first and falls back to CSS-selector-based HTML parsing.
- This tool is intended for personal research and data-mining purposes. Always respect [Kompas.com's Terms of Service](https://www.kompas.com/about/terms-and-conditions).
