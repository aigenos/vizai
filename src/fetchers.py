"""Deterministic fetchers: RSS/Atom feeds and the arXiv API.

Each fetcher is fault-tolerant — a single broken feed or network hiccup logs a
warning and is skipped, never aborting the run.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Iterable
from xml.etree import ElementTree as ET

import feedparser
import requests
from dateutil import parser as date_parser

from .sources import ARXIV_CATEGORIES, ARXIV_QUERIES, RSS_FEEDS, Feed

log = logging.getLogger("aigenos.fetchers")

USER_AGENT = "dAIly-aigenos/1.0 (+https://github.com/aigenos)"
ARXIV_API = "http://export.arxiv.org/api/query"
ATOM_NS = {"a": "http://www.w3.org/2005/Atom"}


@dataclass
class Item:
    """A single piece of fetched content."""

    source: str
    category: str  # lab | newsletter | research
    title: str
    url: str
    published: datetime | None
    summary: str = ""
    authors: list[str] = field(default_factory=list)

    def age_days(self, now: datetime) -> float:
        if self.published is None:
            return 9_999.0
        return (now - self.published).total_seconds() / 86_400.0


def _to_utc(dt_struct) -> datetime | None:
    if not dt_struct:
        return None
    try:
        return datetime.fromtimestamp(time.mktime(dt_struct), tz=timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def _parse_date(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        dt = date_parser.parse(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (ValueError, OverflowError, TypeError):
        return None


def fetch_feed(feed: Feed, lookback_days: int, now: datetime) -> list[Item]:
    """Fetch and date-filter one RSS/Atom feed."""
    cutoff = now - timedelta(days=lookback_days)
    items: list[Item] = []
    try:
        resp = requests.get(
            feed.url, headers={"User-Agent": USER_AGENT}, timeout=20
        )
        resp.raise_for_status()
        parsed = feedparser.parse(resp.content)
    except (requests.RequestException, Exception) as exc:  # noqa: BLE001
        log.warning("skip feed %s (%s): %s", feed.name, feed.url, exc)
        return items

    for entry in parsed.entries:
        published = _to_utc(
            getattr(entry, "published_parsed", None)
            or getattr(entry, "updated_parsed", None)
        )
        # Keep undated entries (some feeds omit dates) but drop clearly-old ones.
        if published is not None and published < cutoff:
            continue
        summary = getattr(entry, "summary", "") or ""
        items.append(
            Item(
                source=feed.name,
                category=feed.category,
                title=(getattr(entry, "title", "") or "").strip(),
                url=getattr(entry, "link", "") or "",
                published=published,
                summary=_strip_html(summary)[:1200],
                authors=[a.get("name", "") for a in getattr(entry, "authors", [])],
            )
        )
    log.info("feed %s: %d recent item(s)", feed.name, len(items))
    return items


def fetch_all_feeds(lookback_days: int, now: datetime) -> list[Item]:
    items: list[Item] = []
    for feed in RSS_FEEDS:
        items.extend(fetch_feed(feed, lookback_days, now))
    return items


def fetch_arxiv(
    lookback_days: int, now: datetime, max_results: int
) -> list[Item]:
    """Query arXiv for recent agentic-AI papers across configured queries."""
    cutoff = now - timedelta(days=lookback_days)
    cat_filter = " OR ".join(f"cat:{c}" for c in ARXIV_CATEGORIES)
    seen: set[str] = set()
    items: list[Item] = []

    for query in ARXIV_QUERIES:
        search = f"({cat_filter}) AND ({query})"
        params = {
            "search_query": search,
            "start": 0,
            "max_results": max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
        try:
            resp = requests.get(
                ARXIV_API,
                params=params,
                headers={"User-Agent": USER_AGENT},
                timeout=30,
            )
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
        except (requests.RequestException, ET.ParseError) as exc:
            log.warning("skip arXiv query (%s): %s", query[:40], exc)
            continue

        for entry in root.findall("a:entry", ATOM_NS):
            url = _text(entry.find("a:id", ATOM_NS))
            if not url or url in seen:
                continue
            published = _parse_date(_text(entry.find("a:published", ATOM_NS)))
            if published is not None and published < cutoff:
                continue
            seen.add(url)
            authors = [
                _text(a.find("a:name", ATOM_NS))
                for a in entry.findall("a:author", ATOM_NS)
            ]
            items.append(
                Item(
                    source="arXiv",
                    category="research",
                    title=" ".join(_text(entry.find("a:title", ATOM_NS)).split()),
                    url=url,
                    published=published,
                    summary=" ".join(
                        _text(entry.find("a:summary", ATOM_NS)).split()
                    )[:1200],
                    authors=[a for a in authors if a],
                )
            )
        # Be polite to the arXiv API between queries.
        time.sleep(1.0)

    log.info("arXiv: %d recent paper(s)", len(items))
    return items


HF_PAPERS_API = "https://huggingface.co/api/daily_papers"


def fetch_hf_papers(lookback_days: int, now: datetime, max_results: int = 50) -> list[Item]:
    """Fetch Hugging Face Daily Papers — the curated 'must-read' trending papers.

    Unlike raw arXiv keyword search, this is community-upvoted, so it surfaces the
    papers people actually consider important. We carry the upvote count into the
    summary so the model can rank by real attention, and link the HF paper page
    (which shows discussion + links straight to the arXiv PDF).
    """
    cutoff = now - timedelta(days=lookback_days)
    items: list[Item] = []
    try:
        resp = requests.get(
            HF_PAPERS_API,
            params={"limit": max_results},
            headers={"User-Agent": USER_AGENT},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        log.warning("skip HF daily papers (%s): %s", HF_PAPERS_API, exc)
        return items

    for row in data if isinstance(data, list) else []:
        paper = row.get("paper") or {}
        pid = paper.get("id") or ""
        if not pid:
            continue
        published = _parse_date(paper.get("publishedAt") or row.get("publishedAt"))
        if published is not None and published < cutoff:
            continue
        upvotes = paper.get("upvotes") or 0
        abstract = " ".join((paper.get("summary") or "").split())
        items.append(
            Item(
                source="HF Daily Papers",
                category="research",
                title=" ".join((paper.get("title") or "").split()),
                url=f"https://huggingface.co/papers/{pid}",
                published=published,
                summary=f"[{upvotes}▲ upvotes on HF] {abstract}"[:1200],
                authors=[a.get("name", "") for a in (paper.get("authors") or []) if a.get("name")],
            )
        )

    # Surface the most-upvoted first so the per-source cap keeps the best.
    items.sort(key=lambda it: _hf_upvotes(it), reverse=True)
    log.info("HF daily papers: %d recent paper(s)", len(items))
    return items


def _hf_upvotes(it: Item) -> int:
    """Extract the upvote count we stashed at the front of the summary."""
    import re

    m = re.match(r"\[(\d+)▲", it.summary)
    return int(m.group(1)) if m else 0


def _text(el) -> str:
    return (el.text or "").strip() if el is not None else ""


def _strip_html(raw: str) -> str:
    """Very light HTML-to-text: good enough for feed summaries."""
    import re

    text = re.sub(r"<[^>]+>", " ", raw)
    text = re.sub(r"&[a-zA-Z]+;", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def dedupe(items: Iterable[Item]) -> list[Item]:
    """Drop items sharing a URL or near-identical title."""
    out: list[Item] = []
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    for it in items:
        url_key = it.url.rstrip("/").lower()
        title_key = "".join(c for c in it.title.lower() if c.isalnum())
        if url_key and url_key in seen_urls:
            continue
        if title_key and title_key in seen_titles:
            continue
        if url_key:
            seen_urls.add(url_key)
        if title_key:
            seen_titles.add(title_key)
        out.append(it)
    return out
