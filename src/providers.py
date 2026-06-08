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

log = logging.getLogger("aigenos.providers")

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
        # Low temperature: this is a factual briefing — creativity here means
        # confabulated releases. Keep it grounded.
        temperature=0.2,
        # Cap thinking so it can't consume the full output budget and leave the
        # response body empty (resp.text would then return "" with STOP).
        thinking_config=types.ThinkingConfig(thinking_budget=4000),
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
        # `resp.text` is empty when the candidate has only thought parts; pull
        # text directly from non-thought parts as a fallback.
        try:
            parts = resp.candidates[0].content.parts or []
            text = "".join(
                p.text for p in parts if getattr(p, "text", None) and not getattr(p, "thought", False)
            ).strip()
        except (AttributeError, IndexError, TypeError):
            pass

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

    # Web-search citations live in grounding_metadata, NOT inline — append them as
    # a verifiable Sources section so every grounded claim is traceable.
    sources = _gemini_grounding_sources(resp)
    if sources:
        text += "\n\n" + _render_sources_section(sources)
        log.info("gemini grounding: %d web source(s) appended", len(sources))
    return text


def _gemini_grounding_sources(resp) -> list[tuple[str, str]]:
    """Extract (title, uri) web sources Gemini used to ground its answer."""
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    try:
        chunks = resp.candidates[0].grounding_metadata.grounding_chunks or []
    except (AttributeError, IndexError, TypeError):
        return out
    for ch in chunks:
        web = getattr(ch, "web", None)
        uri = getattr(web, "uri", None) if web else None
        if not uri or uri in seen:
            continue
        seen.add(uri)
        title = (getattr(web, "title", None) or uri).strip()
        out.append((title, uri))
    return out


def _render_sources_section(sources: list[tuple[str, str]]) -> str:
    """A public, non-private 'Sources' section listing web-verified references."""
    items = "\n".join(
        f'<li><a href="{uri}">{title}</a></li>' for title, uri in sources
    )
    return (
        "<!--SECTION:sources-->\n"
        "<h2>🔗 Sources — Verified via Web Search</h2>\n"
        "<p>Primary references the briefing was grounded against, for you to "
        "verify and read in depth:</p>\n"
        f"<ul>{items}</ul>"
    )


# ── Ollama (local, free — great for testing the whole pipeline) ───────────────
def _generate_ollama(cfg: Config, system: str, user_prompt: str) -> str:
    import json
    import sys
    import requests

    url = cfg.ollama_host.rstrip("/") + "/api/chat"
    payload = {
        "model": cfg.model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_prompt},
        ],
        # Stream so the user sees progress in the terminal instead of staring
        # at a frozen log line for several minutes.
        "stream": True,
        "options": {
            "temperature": 0.4,
            # Ollama defaults num_ctx to 2048 — silently truncates 90% of our
            # prompt. Set explicitly so the model sees the whole input.
            "num_ctx": 16384,
            # Cap output so a runaway generation doesn't take 20+ minutes on
            # local hardware. ~8K tokens is enough for the full 4-section brief.
            "num_predict": 8192,
        },
    }

    def _call() -> dict:
        try:
            r = requests.post(url, json=payload, timeout=600, stream=True)
        except requests.ConnectionError as exc:
            raise RuntimeError(
                f"Cannot reach Ollama at {cfg.ollama_host}. "
                f"Start it with `ollama serve` and pull the model "
                f"(`ollama pull {cfg.model}`). ({exc})"
            ) from exc
        if r.status_code >= 300:
            raise RuntimeError(f"Ollama error {r.status_code}: {r.text[:300]}")

        chunks: list[str] = []
        final_obj: dict = {}
        sys.stdout.write("\n── streaming from Ollama ──\n")
        sys.stdout.flush()
        for line in r.iter_lines(decode_unicode=True):
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            piece = (obj.get("message") or {}).get("content") or ""
            if piece:
                chunks.append(piece)
                sys.stdout.write(piece)
                sys.stdout.flush()
            if obj.get("done"):
                final_obj = obj
                break
        sys.stdout.write("\n── end stream ──\n")
        sys.stdout.flush()
        # Re-assemble into the same shape the non-streaming path returned, so
        # the caller code below doesn't care which mode was used.
        final_obj["message"] = {"content": "".join(chunks)}
        return final_obj

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
