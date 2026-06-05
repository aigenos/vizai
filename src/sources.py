"""Source registry.

Two kinds of sources:

1. RSS/Atom feeds we fetch deterministically (structured, dated entries).
2. "Web targets" we don't have a reliable feed for — these are handed to Claude's
   web_search tool so it can pull the latest items itself (newsletters, DeepSeek,
   and any lab whose feed is flaky).

RSS URLs change over time; a broken feed is skipped gracefully at fetch time and
the web-search layer is expected to backfill the gap.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Feed:
    name: str
    url: str
    category: str  # "lab" | "newsletter" | "research"


# Best-effort RSS/Atom feeds. Order roughly by signal.
RSS_FEEDS: list[Feed] = [
    # ── Frontier labs / tech giants ──────────────────────────────────────────
    Feed("OpenAI", "https://openai.com/news/rss.xml", "lab"),
    Feed("Google DeepMind", "https://deepmind.google/blog/rss.xml", "lab"),
    Feed("Google AI (The Keyword)", "https://blog.google/technology/ai/rss/", "lab"),
    Feed("Microsoft Research", "https://www.microsoft.com/en-us/research/feed/", "lab"),
    Feed("Microsoft AI Blog", "https://blogs.microsoft.com/ai/feed/", "lab"),
    Feed("Meta AI", "https://ai.meta.com/blog/rss/", "lab"),
    Feed("Hugging Face", "https://huggingface.co/blog/feed.xml", "lab"),
    # ── Newsletters (beehiiv feeds; backfilled by web search if they move) ────
    Feed("The Rundown AI", "https://rss.beehiiv.com/feeds/2R3C6Bt5wj.xml", "newsletter"),
    Feed("The Neuron", "https://rss.beehiiv.com/feeds/PVwQjvkw0z.xml", "newsletter"),
]

# Sources Claude should actively search/verify the web for. Plain-language so the
# model can reason about them. Used only when ENABLE_WEB_SEARCH is true.
WEB_SEARCH_TARGETS: list[str] = [
    "Anthropic news and research announcements (anthropic.com/news, anthropic.com/research)",
    "OpenAI announcements and research (openai.com/news, openai.com/research)",
    "Google DeepMind and Google AI announcements",
    "Microsoft AI / Microsoft Research announcements",
    "Meta AI (FAIR) announcements and model releases",
    "DeepSeek releases and papers (DeepSeek-AI on GitHub and Hugging Face)",
    "The Neuron newsletter (theneurondaily.com) latest issue",
    "The Rundown AI newsletter (therundown.ai) latest issue",
]

# arXiv: categories + agentic-AI focused search terms.
ARXIV_CATEGORIES: list[str] = ["cs.AI", "cs.LG", "cs.CL", "cs.MA"]

ARXIV_QUERIES: list[str] = [
    'abs:"LLM agent" OR abs:"language model agent" OR abs:"agentic"',
    'abs:"multi-agent" AND (abs:"LLM" OR abs:"language model")',
    'abs:"tool use" AND abs:"language model"',
    'abs:"agent memory" OR abs:"long-horizon" OR abs:"planning" AND abs:"agent"',
]
