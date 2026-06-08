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
import re
from datetime import datetime

from . import providers
from .config import Config
from .fetchers import Item
from .sources import WEB_SEARCH_TARGETS

log = logging.getLogger("aigenos.analyzer")

SYSTEM_PROMPT = """\
You are an elite AI industry + research analyst writing a daily intelligence \
briefing for a senior AI engineer whose goals are: (1) stay at the cutting edge \
of the AI stack so it directly improves day-to-day AI work, (2) spot missing \
pieces in the ecosystem, and (3) turn those gaps into a viral, revenue-generating \
product, framework, OSS project, startup, or publishable paper. The reader wants \
to build something new — not just consume news.

DESIGN PRINCIPLE — INFORMATION PYRAMID. The briefing is structured so a reader \
with 90 seconds gets everything essential; a reader with 10 minutes gets depth. \
The TOP section must stand alone: if the reader stops there, they should still \
have the full day's signal. No section should bury its thesis.

VOICE. Technical, specific, signal-dense. Name models, libraries, benchmarks, \
numbers, paper IDs, repo names, round sizes. No hype, no filler, no "in today's \
fast-moving world" preambles. Use bullets over prose wherever possible. Short \
sentences. Active voice. Bold the headline of each bullet so the reader can \
skim. No paragraph longer than 3 sentences.

SOURCES. You are given candidate items fetched from frontier labs, AI-engineer \
newsletters, infra/tooling vendors, community feeds (Reddit, HN), and recent \
arXiv papers. Some sources may be missing or stale — use web search to verify, \
fill gaps, and pull anything important from the last few days that the candidate \
list missed (especially trending GitHub repos, Hugging Face models, eval \
leaderboard moves, AI funding rounds, and YC / Show HN / Product Hunt launches). \
Cross-check claims; do not invent releases. Every factual claim must correspond \
to a real, linkable primary source.

CITATIONS — NON-NEGOTIABLE. Every single factual claim, story, paper, release, \
benchmark number, funding round, or opportunity proof-point MUST be followed by a \
real <a href="..."> link to its primary source. No orphan claims. When an item \
comes from the candidate list below, use its EXACT url — do not paraphrase or \
guess the link. When you pull something via web search, link the canonical \
primary source (the lab's own post, the arXiv abstract, the official repo), not \
an aggregator. If you cannot find a source for a claim, DROP the claim. A bullet \
without a link is a bug. The reader uses these links to verify truth.

Curate ruthlessly. Deduplicate. Rank by importance to the reader's goals — \
prioritize signal that either (a) changes how the reader should build AI today, \
or (b) reveals a gap that a small team could exploit."""

# ── Briefing sections ─────────────────────────────────────────────────────────
# Each section is (id, order, instructions). Public sections live here. Private
# sections (e.g. the Opportunity Map — the "secret sauce") are loaded at runtime
# from the gitignored src/private/ package, so they never appear in the public
# repo and a public clone simply omits them. See src/private/README.md.
#
# Every section instructs the model to emit an HTML-comment marker
# (<!--SECTION:id-->) right before its <h2>. Markers are invisible in email but
# let the archive layer strip private sections before publishing publicly.

_INSTRUCTIONS_HEADER = """\
Produce the briefing as a single self-contained HTML fragment (no <html>, <head>, \
or <body> tags — just the inner content). Use ONLY these tags: <h2>, <h3>, <p>, \
<ul>, <li>, <a>, <strong>, <em>, <blockquote>, plus HTML comments. Every external \
reference must be a real <a href="..."> link to the primary source.

Structure it as EXACTLY these {n} sections, in the order given below. Immediately \
before each section's <h2>, output that section's HTML-comment marker (shown at \
the top of the section, e.g. <!--SECTION:pulse-->) on its own line — these are \
invisible in email and let tooling identify sections. Each <h2> must end with its \
read-time budget in parentheses. Do not add, drop, reorder, or rename sections, \
and do not emit any section not listed below.

TRUTHFULNESS — READ TWICE. Only report a development if it is (a) present in the \
candidate list below, or (b) something you verified THIS run via web search. Do \
NOT report rumors, leaks, "alleged" items, or "unconfirmed" reports. Do NOT \
invent model names, version numbers, funding amounts, benchmark scores, or \
release dates. If you are not certain an item is real and recent, OMIT it. \
Fabricating a plausible-sounding item is the single worst failure — a shorter, \
fully-true briefing beats a longer one with one made-up item.

LINKS — every claim is clickable. Each item you mention must be wrapped in or \
followed by a real <a href="..."> to its primary source. For candidate items, \
use the URL printed under that item VERBATIM. Example of the required style:
  <li><strong><a href="https://arxiv.org/abs/2606.07454">Code2LoRA</a></strong> \
— hypernetwork-generated LoRA adapters for code models.</li>
A claim with no link will be treated as unverified and is a defect."""

_INSTRUCTIONS_FOOTER = """\
End with a one-line <p><em>…</em></p> sign-off. Output ONLY the HTML fragment. \
No markdown code fences, no commentary before or after."""

_SECTION_PULSE = ("pulse", 10, """\
<!--SECTION:pulse-->
<h2>⚡ The Pulse — If You Only Read One Thing (90 sec read)</h2>
This section MUST stand alone. A reader who stops here should still have the
full day's signal. Two sub-blocks:

<h3>🎯 Today's Game-Changer</h3>
The single most important development from the last 24–72 hours — pick ONE. A
2–3 sentence <p>: what happened (with the primary <a> link, named model / repo /
number), then one tight clause on why it matters more than anything else today.
If nothing is truly game-changing, say so honestly and elevate the most
consequential item instead — do not manufacture drama.

<h3>📍 In a Nutshell</h3>
A <ul> of 8–12 ultra-tight one-line bullets covering everything else important
today: model releases, infra changes, funding, eval leaderboard moves, big
papers, ecosystem shifts, notable launches. Pattern per bullet:
<strong>X shipped Y</strong> — one-clause why-it-matters. <a>source</a>
Skim-readable in under a minute. Cluster related bullets next to each other.
Zero filler. If it doesn't change a builder's decisions or signal a gap, cut it.""")

_SECTION_OPP_TEASER = ("opp_teaser", 20, """\
<!--SECTION:opp_teaser-->
<h2>🚀 Opportunity of the Day (2 min read)</h2>
Pick THE single most compelling thing to build from today's signal — the one bet
with the clearest path to BOTH viral adoption and revenue. Present just this one,
in full. An <h3> with a punchy product/project name (not a description), then a
<ul> with these EXACT bolded labels in order:
<ul>
<li><strong>The gap:</strong> what's missing or broken in the current AI stack
(cite the specific news/paper above that exposes it).</li>
<li><strong>Why now:</strong> what changed in the last few days that makes this
newly tractable (a new model, API, benchmark, price drop, or capability shift).</li>
<li><strong>Build as:</strong> pick one — arXiv paper / OSS library / dev tool /
SaaS product / vertical app / startup — and say why that shape fits.</li>
<li><strong>Wedge &amp; moat:</strong> the first user, the first dollar, and what
compounds over time.</li>
<li><strong>Already heating up:</strong> 2–3 concrete, linked proof points of real
early demand (HN thread, repo with star velocity, recent funding, Show HN). If
none, mark <em>(speculative — no validation signal yet)</em> honestly.</li>
<li><strong>First step this week:</strong> one concrete action to validate or
prototype it in the next 7 days.</li>
</ul>
Make this the strongest, most shareable pick — it is the public teaser for the
full Opportunity Map.""")

_SECTION_STACK = ("stack", 30, """\
<!--SECTION:stack-->
<h2>📊 Stack Signals — Pick Your Tools (3 min read)</h2>
Three skim-friendly sub-blocks under <h3> headers. Bullets, not prose.

<h3>Benchmarks &amp; Evals</h3>
What moved on LMSYS Arena, SWE-bench, GAIA, τ-bench, HumanEval, MMLU-Pro,
LiveCodeBench, MTEB, or any other live leaderboard in the last few days. Note
any NEW benchmark released — those signal what the next race is about. Each
bullet: who moved, by how much, link to source. If nothing material moved, say
"no notable leaderboard moves" — do not pad.

<h3>Repo &amp; Model Velocity</h3>
A <ul> of the 5–8 fastest-rising AI-related GitHub repos (last 24–72h) plus
trending Hugging Face models / Spaces. Each bullet: linked name, one clause on
what it does, one clause on why dev mindshare is shifting there (problem it
solves, who's adopting it).

<h3>Funding &amp; Launches — with Thesis</h3>
AI rounds announced in the last few days plus notable Show HN / Product Hunt /
YC batch AI launches. For each bullet: company (linked), round size + stage (or
"Show HN" / "PH #1"), and crucially a <strong>Thesis:</strong> one-line
extraction of WHAT BET this round/launch is buying (e.g. "vertical agent for
healthcare RCM", "open-weight reasoning model for sub-$1/M tokens"). Skip any
item with no clear thesis.""")

_SECTION_DEEP = ("deep", 40, """\
<!--SECTION:deep-->
<h2>🔬 Deep Reads — For When You Have Time (skip if rushed)</h2>
Two sub-blocks for readers who want depth. Everything above already gave them
the signal — this section is the depth layer.

<h3>📖 The One Deep Read</h3>
Pick the single most important paper or essay from the last few days and tell
the reader to ACTUALLY read it end-to-end. <h3> already provided — follow it
with a <p>: linked title + authors, 2–3 sentences explaining why this is THE
piece to read this week (what it changes, why it's worth a full hour), and a
<strong>Read it for:</strong> one-line takeaway preview.

<h3>📑 Supporting Research</h3>
A <ul> of 5–8 other recent arXiv papers / lab research posts worth knowing
about. Each <li>: linked title, authors (or "et al."), one sentence on the
contribution and result. Terse — this is a scanning list.""")

# Public sections, in display order. Private sections slot in by their `order`.
# The Opportunity-of-the-Day teaser is PUBLIC (it ships in the archive as the
# viral hook); the full Opportunity Map is private (loaded from src/private/).
_PUBLIC_SECTIONS: list[tuple[str, int, str]] = [
    _SECTION_PULSE,
    _SECTION_OPP_TEASER,
    _SECTION_STACK,
    _SECTION_DEEP,
]


def _load_private_sections() -> list[tuple[str, int, str]]:
    """Load optional private section blocks from the gitignored src/private/.

    The Opportunity Map lives there. A public clone has no such module, so this
    returns [] and the briefing is produced without it — the secret never ships.
    """
    out: list[tuple[str, int, str]] = []
    try:
        from .private import opportunity  # type: ignore
        out.append((opportunity.SECTION_ID, opportunity.ORDER, opportunity.INSTRUCTIONS))
    except Exception as exc:  # noqa: BLE001 — absence is the normal public case
        log.debug("no private sections loaded (%s)", exc)
    return out


def private_section_ids() -> list[str]:
    """Section ids that must be stripped before publishing publicly."""
    return [sid for sid, _, _ in _load_private_sections()]


def build_instructions() -> str:
    """Compose the full instruction block from public + private sections."""
    sections = sorted(_PUBLIC_SECTIONS + _load_private_sections(), key=lambda s: s[1])
    body = "\n\n".join(block for _, _, block in sections)
    return (
        _INSTRUCTIONS_HEADER.format(n=len(sections))
        + "\n\n" + body
        + "\n\n" + _INSTRUCTIONS_FOOTER
    )


# Per-source caps keep one chatty feed from dominating the prompt. Tuned so
# the full briefing fits ~10K input tokens with all feeds healthy.
_PER_SOURCE_CAP = {
    "lab": 3,
    "newsletter": 2,
    "infra": 2,
    "community": 4,
    "research": 5,
}
# Global ceiling on items handed to the model — keeps the prompt bounded even
# if every feed comes back full.
_TOTAL_ITEM_CAP = 80


def _select_for_prompt(items: list[Item]) -> list[Item]:
    """Rank + cap items so the prompt is signal-dense, not exhaustive.

    Strategy: rank (HF papers by community upvotes, everything else by recency),
    keep the top N per source, then truncate to a global cap. The fetch layer
    stays exhaustive; selection happens here.
    """
    from .fetchers import _hf_upvotes

    def rank_key(it: Item) -> float:
        # HF Daily Papers carry an upvote signal — let "must-read" beat "newest".
        # Each upvote is worth ~half a day of recency so a highly-upvoted paper
        # from yesterday outranks a zero-vote one from today.
        ts = it.published.timestamp() if it.published else 0.0
        upvote_boost = _hf_upvotes(it) * 43200 if it.source == "HF Daily Papers" else 0
        return -(ts + upvote_boost)

    ordered = sorted(items, key=rank_key)
    per_source: dict[str, int] = {}
    selected: list[Item] = []
    for it in ordered:
        cap = _PER_SOURCE_CAP.get(it.category, 3)
        seen = per_source.get(it.source, 0)
        if seen >= cap:
            continue
        per_source[it.source] = seen + 1
        selected.append(it)
        if len(selected) >= _TOTAL_ITEM_CAP:
            break
    return selected


def _format_items(items: list[Item]) -> str:
    by_cat: dict[str, list[Item]] = {
        "lab": [], "newsletter": [], "infra": [], "community": [], "research": [],
    }
    for it in items:
        by_cat.setdefault(it.category, []).append(it)

    labels = {
        "lab": "FRONTIER LABS / TECH GIANTS",
        "newsletter": "NEWSLETTERS (AI engineer + research focused)",
        "infra": "AI INFRA / TOOLING VENDORS",
        "community": "COMMUNITY (Reddit / HN — where releases break first)",
        "research": "RESEARCH PAPERS (arXiv + HF Daily Papers; ▲ = community upvotes = must-read signal)",
    }
    blocks: list[str] = []
    for cat in ("lab", "newsletter", "infra", "community", "research"):
        group = by_cat.get(cat) or []
        if not group:
            continue
        lines = [f"### {labels[cat]} ({len(group)})"]
        for it in group:
            date = it.published.strftime("%Y-%m-%d") if it.published else "n/a"
            authors = f" — {', '.join(it.authors[:2])}" if it.authors else ""
            lines.append(
                f"- [{it.source} | {date}] {it.title}{authors}\n"
                f"  {it.url}\n"
                f"  {it.summary[:240]}"
            )
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) if blocks else "(no items fetched deterministically)"


def build_digest(cfg: Config, items: list[Item], now: datetime) -> str:
    """Build the prompt, run the configured provider, return the HTML fragment."""
    selected = _select_for_prompt(items)
    log.info(
        "selected %d/%d items for prompt (per-source + global cap)",
        len(selected), len(items),
    )
    targets = "\n".join(f"- {t}" for t in WEB_SEARCH_TARGETS)
    user_content = (
        f"Date: {now.strftime('%A, %B %d, %Y')} (UTC).\n"
        f"Consider developments from roughly the last {cfg.lookback_days} days.\n\n"
        f"CANDIDATE ITEMS (fetched from RSS + arXiv — pre-ranked by recency, "
        f"capped per source):\n\n"
        f"{_format_items(selected)}\n\n"
        f"SOURCES TO VERIFY / BACKFILL VIA WEB SEARCH (pull anything important "
        f"these published recently that's missing above):\n{targets}\n\n"
        f"{build_instructions()}"
    )
    log.info(
        "prompt size: ~%d chars (~%d tokens est.)",
        len(user_content), len(user_content) // 4,
    )

    log.info("generating digest via %s (%s)", cfg.provider, cfg.model)
    raw = providers.generate(cfg, SYSTEM_PROMPT, user_content)
    html = _strip_code_fence(raw)
    if not html:
        raise RuntimeError("provider produced an empty digest")

    # Guarantee clickable sources: the model is unreliable about emitting <a>
    # links, so deterministically hyperlink any fetched item it names back to the
    # item's real URL. This makes every candidate-sourced claim verifiable.
    html, added = _backfill_links(html, selected)
    log.info("digest generated: %d chars (+%d source links backfilled)", len(html), added)
    return html


# Distinctive low-value tokens we won't treat as a linkable "phrase" on their own.
_GENERIC_TITLE_WORDS = {
    "the", "a", "an", "and", "or", "for", "with", "to", "of", "in", "on",
    "ai", "llm", "llms", "model", "models", "new", "paper", "study", "report",
}


def _backfill_links(html: str, items: list[Item]) -> tuple[str, int]:
    """Hyperlink the first unlinked mention of each fetched item's title (or its
    pre-colon head) to the item's URL — without touching existing <a> elements or
    tag internals. Returns (html, links_added)."""
    pairs: list[tuple[str, str]] = []
    for it in items:
        title = (it.title or "").strip()
        if not it.url or len(title) < 6:
            continue
        pairs.append((title, it.url))
        head = title.split(":")[0].strip()
        # Only use the head if it's specific enough (multi-word or a distinctive
        # single token like "Code2LoRA" / "MemDreamer").
        if 6 <= len(head) < len(title):
            if " " in head or head.lower() not in _GENERIC_TITLE_WORDS:
                pairs.append((head, it.url))
    # Prefer the most specific (longest) phrases first.
    pairs.sort(key=lambda p: len(p[0]), reverse=True)

    # URLs already present in the output need no backfill.
    linked: set[str] = {u for _, u in pairs if u in html}

    # Tokenise into tags vs text so we never edit inside a tag or an <a> element.
    parts = re.split(r"(<[^>]+>)", html)
    inside_a = 0
    added = 0
    for i, tok in enumerate(parts):
        if tok.startswith("<") and tok.endswith(">"):
            low = tok.lower()
            if low.startswith("<a") and not low.startswith("<area"):
                inside_a += 1
            elif low.startswith("</a"):
                inside_a = max(0, inside_a - 1)
            continue
        if inside_a or not tok:
            continue
        seg = tok
        for phrase, url in pairs:
            if url in linked:
                continue
            idx = seg.find(phrase)
            if idx == -1:
                continue
            seg = f'{seg[:idx]}<a href="{url}">{phrase}</a>{seg[idx + len(phrase):]}'
            linked.add(url)
            added += 1
        parts[i] = seg
    return "".join(parts), added


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
