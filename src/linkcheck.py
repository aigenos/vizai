"""Pre-send link verification: HEAD-check every href in the digest.

Dead links are flagged visibly (a small ⚠ marker after the anchor) and logged,
so the reader is warned and the operator can see broken sources in CI logs.

FAIL-OPEN by design: timeouts, odd servers, and full network outages must never
abort the daily run — at worst the digest ships with unchecked links, exactly
as it did before this module existed.
"""

from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor

import requests

from .fetchers import USER_AGENT

log = logging.getLogger("aigenos.linkcheck")

_HREF_RX = re.compile(r'<a\b[^>]*\bhref="(https?://[^"]+)"', re.IGNORECASE)

# Don't burn CI minutes on a pathological digest; anything beyond the cap is
# left unchecked (fail-open).
_MAX_LINKS = 80

_DEAD_FLAG = (
    '<sup class="aigenos-deadlink" title="link did not respond at send time" '
    'style="color:#b45309;font-size:11px;font-weight:700;">⚠</sup>'
)


def extract_links(html: str) -> list[str]:
    """Unique http(s) hrefs in document order."""
    seen: set[str] = set()
    out: list[str] = []
    for url in _HREF_RX.findall(html):
        if url not in seen:
            seen.add(url)
            out.append(url)
    return out


def check_url(url: str, timeout: float = 5.0, retries: int = 1) -> bool:
    """True if the URL responds < 400. HEAD first; one retry falls back to a
    light GET because many sites (arXiv included) reject or mishandle HEAD."""
    for attempt in range(retries + 1):
        method = "HEAD" if attempt == 0 else "GET"
        try:
            resp = requests.request(
                method,
                url,
                headers={"User-Agent": USER_AGENT},
                timeout=timeout,
                allow_redirects=True,
                stream=True,
            )
            resp.close()
            if resp.status_code < 400:
                return True
            # 403/405/429 are bot-walls or method quirks, not dead pages.
            if resp.status_code in (403, 405, 429):
                if attempt < retries:
                    continue
                return True
        except requests.RequestException:
            if attempt < retries:
                continue
            return False
    return False


def find_dead_links(
    html: str, timeout: float = 5.0, max_workers: int = 8
) -> list[str]:
    """Check all links in parallel; return the ones that failed."""
    links = extract_links(html)[:_MAX_LINKS]
    if not links:
        return []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        results = list(pool.map(lambda u: check_url(u, timeout=timeout), links))
    return [u for u, ok in zip(links, results) if not ok]


def flag_dead_links(html: str, dead: list[str]) -> str:
    """Append a visible ⚠ marker after every anchor pointing at a dead URL."""
    for url in dead:
        html = re.sub(
            r'(<a\b[^>]*\bhref="' + re.escape(url) + r'"[^>]*>(?:(?!</a>).)*?</a>)',
            r"\1" + _DEAD_FLAG,
            html,
            flags=re.IGNORECASE | re.DOTALL,
        )
    return html


def verify_links(html: str, timeout: float = 5.0, max_workers: int = 8) -> str:
    """The fail-open entry point: flag dead links, never raise."""
    try:
        dead = find_dead_links(html, timeout=timeout, max_workers=max_workers)
        if dead:
            for url in dead:
                log.warning("dead link in digest: %s", url)
            html = flag_dead_links(html, dead)
            log.info("link check: flagged %d dead link(s)", len(dead))
        else:
            log.info("link check: all %d link(s) ok", len(extract_links(html)))
    except Exception as exc:  # noqa: BLE001 — link checking must never kill the run
        log.warning("link check skipped (%s)", exc)
    return html
