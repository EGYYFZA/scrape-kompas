#!/usr/bin/env python3
"""Command-line interface for the Kompas.com scraper."""

import argparse
import logging
import sys

from kompas import KompasScraper
from kompas.scraper import CATEGORIES
from kompas.utils import save_csv, save_json


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kompas-scraper",
        description="Scrape news articles from Kompas.com",
    )
    parser.add_argument(
        "category",
        nargs="?",
        default="terkini",
        help=(
            "Category to scrape. One of: "
            + ", ".join(sorted(CATEGORIES.keys()))
            + ". Or a full URL. (default: terkini)"
        ),
    )
    parser.add_argument(
        "-n", "--max-articles",
        type=int,
        default=10,
        dest="max_articles",
        help="Maximum number of articles to scrape (default: 10)",
    )
    parser.add_argument(
        "-p", "--max-pages",
        type=int,
        default=5,
        dest="max_pages",
        help="Maximum number of listing pages to crawl (default: 5)",
    )
    parser.add_argument(
        "--no-content",
        action="store_true",
        dest="no_content",
        help="Skip fetching full article content (faster)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay in seconds between requests (default: 1.0)",
    )
    parser.add_argument(
        "--output-csv",
        metavar="FILE",
        dest="output_csv",
        help="Save results to a CSV file",
    )
    parser.add_argument(
        "--output-json",
        metavar="FILE",
        dest="output_json",
        help="Save results to a JSON file",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    scraper = KompasScraper(delay=args.delay)

    articles = scraper.scrape_category(
        category=args.category,
        max_articles=args.max_articles,
        max_pages=args.max_pages,
        include_content=not args.no_content,
    )

    if not articles:
        print("No articles found.")
        return 1

    # Print summary to stdout
    print(f"\nScraped {len(articles)} article(s) from '{args.category}':\n")
    for i, article in enumerate(articles, 1):
        print(f"{i}. {article}")
        print()

    # Export
    if args.output_csv:
        save_csv(articles, args.output_csv)
        print(f"Saved CSV → {args.output_csv}")

    if args.output_json:
        save_json(articles, args.output_json)
        print(f"Saved JSON → {args.output_json}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
