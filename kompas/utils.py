"""Utility helpers: CSV / JSON export, text cleaning."""

import csv
import json
import re
from typing import List

from .models import Article


def clean_text(text: str) -> str:
    """Strip excess whitespace and normalize newlines."""
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def save_csv(articles: List[Article], filepath: str) -> None:
    """Save a list of articles to a CSV file.

    Args:
        articles: List of Article objects to save.
        filepath: Destination file path.
    """
    if not articles:
        return

    fieldnames = list(articles[0].to_dict().keys())
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for article in articles:
            row = article.to_dict()
            # Serialise the tags list as a pipe-separated string for CSV
            row["tags"] = "|".join(row["tags"])
            writer.writerow(row)


def save_json(articles: List[Article], filepath: str) -> None:
    """Save a list of articles to a JSON file.

    Args:
        articles: List of Article objects to save.
        filepath: Destination file path.
    """
    data = [a.to_dict() for a in articles]
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
