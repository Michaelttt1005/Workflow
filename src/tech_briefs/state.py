from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .models import Candidate


class SeenState:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        else:
            self.data = {"seen": []}

    @property
    def seen_keys(self) -> set[str]:
        return {item.get("key", "") for item in self.data.get("seen", [])}

    def has_seen(self, candidate: Candidate) -> bool:
        return candidate.key in self.seen_keys

    def remember(self, candidate: Candidate, alert_sent: bool) -> None:
        existing = self.seen_keys
        if candidate.key in existing:
            return
        self.data.setdefault("seen", []).append(
            {
                "key": candidate.key,
                "title": candidate.title,
                "url": candidate.url,
                "source": candidate.source,
                "published_at": candidate.published_at.astimezone(timezone.utc).isoformat(),
                "first_seen_at": datetime.now(timezone.utc).isoformat(),
                "score": candidate.score,
                "alert_sent": alert_sent,
            }
        )

    def save(self) -> None:
        self.data["seen"] = self.data.get("seen", [])[-500:]
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

