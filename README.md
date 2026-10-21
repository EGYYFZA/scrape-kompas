# Kompas News Dataset Collector

A Python command-line project for collecting Indonesian news articles for data mining.

## Stack

HTTPX, Selectolax, lxml, pandas, python-dateutil, Tenacity, and tqdm.

## Setup

```sh
python -m venv .venv
```

Activate the environment, then install dependencies:

```sh
python -m pip install -r requirements.txt
python scrape_kompas_news.py --help
```

A small collection run:

```sh
python scrape_kompas_news.py --max 10 --concurrency 1 --out sample.csv
```

Review the source site's access rules and content permissions before collecting or redistributing articles. Avoid aggressive concurrency. Generated crawl state and virtual environments stay local. Existing datasets are research inputs, not a grant of rights to the source articles.

See [SECURITY.md](SECURITY.md).
