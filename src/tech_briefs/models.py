from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class Candidate:
    title: str
    url: str
    source: str
    published_at: datetime
    summary: str = ""
    item_type: str = "news"
    score: int = 0
    reasons: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def key(self) -> str:
        return canonical_key(self.url, self.title)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "source": self.source,
            "published_at": self.published_at.astimezone(timezone.utc).isoformat(),
            "summary": self.summary,
            "item_type": self.item_type,
            "score": self.score,
            "reasons": self.reasons,
        }


def canonical_key(url: str, title: str) -> str:
    normalized_url = (url or "").split("?")[0].split("#")[0].strip().lower()
    normalized_title = " ".join((title or "").lower().split())
    return f"{normalized_url}|{normalized_title[:120]}"

