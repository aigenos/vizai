"""Synthesis layer: turn raw fetched items into a curated digest.

Builds the (provider-agnostic) prompt, then delegates generation to the configured
provider (Gemini or Claude) which grounds itself with web search to (a) curate and
deduplicate the day's signal, (b) extract learnings + next steps, (c) propose
OSS/product ideas, and (d) surface open problems in agentic AI worth publishing on.

The model returns a self-contained HTML body fragment which the emailer wraps in a
styled template.
"""

from __future__ import annotations

import logging
from datetime import datetime

from . import providers
from .config import Config
from .fetchers import Item
from .sources import WEB_SEARCH_TARGETS

log = logging.getLogger("vizai.analyzer")

SYSTEM_PROMPT = """\
You are an elite AI research & industry analyst writing a daily intelligence \
briefing for a senior AI engineer who is building AI solutions and wants to (1) \
stay ahead of the field, (2) excel at shipping AI products, and (3) find \
publishable open problems in the agentic-AI space.

Your reader is technical. Be specific, concrete, and signal-dense. No hype, no \
filler, no "in today's fast-moving world" preambles. Prefer substance over volume.

You are given a set of candidate items fetched from frontier labs (Google, \
Microsoft, OpenAI, Anthropic, Meta, DeepSeek), top newsletters (The Neuron, The \
Rundown AI), and recent arXiv papers. Some sources may be missing or stale — use \
web search to verify, fill gaps, and pull anything genuinely important from the \
last few days that the candidate list missed. Cross-check claims; do not invent \
releases that did not happen. Every factual claim about a release/paper must \
correspond to a real, linkable source.

Curate ruthlessly. Deduplicate. Rank by importance to the reader's goals."""

INSTRUCTIONS = """\
Produce the briefing as a single self-contained HTML fragment (no <html>, <head>, \
or <body> tags — just the inner content). Use ONLY these tags: <h2>, <h3>, <p>, \
<ul>, <li>, <a>, <strong>, <em>, <blockquote>. Every external reference must be a \
real <a href="..."> link to the primary source.

Structure it as exactly these five sections, each opened with an <h2>:

<h2>🔭 Top Stories — What Actually Matters Today</h2>
The 5–8 most important developments. For each: an <h3> headline, then a short <p>
covering WHAT happened and — in <strong>Why it matters:</strong> — the concrete
implication for someone building AI solutions. Link the primary source.

<h2>🧠 Key Learnings &amp; Your Next Steps</h2>
A tight synthesis: what today's signal collectively means, and a <ul> of 4–6
specific, actionable next steps the reader can take this week to stay ahead and
level up their AI engineering (skills to pick up, tools/models to try, patterns
to adopt). Be concrete (name the model/library/technique).

<h2>🚀 OSS &amp; Product Opportunity Ideas</h2>
3–5 ideas for open-source projects or products inspired by today's developments
or visible gaps. For each: an <h3> name, a one-line pitch, who it's for, and why
now. Favor ideas that are buildable by a small team and ride a current trend.

<h2>🔬 Open Problems in Agentic AI — Worth Working On / Publishing</h2>
3–5 unsolved or under-explored research problems in the agentic-AI space (e.g.
long-horizon planning, memory, multi-agent coordination, tool-use reliability,
evaluation, credit assignment, self-correction). For each: an <h3> problem
statement, a <p> on why it's open and hard, and a <strong>Possible angle:</strong>
suggesting a tractable research direction or experiment. Ground these in the
recent arXiv papers where possible and link them.

<h2>📑 arXiv Picks</h2>
A <ul> of the 5–8 most relevant recent papers. Each <li>: linked title, authors
(or "et al."), and one sentence on the contribution and why it's worth reading.

End with a short <p><em>…</em></p> one-line sign-off. Output ONLY the HTML
fragment — no markdown code fences, no commentary before or after."""


def _format_items(items: list[Item]) -> str:
    by_cat: dict[str, list[Item]] = {"lab": [], "newsletter": [], "research": []}
    for it in items:
        by_cat.setdefault(it.category, []).append(it)

    labels = {
        "lab": "FRONTIER LABS / TECH GIANTS",
        "newsletter": "NEWSLETTERS",
        "research": "arXiv RESEARCH PAPERS",
    }
    blocks: list[str] = []
    for cat in ("lab", "newsletter", "research"):
        group = by_cat.get(cat) or []
        if not group:
            continue
        lines = [f"### {labels[cat]} ({len(group)})"]
        for it in group:
            date = it.published.strftime("%Y-%m-%d") if it.published else "n/a"
            authors = f" — {', '.join(it.authors[:4])}" if it.authors else ""
            lines.append(
                f"- [{it.source} | {date}] {it.title}{authors}\n"
                f"  {it.url}\n"
                f"  {it.summary[:500]}"
            )
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) if blocks else "(no items fetched deterministically)"


def build_digest(cfg: Config, items: list[Item], now: datetime) -> str:
    """Build the prompt, run the configured provider, return the HTML fragment."""
    targets = "\n".join(f"- {t}" for t in WEB_SEARCH_TARGETS)
    user_content = (
        f"Date: {now.strftime('%A, %B %d, %Y')} (UTC).\n"
        f"Consider developments from roughly the last {cfg.lookback_days} days.\n\n"
        f"CANDIDATE ITEMS (fetched from RSS + arXiv):\n\n"
        f"{_format_items(items)}\n\n"
        f"SOURCES TO VERIFY / BACKFILL VIA WEB SEARCH (pull anything important "
        f"these published recently that's missing above):\n{targets}\n\n"
        f"{INSTRUCTIONS}"
    )

    log.info("generating digest via %s (%s)", cfg.provider, cfg.model)
    raw = providers.generate(cfg, SYSTEM_PROMPT, user_content)
    html = _strip_code_fence(raw)
    if not html:
        raise RuntimeError("provider produced an empty digest")
    log.info("digest generated: %d chars", len(html))
    return html


def _strip_code_fence(text: str) -> str:
    """Remove a leading/trailing ```html fence if the model added one."""
    t = text.strip()
    if t.startswith("```"):
        first_nl = t.find("\n")
        if first_nl != -1:
            t = t[first_nl + 1 :]
        if t.rstrip().endswith("```"):
            t = t.rstrip()[: -3]
    return t.strip()
