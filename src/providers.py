"""Pluggable analysis providers.

Each provider takes a system prompt + user prompt and returns the model's raw
text output (an HTML fragment). Web grounding is enabled per-provider when
``cfg.enable_web_search`` is true:

- Gemini  → Google Search grounding tool
- Claude  → web_search server tool (with pause_turn resume loop)

SDKs are imported lazily so you only need the package for the provider you use.
"""

from __future__ import annotations

import logging
import time
from typing import Callable, TypeVar

from .config import Config

log = logging.getLogger("vizai.providers")

T = TypeVar("T")

# Substrings that mark a retryable, transient server/rate condition.
_TRANSIENT_MARKERS = (
    "503", "UNAVAILABLE", "overloaded", "529",
    "429", "RESOURCE_EXHAUSTED", "500", "INTERNAL",
)


def _is_transient(exc: Exception) -> bool:
    blob = f"{type(exc).__name__} {exc}"
    return any(m in blob for m in _TRANSIENT_MARKERS)


def _with_retries(fn: Callable[[], T], attempts: int = 4, base: float = 5.0) -> T:
    """Run fn, retrying transient errors with exponential backoff (5s, 10s, 20s…)."""
    last: Exception | None = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            last = exc
            if i == attempts - 1 or not _is_transient(exc):
                raise
            delay = base * (2**i)
            log.warning(
                "transient model error (%s); retrying in %.0fs [%d/%d]",
                exc, delay, i + 1, attempts - 1,
            )
            time.sleep(delay)
    assert last is not None
    raise last


def generate(cfg: Config, system: str, user_prompt: str) -> str:
    """Dispatch to the configured provider and return raw model text."""
    if cfg.provider == "gemini":
        return _generate_gemini(cfg, system, user_prompt)
    if cfg.provider == "claude":
        return _generate_claude(cfg, system, user_prompt)
    if cfg.provider == "ollama":
        return _generate_ollama(cfg, system, user_prompt)
    raise ValueError(f"unknown provider: {cfg.provider}")


# ── Gemini ────────────────────────────────────────────────────────────────────
def _generate_gemini(cfg: Config, system: str, user_prompt: str) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=cfg.gemini_api_key)

    tools = []
    if cfg.enable_web_search:
        tools.append(types.Tool(google_search=types.GoogleSearch()))

    config = types.GenerateContentConfig(
        system_instruction=system,
        tools=tools or None,
        # Generous ceiling: must cover both thinking and the response body so the
        # digest is never truncated mid-section.
        max_output_tokens=24000,
        temperature=0.4,
    )

    resp = _with_retries(
        lambda: client.models.generate_content(
            model=cfg.model,
            contents=user_prompt,
            config=config,
        )
    )

    text = (getattr(resp, "text", None) or "").strip()
    if not text:
        # Surface why (e.g. MAX_TOKENS, SAFETY) for debugging in CI logs.
        reason = "unknown"
        try:
            reason = str(resp.candidates[0].finish_reason)
        except (AttributeError, IndexError, TypeError):
            pass
        raise RuntimeError(f"Gemini returned empty text (finish_reason={reason})")

    try:
        usage = resp.usage_metadata
        log.info(
            "gemini ok: %d chars (in=%s, out=%s tokens)",
            len(text),
            getattr(usage, "prompt_token_count", "?"),
            getattr(usage, "candidates_token_count", "?"),
        )
    except AttributeError:
        log.info("gemini ok: %d chars", len(text))
    return text


# ── Ollama (local, free — great for testing the whole pipeline) ───────────────
def _generate_ollama(cfg: Config, system: str, user_prompt: str) -> str:
    import requests

    url = cfg.ollama_host.rstrip("/") + "/api/chat"
    payload = {
        "model": cfg.model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "options": {"temperature": 0.4},
    }

    def _call() -> dict:
        try:
            r = requests.post(url, json=payload, timeout=600)
        except requests.ConnectionError as exc:
            raise RuntimeError(
                f"Cannot reach Ollama at {cfg.ollama_host}. "
                f"Start it with `ollama serve` and pull the model "
                f"(`ollama pull {cfg.model}`). ({exc})"
            ) from exc
        if r.status_code >= 300:
            raise RuntimeError(f"Ollama error {r.status_code}: {r.text[:300]}")
        return r.json()

    data = _with_retries(_call)
    text = ((data.get("message") or {}).get("content") or "").strip()
    if not text:
        raise RuntimeError("Ollama returned empty content")
    log.info("ollama ok: %d chars (model=%s)", len(text), cfg.model)
    return text


# ── Claude ────────────────────────────────────────────────────────────────────
def _generate_claude(cfg: Config, system: str, user_prompt: str) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=cfg.anthropic_api_key)

    tools = (
        [{"type": "web_search_20260209", "name": "web_search"}]
        if cfg.enable_web_search
        else []
    )
    messages = [{"role": "user", "content": user_prompt}]

    final = None
    # web_search runs server-side; a long search session returns
    # stop_reason="pause_turn" — re-send to resume.
    for _ in range(6):
        kwargs = dict(
            model=cfg.model,
            max_tokens=16000,
            system=system,
            thinking={"type": "adaptive"},
            output_config={"effort": "medium"},
            messages=messages,
        )
        if tools:
            kwargs["tools"] = tools
        resp = _with_retries(lambda: client.messages.create(**kwargs))

        if resp.stop_reason == "pause_turn":
            messages = [
                {"role": "user", "content": user_prompt},
                {"role": "assistant", "content": resp.content},
            ]
            final = resp
            continue
        final = resp
        break

    if final is None:
        raise RuntimeError("Claude returned no response")

    text = "".join(b.text for b in final.content if b.type == "text").strip()
    if not text:
        raise RuntimeError(
            f"Claude produced empty text (stop_reason={final.stop_reason})"
        )

    usage = final.usage
    log.info(
        "claude ok: %d chars (in=%s, out=%s tokens)",
        len(text),
        getattr(usage, "input_tokens", "?"),
        getattr(usage, "output_tokens", "?"),
    )
    return text
