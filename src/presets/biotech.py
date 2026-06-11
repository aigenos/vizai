"""SOURCE_PRESET=biotech — daily biotech / life-sciences briefing.

Drug discovery, genomics, synthetic biology, ML-for-bio, and industry moves.
Feeds listed here use long-stable URLs; paywalled outlets (Endpoints, STAT)
and approval trackers are web-search targets instead.
"""

from __future__ import annotations

from ..sources import Feed

RSS_FEEDS: list[Feed] = [
    # ── Journals / preprints ──────────────────────────────────────────────────
    Feed("Nature Biotechnology", "https://www.nature.com/nbt.rss", "research"),
    Feed("bioRxiv (bioinformatics)", "https://connect.biorxiv.org/biorxiv_xml.php?subject=bioinformatics", "research"),
    Feed("bioRxiv (synthetic biology)", "https://connect.biorxiv.org/biorxiv_xml.php?subject=synthetic_biology", "research"),

    # ── Industry reporting ────────────────────────────────────────────────────
    Feed("Fierce Biotech", "https://www.fiercebiotech.com/rss/xml", "newsletter"),
    Feed("ScienceDaily Biotechnology", "https://www.sciencedaily.com/rss/plants_animals/biotechnology.xml", "newsletter"),

    # ── Community ─────────────────────────────────────────────────────────────
    Feed("r/biotech (top/day)", "https://www.reddit.com/r/biotech/top/.rss?t=day", "community"),
    Feed("r/bioinformatics (top/day)", "https://www.reddit.com/r/bioinformatics/top/.rss?t=day", "community"),
    Feed("HN biotech (50+ pts)", "https://hnrss.org/newest?q=biotech+OR+genomics+OR+CRISPR+OR+%22drug+discovery%22&points=50", "community"),
]

WEB_SEARCH_TARGETS: list[str] = [
    "Endpoints News — latest biotech industry stories (endpts.com)",
    "STAT News biotech coverage — latest (statnews.com/category/biotech)",
    "FDA drug and biologic approvals and notable advisory-committee outcomes this week",
    "Genetic Engineering & Biotechnology News — latest (genengnews.com)",
    "Nature, Science, Cell — notable biology papers published in the last few days",
    "DeepMind / Isomorphic Labs and other AI-for-biology model releases (AlphaFold-class work)",
    "Protein design and structure-prediction tool releases on GitHub and Hugging Face",
    "Biotech funding rounds and IPOs in the last 7 days (Fierce Biotech, Endpoints, Crunchbase)",
    "Clinical trial readouts moving the field in the last week",
]

ARXIV_CATEGORIES: list[str] = ["q-bio.BM", "q-bio.GN", "q-bio.QM", "cs.LG"]

ARXIV_QUERIES: list[str] = [
    'abs:"protein" AND (abs:"design" OR abs:"structure prediction" OR abs:"folding")',
    'abs:"drug discovery" OR abs:"molecular generation" OR abs:"binding affinity"',
    'abs:"genomics" OR abs:"single-cell" OR abs:"gene expression"',
    'abs:"language model" AND (abs:"protein" OR abs:"DNA" OR abs:"biology")',
]
