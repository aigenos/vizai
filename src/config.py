"""Runtime configuration, resolved from environment variables.

All knobs have sensible defaults so the agent runs with just the two required
secrets (ANTHROPIC_API_KEY, RESEND_API_KEY) set.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _get_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class Config:
    anthropic_api_key: str
    resend_api_key: str
    email_to: str
    email_from: str
    model: str
    lookback_days: int
    enable_web_search: bool
    arxiv_max_results: int
    save_html: bool

    @classmethod
    def from_env(cls) -> "Config":
        anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        resend_api_key = os.environ.get("RESEND_API_KEY", "").strip()

        missing = []
        if not anthropic_api_key:
            missing.append("ANTHROPIC_API_KEY")
        if not resend_api_key:
            missing.append("RESEND_API_KEY")
        if missing:
            raise SystemExit(
                "Missing required environment variable(s): "
                + ", ".join(missing)
                + "\nSee .env.example for setup details."
            )

        return cls(
            anthropic_api_key=anthropic_api_key,
            resend_api_key=resend_api_key,
            email_to=os.environ.get("EMAIL_TO", "mukeshatnyc1@gmail.com").strip(),
            email_from=os.environ.get(
                "EMAIL_FROM", "AI Daily Digest <onboarding@resend.dev>"
            ).strip(),
            model=os.environ.get("DIGEST_MODEL", "claude-sonnet-4-6").strip(),
            lookback_days=_get_int("LOOKBACK_DAYS", 3),
            enable_web_search=_get_bool("ENABLE_WEB_SEARCH", True),
            arxiv_max_results=_get_int("ARXIV_MAX_RESULTS", 40),
            save_html=_get_bool("SAVE_HTML", True),
        )
