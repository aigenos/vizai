"""Deterministic enrichment: priority ranking + article images + a Top Stories
section that does NOT depend on the model.

This is the reliability layer. Whatever the LLM does (or fails to do), we always
produce a "Top Stories" strip built straight from the fetched candidate items —
with real source links, og:image thumbnails, and a defensible priority order —
so every digest has clickable, image-rich, sensibly-ranked sources even on a weak
local model with no web grounding.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime

import requests

from .fetchers import Item, USER_AGENT, _hf_upvotes

log = logging.getLogger("aigenos.enrich")

# Source authority (named publishers beat generic category weight).
_AUTHORITY = {
    "OpenAI": 95, "Anthropic": 95, "Google DeepMind": 92, "Meta AI": 90,
    "Mistral": 85, "Hugging Face": 85, "Google AI (The Keyword)": 78,
    "Microsoft Research": 75, "NVIDIA Developer": 75, "Microsoft AI Blog": 70,
    "Cohere": 70, "Together AI": 66, "AWS ML Blog": 62, "LangChain": 60,
}
_CATEGORY_BASE = {
    "lab": 68, "research": 60, "newsletter": 55, "infra": 52, "community": 46,
}

# Down-weight corporate / PR items the reader called out as low-signal.
_BIZ_RE = re.compile(
    r"\b(S-1|IPO|SEC|fil(?:ed|ing)|funding|raises?|raised|valuation|round|"
    r"partnership|hires?|hiring|appoints?|acquir\w*|merger|lawsuit|board|"
    r"\$\d+\s?(?:million|billion|m|b)\b)",
    re.IGNORECASE,
)
# Up-weight capability / builder-relevant signal.
_CAPABILITY_RE = re.compile(
    r"\b(release[sd]?|launch\w*|open[- ]?source|open[- ]?weights?|model|"
    r"benchmark|SOTA|state[- ]of[- ]the[- ]art|outperform\w*|inference|"
    r"training|fine[- ]?tun\w*|quantiz\w*|context window|agent\w*|reasoning|"
    r"RAG|retrieval|throughput|latency|tokens?/s)\b",
    re.IGNORECASE,
)


def priority_score(item: Item, now: datetime) -> float:
    """Rank by builder-relevance, not by who has the biggest PR team."""
    score = float(_AUTHORITY.get(item.source, _CATEGORY_BASE.get(item.category, 45)))

    # Recency: today >> last week.
    age = item.age_days(now)
    score += max(0.0, 25.0 - age * 4.0)

    # Research community signal.
    score += min(70.0, float(_hf_upvotes(item)))

    # Capability vs corporate-news nudges (the reader's ordering complaint).
    text = f"{item.title} {item.summary[:200]}"
    if _CAPABILITY_RE.search(text):
        score += 18.0
    if _BIZ_RE.search(text):
        score -= 32.0

    return score


def rank_by_priority(items: list[Item], now: datetime) -> list[Item]:
    return sorted(items, key=lambda it: priority_score(it, now), reverse=True)


_OG_RE = (
    re.compile(r'<meta[^>]+property=["\']og:image(?::secure_url)?["\'][^>]+content=["\']([^"\']+)', re.I),
    re.compile(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', re.I),
    re.compile(r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)', re.I),
)


def fetch_og_image(url: str, timeout: int = 8) -> str | None:
    """Best-effort: pull a page's og:image (the article's hero thumbnail).
    Returns None on any failure — never raises."""
    try:
        r = requests.get(
            url, headers={"User-Agent": USER_AGENT}, timeout=timeout,
            stream=True, allow_redirects=True,
        )
        if r.status_code >= 300 or "html" not in r.headers.get("content-type", "").lower():
            return None
        raw = r.raw.read(200_000, decode_content=True) or b""
        head = raw.decode("utf-8", "ignore")
    except (requests.RequestException, ValueError, OSError):
        return None
    finally:
        try:
            r.close()  # type: ignore
        except Exception:
            pass
    for rx in _OG_RE:
        m = rx.search(head)
        if m:
            img = m.group(1).strip()
            if img.startswith("//"):
                img = "https:" + img
            if img.startswith("http"):
                return img
    return None


def _favicon(domain: str) -> str:
    return f"https://www.google.com/s2/favicons?domain={domain}&sz=64"


def _domain(url: str) -> str:
    from urllib.parse import urlparse
    try:
        net = urlparse(url).netloc.lower()
        return net[4:] if net.startswith("www.") else net
    except (ValueError, AttributeError):
        return ""


def build_top_stories(
    items: list[Item], now: datetime, count: int, with_images: bool
) -> str:
    """Render the deterministic Top Stories section: ranked rows with a thumbnail
    (og:image, falling back to the source favicon), linked title, and source·date.
    Marked <!--SECTION:topstories--> and public (kept in the archive)."""
    ranked = rank_by_priority(items, now)[:count]
    if not ranked:
        return ""

    rows: list[str] = []
    img_hits = 0
    for it in ranked:
        dom = _domain(it.url) or "news"
        thumb = fetch_og_image(it.url) if with_images else None
        if thumb:
            img_hits += 1
        thumb = thumb or _favicon(dom)
        is_fav = "favicons" in thumb
        date = it.published.strftime("%b %d") if it.published else ""
        # Thumbnail cell: big article image, or small centered favicon fallback.
        if is_fav:
            thumb_cell = (
                '<td width="76" style="width:76px;vertical-align:middle;padding:0 14px 0 0;">'
                '<div style="width:64px;height:64px;border-radius:12px;background:#f1f0fb;'
                'text-align:center;line-height:64px;">'
                f'<img src="{thumb}" width="28" height="28" alt="" style="vertical-align:middle;border:0;border-radius:6px;"></div></td>'
            )
        else:
            thumb_cell = (
                '<td width="76" style="width:76px;vertical-align:middle;padding:0 14px 0 0;">'
                f'<img src="{thumb}" width="64" height="64" alt="" '
                'style="width:64px;height:64px;object-fit:cover;border-radius:12px;border:0;display:block;"></td>'
            )
        rows.append(
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
            'class="aigenos-src-row" style="margin:10px 0;border:1px solid #ece9fb;border-radius:14px;'
            'background:#ffffff;"><tr>'
            '<td style="padding:12px 14px;">'
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>'
            f'{thumb_cell}'
            '<td style="vertical-align:middle;">'
            f'<a href="{it.url}" class="aigenos-src-title" style="color:#14142a;text-decoration:none;'
            f'font-weight:650;font-size:15px;line-height:1.35;">{_esc(it.title)}</a>'
            f'<div class="aigenos-src-meta" style="margin-top:4px;font-size:12px;color:#8a8a9a;">'
            f'<img src="{_favicon(dom)}" width="13" height="13" alt="" style="vertical-align:middle;margin-right:5px;border-radius:3px;border:0;">'
            f'{_esc(it.source)}{" · " + date if date else ""}</div>'
            '</td></tr></table></td></tr></table>'
        )

    log.info("top stories: %d item(s), %d og:image thumbnail(s)", len(ranked), img_hits)
    return (
        "<!--SECTION:topstories-->\n"
        '<h2>📌 Top Stories — Ranked &amp; Sourced (skim)</h2>\n'
        "<p>The day's highest-signal items, ranked by builder-relevance, each "
        "linked to its primary source.</p>\n" + "\n".join(rows)
    )


def _esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
