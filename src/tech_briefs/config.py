from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_config(path: Path | None = None) -> dict[str, Any]:
    config_path = path or project_root() / "config" / "sources.yaml"
    with config_path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def ensure_dirs(root: Path) -> None:
    for rel in [
        "data/state",
        "data/cache",
        "output/daily",
        "output/weekly",
        "output/alerts",
        "logs",
    ]:
        (root / rel).mkdir(parents=True, exist_ok=True)

