"""Data models for scraped Kompas.com articles."""

from dataclasses import dataclass, field, asdict
from typing import List, Optional


@dataclass
class Article:
    """Represents a single scraped news article from Kompas.com."""

    url: str
    title: str
    author: Optional[str] = None
    published_at: Optional[str] = None
    category: Optional[str] = None
    content: Optional[str] = None
    image_url: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    editor: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert the article to a plain dictionary."""
        return asdict(self)

    def __str__(self) -> str:
        return (
            f"[{self.category or 'Uncategorized'}] {self.title}\n"
            f"  URL    : {self.url}\n"
            f"  Author : {self.author or '-'}\n"
            f"  Date   : {self.published_at or '-'}\n"
            f"  Tags   : {', '.join(self.tags) if self.tags else '-'}"
        )
