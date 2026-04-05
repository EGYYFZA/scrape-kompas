"""Tests for the Article data model."""

import pytest

from kompas.models import Article


class TestArticle:
    def test_basic_creation(self):
        article = Article(url="https://kompas.com/read/1", title="Test")
        assert article.url == "https://kompas.com/read/1"
        assert article.title == "Test"
        assert article.tags == []

    def test_to_dict_has_all_fields(self):
        article = Article(
            url="https://kompas.com/read/1",
            title="Berita Terkini",
            author="Penulis A",
            published_at="2024-01-01T10:00:00+07:00",
            category="Nasional",
            content="Isi berita",
            image_url="https://cdn.kompas.com/img.jpg",
            tags=["politik", "nasional"],
            editor="Editor B",
        )
        d = article.to_dict()
        assert d["url"] == "https://kompas.com/read/1"
        assert d["title"] == "Berita Terkini"
        assert d["author"] == "Penulis A"
        assert d["published_at"] == "2024-01-01T10:00:00+07:00"
        assert d["category"] == "Nasional"
        assert d["content"] == "Isi berita"
        assert d["image_url"] == "https://cdn.kompas.com/img.jpg"
        assert d["tags"] == ["politik", "nasional"]
        assert d["editor"] == "Editor B"

    def test_str_representation(self):
        article = Article(
            url="https://kompas.com/read/1",
            title="Berita",
            author="Penulis",
            published_at="2024-01-01",
            category="Tekno",
            tags=["ai", "teknologi"],
        )
        text = str(article)
        assert "Tekno" in text
        assert "Berita" in text
        assert "Penulis" in text
        assert "ai" in text

    def test_str_representation_no_optional(self):
        article = Article(url="https://kompas.com/read/1", title="Berita")
        text = str(article)
        assert "Uncategorized" in text
        assert "-" in text

    def test_tags_default_empty_list(self):
        a1 = Article(url="u1", title="t1")
        a2 = Article(url="u2", title="t2")
        a1.tags.append("tag1")
        # Confirm the default factory gives independent lists
        assert a2.tags == []
