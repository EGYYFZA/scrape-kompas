"""Tests for utility functions (clean_text, save_csv, save_json)."""

import csv
import json
import os
import tempfile

import pytest

from kompas.models import Article
from kompas.utils import clean_text, save_csv, save_json


class TestCleanText:
    def test_strips_whitespace(self):
        assert clean_text("  hello world  ") == "hello world"

    def test_collapses_internal_whitespace(self):
        assert clean_text("hello   world\n\tfoo") == "hello world foo"

    def test_empty_string(self):
        assert clean_text("") == ""

    def test_only_whitespace(self):
        assert clean_text("   \t\n  ") == ""


class TestSaveCsv:
    def _make_articles(self):
        return [
            Article(
                url="https://kompas.com/read/1",
                title="Artikel Satu",
                author="Penulis A",
                published_at="2024-01-01",
                category="Nasional",
                content="Konten satu.",
                image_url="https://img.kompas.com/1.jpg",
                tags=["tag1", "tag2"],
                editor="Editor X",
            ),
            Article(
                url="https://kompas.com/read/2",
                title="Artikel Dua",
                tags=[],
            ),
        ]

    def test_creates_file(self):
        articles = self._make_articles()
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            path = f.name
        try:
            save_csv(articles, path)
            assert os.path.exists(path)
            assert os.path.getsize(path) > 0
        finally:
            os.unlink(path)

    def test_csv_content(self):
        articles = self._make_articles()
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            path = f.name
        try:
            save_csv(articles, path)
            with open(path, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            assert len(rows) == 2
            assert rows[0]["title"] == "Artikel Satu"
            assert rows[0]["tags"] == "tag1|tag2"
            assert rows[1]["tags"] == ""
        finally:
            os.unlink(path)

    def test_empty_list_creates_no_file_content(self):
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            path = f.name
        try:
            # File is created empty by tempfile; save_csv should leave it empty
            save_csv([], path)
            assert os.path.getsize(path) == 0
        finally:
            os.unlink(path)


class TestSaveJson:
    def _make_articles(self):
        return [
            Article(
                url="https://kompas.com/read/1",
                title="Artikel JSON",
                tags=["foo", "bar"],
            ),
        ]

    def test_creates_valid_json(self):
        articles = self._make_articles()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            save_json(articles, path)
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            assert isinstance(data, list)
            assert data[0]["title"] == "Artikel JSON"
            assert data[0]["tags"] == ["foo", "bar"]
        finally:
            os.unlink(path)

    def test_unicode_preserved(self):
        articles = [Article(url="u", title="Berita Hari Ini 🗞️")]
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            save_json(articles, path)
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            assert "Berita Hari Ini" in data[0]["title"]
        finally:
            os.unlink(path)
