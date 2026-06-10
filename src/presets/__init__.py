"""Field presets: ready-made source packs for non-AI daily briefings.

Select one with the ``SOURCE_PRESET`` env var (e.g. ``SOURCE_PRESET=security``)
— no code change needed. Each preset module may define any of:

- ``RSS_FEEDS``           list[Feed]   feeds fetched deterministically
- ``WEB_SEARCH_TARGETS``  list[str]    sources the LLM backfills via web search
- ``ARXIV_CATEGORIES``    list[str]    arXiv categories to query
- ``ARXIV_QUERIES``       list[str]    arXiv abstract search terms

Names a preset omits keep the AI defaults from ``src/sources.py``. Only list a
feed here if you're confident the URL is live; anything uncertain belongs in
``WEB_SEARCH_TARGETS`` instead (the fetch layer skips broken feeds gracefully,
but dead URLs are still noise).

To add a preset: copy one of these modules, swap the sources, and run
``SOURCE_PRESET=<name> DRY_RUN=true python -m src.main`` to check feed health
in the logs.
"""

AVAILABLE = ["ai", "security", "biotech", "fintech"]
