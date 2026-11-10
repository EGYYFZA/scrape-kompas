# Kompas News Collector

A Python command-line collector that exports Indonesian news article records for data-mining research.

**Python · HTTPX · Selectolax · pandas** · Command-line research tool

## Collection workflow

Configure the article limit, date range and concurrency, then export the collected
records as CSV. The project uses HTTPX, Selectolax, lxml, pandas, python-dateutil,
Tenacity and tqdm.

## Setup

Create and activate a Python virtual environment, then run:

```sh
python -m pip install -r requirements.txt
python scrape_kompas_news.py --help
```

A small collection example:

```sh
python scrape_kompas_news.py --max 10 --concurrency 1 --out sample.csv
```

Use <code>--start</code> and <code>--days</code> to select a date window. Review
<code>--help</code> before starting a larger collection.

## Responsible use

Review the source site's access rules and content permissions before collecting
or redistributing articles. Avoid aggressive concurrency. Included datasets are
research inputs, not a grant of rights to the original articles. Keep crawl
state, local environments and personal data out of public contributions.
See [SECURITY.md](SECURITY.md).
