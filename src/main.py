"""Entry point: fetch → synthesize → email the daily AI digest.

Run locally:  python -m src.main
In CI:        invoked by .github/workflows/daily-ai-digest.yml
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone

from .analyzer import build_digest
from .config import Config
from .emailer import render_html, send_email, subject_line
from .fetchers import dedupe, fetch_all_feeds, fetch_arxiv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("vizai")


def run() -> int:
    cfg = Config.from_env()
    now = datetime.now(timezone.utc)
    log.info("starting daily digest run (model=%s, lookback=%dd)", cfg.model, cfg.lookback_days)

    # 1. Fetch
    feed_items = fetch_all_feeds(cfg.lookback_days, now)
    arxiv_items = fetch_arxiv(cfg.lookback_days, now, cfg.arxiv_max_results)
    items = dedupe([*feed_items, *arxiv_items])
    log.info(
        "fetched %d item(s) total (%d feed, %d arXiv) after dedupe",
        len(items),
        len(feed_items),
        len(arxiv_items),
    )

    if not items and not cfg.enable_web_search:
        log.error("no items fetched and web search disabled — aborting")
        return 1

    # 2. Synthesize
    body = build_digest(cfg, items, now)
    html = render_html(body, now, engine=f"{cfg.provider} ({cfg.model})")

    # Always save to disk in DRY_RUN so you can eyeball the result locally.
    if cfg.save_html or cfg.dry_run:
        out_path = f"digest_{now.strftime('%Y%m%d')}.html"
        try:
            with open(out_path, "w", encoding="utf-8") as fh:
                fh.write(html)
            log.info("saved rendered digest to %s", out_path)
        except OSError as exc:
            log.warning("could not save html: %s", exc)

    # 3. Deliver (skipped in DRY_RUN)
    if cfg.dry_run:
        log.info("DRY_RUN enabled — skipping email send. Open %s to review.", out_path)
        return 0
    send_email(cfg, subject_line(now), html)
    log.info("done.")
    return 0


def main() -> None:
    try:
        sys.exit(run())
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        log.exception("digest run failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
