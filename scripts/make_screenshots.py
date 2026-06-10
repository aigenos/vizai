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

    digest = args.digest or find_latest_digest()
    if not digest or not os.path.exists(digest):
        sys.exit("No digest HTML found — run the pipeline once or pass a path.")
    render(digest, args.out, args.width, args.height)


if __name__ == "__main__":
    main()
