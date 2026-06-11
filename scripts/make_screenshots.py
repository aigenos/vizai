#!/usr/bin/env python3
"""Render hero screenshots of the latest digest for the README.

Takes the newest ``digest_YYYYMMDD.html`` (from docs/digests/ by default, or a
path you pass) and renders light- and dark-mode PNGs to ``docs/assets/`` using
Playwright's Chromium with ``prefers-color-scheme`` emulation — the same
mechanism mail clients use, so the screenshots match what subscribers see.

Setup (dev-only deps, not in the runtime requirements):
    pip install -r requirements-dev.txt
    python -m playwright install chromium

Usage:
    python scripts/make_screenshots.py                 # newest archived digest
    python scripts/make_screenshots.py digest_20260610.html
    python scripts/make_screenshots.py --out docs/assets --width 720 --height 900
"""

from __future__ import annotations

import argparse
import os
import re
import sys

_DIGEST_RX = re.compile(r"digest_(\d{8})\.html$")

# Shown only when no real issue exists yet (fresh fork, pre-first-run): a
# representative sample rendered through the real email template, so the README
# hero is never a broken image. Replaced by real-issue screenshots as soon as
# the archive has content.
_SAMPLE_BODY = """\
<!--SECTION:pulse-->
<h2>⚡ The Pulse — If You Only Read One Thing (90 sec read)</h2>
<h3>🎯 Today's Game-Changer</h3>
<p><strong><a href="https://example.com">Sample issue</a></strong> — this is a
preview rendered before your first digest run. Each real issue opens with the
single most important development of the day, source-linked, with one tight
clause on why it matters more than anything else.</p>
<h3>📍 In a Nutshell</h3>
<ul>
<li><strong>A model release</strong> — what changed for builders. <a href="https://example.com">source</a></li>
<li><strong>A benchmark move</strong> — who moved, by how much. <a href="https://example.com">source</a></li>
<li><strong>A fast-rising repo</strong> — why dev mindshare is shifting. <a href="https://example.com">source</a></li>
<li><strong>A funding round</strong> — the bet it's buying. <a href="https://example.com">source</a></li>
</ul>
<!--SECTION:opp_teaser-->
<h2>🚀 Opportunity of the Day (2 min read)</h2>
<h3>The thing to build</h3>
<ul>
<li><strong>The gap:</strong> what's missing in the current stack.</li>
<li><strong>Why now:</strong> what changed this week that makes it tractable.</li>
<li><strong>Build as:</strong> OSS library / dev tool / SaaS — and why.</li>
<li><strong>Already heating up:</strong> two independent, quantified signals.</li>
<li><strong>First step this week:</strong> one concrete validation action.</li>
</ul>
<p><em>Run your first digest and this becomes a real, evidence-backed pick.</em></p>"""


def _render_sample_digest() -> str:
    """Build a sample issue through the real pipeline renderer and return its
    temp-file path. Used only when the archive has no issues yet."""
    import tempfile
    from datetime import datetime, timezone

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from src.emailer import render_html

    html = render_html(_SAMPLE_BODY, datetime.now(timezone.utc))
    fd, path = tempfile.mkstemp(suffix=".html", prefix="daily_sample_")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"no archived digest yet — rendering sample issue ({path})")
    return path


def find_latest_digest(digests_dir: str = "docs/digests") -> str | None:
    if not os.path.isdir(digests_dir):
        return None
    candidates = sorted(
        (n for n in os.listdir(digests_dir) if _DIGEST_RX.search(n)), reverse=True
    )
    return os.path.join(digests_dir, candidates[0]) if candidates else None


def render(digest_path: str, out_dir: str, width: int, height: int) -> list[str]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit(
            "Playwright not installed. Run:\n"
            "  pip install -r requirements-dev.txt\n"
            "  python -m playwright install chromium"
        )

    os.makedirs(out_dir, exist_ok=True)
    url = "file://" + os.path.abspath(digest_path)
    written: list[str] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for scheme in ("light", "dark"):
            page = browser.new_page(
                viewport={"width": width, "height": height},
                color_scheme=scheme,
                device_scale_factor=2,  # crisp on retina / README zoom
            )
            page.goto(url)
            page.wait_for_load_state("networkidle")
            out_path = os.path.join(out_dir, f"hero-{scheme}.png")
            page.screenshot(path=out_path)
            page.close()
            written.append(out_path)
            print(f"wrote {out_path}")
        browser.close()
    return written


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("digest", nargs="?", help="digest HTML (default: newest in docs/digests/)")
    ap.add_argument("--out", default="docs/assets", help="output dir (default: docs/assets)")
    ap.add_argument("--width", type=int, default=720)
    ap.add_argument("--height", type=int, default=1000)
    args = ap.parse_args()

    digest = args.digest or find_latest_digest() or _render_sample_digest()
    if not os.path.exists(digest):
        sys.exit(f"Digest HTML not found: {digest}")
    render(digest, args.out, args.width, args.height)


if __name__ == "__main__":
    main()
