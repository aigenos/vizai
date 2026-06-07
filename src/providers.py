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

from .config import Config

log = logging.getLogger("vizai.providers")


def generate(cfg: Config, system: str, user_prompt: str) -> str:
    """Dispatch to the configured provider and return raw model text."""
    if cfg.provider == "gemini":
        return _generate_gemini(cfg, system, user_prompt)
    if cfg.provider == "claude":
        return _generate_claude(cfg, system, user_prompt)
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
        # Cap thinking so it can't consume the full output budget and leave the
        # response body empty (resp.text would then return "" with STOP).
        thinking_config=types.ThinkingConfig(thinking_budget=4000),
    )

    resp = client.models.generate_content(
        model=cfg.model,
        contents=user_prompt,
        config=config,
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
        resp = client.messages.create(**kwargs)

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
