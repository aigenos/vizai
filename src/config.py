"""Runtime configuration, resolved from environment variables.

The analysis provider is pluggable (Gemini or Claude), chosen via PROVIDER.
Only the API key for the selected provider is required.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

VALID_PROVIDERS = {"gemini", "claude", "ollama"}

# Default model per provider when DIGEST_MODEL is not set.
DEFAULT_MODELS = {
    "gemini": "gemini-2.5-flash",
    "claude": "claude-sonnet-4-6",
    "ollama": "llama3.1",
}


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
    provider: str
    anthropic_api_key: str
    gemini_api_key: str
    resend_api_key: str
    ollama_host: str
    dry_run: bool
    email_to: str
    email_from: str
    model: str
    lookback_days: int
    enable_web_search: bool
    arxiv_max_results: int
    save_html: bool

    @classmethod
    def from_env(cls) -> "Config":
        provider = (os.environ.get("PROVIDER") or "").strip().lower() or "gemini"
        if provider not in VALID_PROVIDERS:
            raise SystemExit(
                f"Invalid PROVIDER={provider!r}. "
                f"Choose one of: {', '.join(sorted(VALID_PROVIDERS))}."
            )

        anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        gemini_api_key = (
            os.environ.get("GEMINI_API_KEY", "")
            or os.environ.get("GOOGLE_API_KEY", "")
        ).strip()
        resend_api_key = os.environ.get("RESEND_API_KEY", "").strip()
        dry_run = _get_bool("DRY_RUN", False)

        # Only the selected provider's key is required (ollama needs none).
        missing = []
        if provider == "gemini" and not gemini_api_key:
            missing.append("GEMINI_API_KEY")
        if provider == "claude" and not anthropic_api_key:
            missing.append("ANTHROPIC_API_KEY")
        # Resend is only needed when we actually send (skipped in DRY_RUN).
        if not dry_run and not resend_api_key:
            missing.append("RESEND_API_KEY")
        if missing:
            raise SystemExit(
                "Missing required environment variable(s): "
                + ", ".join(missing)
                + f"\n(provider={provider}). See .env.example for setup details."
            )

        model = os.environ.get("DIGEST_MODEL", "").strip() or DEFAULT_MODELS[provider]

        return cls(
            provider=provider,
            anthropic_api_key=anthropic_api_key,
            gemini_api_key=gemini_api_key,
            resend_api_key=resend_api_key,
            ollama_host=os.environ.get("OLLAMA_HOST", "http://localhost:11434").strip(),
            dry_run=dry_run,
            email_to=os.environ.get("EMAIL_TO", "mukeshatnyc1@gmail.com").strip(),
            email_from=os.environ.get(
                "EMAIL_FROM", "AI Daily Digest <onboarding@resend.dev>"
            ).strip(),
            model=model,
            lookback_days=_get_int("LOOKBACK_DAYS", 3),
            enable_web_search=_get_bool("ENABLE_WEB_SEARCH", True),
            arxiv_max_results=_get_int("ARXIV_MAX_RESULTS", 40),
            save_html=_get_bool("SAVE_HTML", True),
        )
