"""Audio version of the digest — a spoken rendering of The Pulse.

Uses gTTS (Google Translate TTS): free, no API key, so a $0 clone still works.
The dependency is imported lazily and optional — if gTTS isn't installed, audio
is skipped with a warning rather than failing the run.

We voice only **The Pulse** (the standalone 90-second summary), not the whole
briefing — that's the part that works as a listen-on-your-commute artifact.
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime

from .config import Config
from .notifiers import extract_section, html_to_text

log = logging.getLogger("aigenos.audio")


def _spoken_text(body_fragment: str) -> str:
    """Turn The Pulse + Opportunity of the Day into clean prose for TTS
    (drop URLs — unspeakable)."""
    pulse = extract_section(body_fragment, "pulse")
    opp = extract_section(body_fragment, "opp_teaser")
    chunks = []
    if pulse:
        chunks.append(html_to_text(pulse, max_bullets=12))
    if opp:
        chunks.append("And here's today's opportunity of the day. " + html_to_text(opp, max_bullets=8))
    text = "\n".join(chunks)
    # Strip the "(url)" parentheticals html_to_text leaves in — links don't read
    # aloud well.
    text = re.sub(r"\s*\(https?://[^)]+\)", "", text)
    text = re.sub(r"•\s*", "", text)
    text = re.sub(r"\n{2,}", ". ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def generate(cfg: Config, body_fragment: str, now: datetime) -> str | None:
    """Write an MP3 of The Pulse to <audio_dir>. Returns path, or None if skipped."""
    text = _spoken_text(body_fragment)
    if not text:
        log.warning("audio skipped: no Pulse text to voice")
        return None

    try:
        from gtts import gTTS  # lazy: optional dependency
    except ImportError:
        log.warning("audio skipped: gTTS not installed (`pip install gTTS`)")
        return None

    os.makedirs(cfg.audio_dir, exist_ok=True)
    out_path = os.path.join(cfg.audio_dir, f"digest_{now.strftime('%Y%m%d')}.mp3")
    try:
        intro = f"Your AI daily digest for {now.strftime('%A, %B %d')}. Here's the pulse. "
        gTTS(text=intro + text, lang="en", tld="com").save(out_path)
    except Exception as exc:  # noqa: BLE001 — network/TTS errors shouldn't kill the run
        log.warning("audio generation failed: %s", exc)
        return None

    log.info("audio written → %s (%d chars voiced)", out_path, len(text))
    return out_path
