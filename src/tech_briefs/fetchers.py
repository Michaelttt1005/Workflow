from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Iterable

import feedparser
import requests
from dateutil.parser import parse as parse_dt

from .models import Candidate


USER_AGENT = "tech-brief-radar/0.1 (+https://github.com/Michaelttt1005/Workflow)"


def _parse_date(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    try:
        dt = parse_dt(value)
    except Exception:
        try:
            dt = parsedate_to_datetime(value)
        except Exception:
            return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _clean(value: str | None, limit: int = 900) -> str:
    text = " ".join((value or "").replace("\n", " ").split())
    return text[:limit]


def fetch_rss_sources(config: dict, days: int) -> list[Candidate]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    candidates: list[Candidate] = []
    for source in config.get("rss_sources", []):
        parsed = feedparser.parse(source["url"], request_headers={"User-Agent": USER_AGENT})
        for entry in parsed.entries[:25]:
            published = _parse_date(
                getattr(entry, "published", None)
                or getattr(entry, "updated", None)
                or getattr(entry, "created", None)
            )
            if published < cutoff:
                continue
            title = _clean(getattr(entry, "title", "Untitled"), 240)
            url = getattr(entry, "link", source["url"])
            summary = _clean(getattr(entry, "summary", "") or getattr(entry, "description", ""))
            candidates.append(
                Candidate(
                    title=title,
                    url=url,
                    source=source["name"],
                    published_at=published,
                    summary=summary,
                    item_type="official",
                )
            )
    return candidates


def fetch_github_releases(config: dict, days: int, token: str | None = None) -> list[Candidate]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    headers = {"Accept": "application/vnd.github+json", "User-Agent": USER_AGENT}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    candidates: list[Candidate] = []
    for repo in config.get("github_releases", []):
        url = f"https://api.github.com/repos/{repo}/releases"
        try:
            response = requests.get(url, headers=headers, timeout=20)
            response.raise_for_status()
        except Exception:
            continue
        for release in response.json()[:5]:
            published = _parse_date(release.get("published_at") or release.get("created_at"))
            if published < cutoff:
                continue
            candidates.append(
                Candidate(
                    title=_clean(release.get("name") or release.get("tag_name") or repo, 240),
                    url=release.get("html_url") or f"https://github.com/{repo}/releases",
                    source=f"GitHub Release: {repo}",
                    published_at=published,
                    summary=_clean(release.get("body") or ""),
                    item_type="github_release",
                    raw={"repo": repo, "tag": release.get("tag_name")},
                )
            )
    return candidates


def fetch_arxiv(config: dict, days: int) -> list[Candidate]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    candidates: list[Candidate] = []
    for category in config.get("arxiv_categories", []):
        query = (
            "http://export.arxiv.org/api/query?"
            f"search_query=cat:{category}&sortBy=submittedDate&sortOrder=descending&max_results=20"
        )
        parsed = feedparser.parse(query, request_headers={"User-Agent": USER_AGENT})
        for entry in parsed.entries[:20]:
            published = _parse_date(getattr(entry, "published", None) or getattr(entry, "updated", None))
            if published < cutoff:
                continue
            candidates.append(
                Candidate(
                    title=_clean(getattr(entry, "title", "Untitled"), 240),
                    url=getattr(entry, "link", query),
                    source=f"arXiv {category}",
                    published_at=published,
                    summary=_clean(getattr(entry, "summary", "")),
                    item_type="paper",
                )
            )
    return candidates


def fetch_all(config: dict, days: int, github_token: str | None = None) -> list[Candidate]:
    all_items: list[Candidate] = []
    for fetcher in (
        lambda: fetch_rss_sources(config, days),
        lambda: fetch_github_releases(config, days, github_token),
        lambda: fetch_arxiv(config, days),
    ):
        try:
            all_items.extend(fetcher())
        except Exception:
            continue
    return dedupe(all_items)


def dedupe(items: Iterable[Candidate]) -> list[Candidate]:
    seen: set[str] = set()
    result: list[Candidate] = []
    for item in items:
        if item.key in seen:
            continue
        seen.add(item.key)
        result.append(item)
    return result

