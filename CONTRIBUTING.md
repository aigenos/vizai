# Contributing to dAIly

Thanks for helping make the daily briefing better. The three highest-impact
contributions, in order: **new field presets**, **new sources**, and **fixes
with tests**.

## Run it for free first

You can exercise the entire pipeline with zero API keys and zero emails:

```bash
pip install -r requirements.txt
ollama serve &                     # https://ollama.com — local, free
ollama pull qwen2.5:14b
PROVIDER=ollama DRY_RUN=true python -m src.main
# → writes digest_YYYYMMDD.html; open it in a browser.
```

`DRY_RUN=true` skips Resend, so `RESEND_API_KEY` isn't needed.

## Add a source (to the default AI preset)

Edit [`src/sources.py`](src/sources.py):

1. **Has a working RSS/Atom feed?** Add a `Feed(name, url, category)` to
   `RSS_FEEDS`. Categories: `lab`, `newsletter`, `infra`, `community`,
   `research`. **Verify the URL returns HTTP 200 first** — uncertain or
   feed-less sources belong in `WEB_SEARCH_TARGETS` instead (a plain-language
   line the LLM uses for web grounding).
2. Run `DRY_RUN=true python -m src.main` and check the log line for your feed
   (`feed <name>: N recent item(s)`).

## Add a field preset

One file makes dAIly a daily analyst for a whole new field:

1. Copy [`src/presets/security.py`](src/presets/security.py) to
   `src/presets/<yourfield>.py`.
2. Define any of `RSS_FEEDS`, `WEB_SEARCH_TARGETS`, `ARXIV_CATEGORIES`,
   `ARXIV_QUERIES` — names you omit keep the AI defaults. Same rule as above:
   only confident, verified feed URLs in `RSS_FEEDS`.
3. Add the preset name to `AVAILABLE` in `src/presets/__init__.py`.
4. Test: `SOURCE_PRESET=<yourfield> PROVIDER=ollama DRY_RUN=true python -m src.main`
5. Mention the preset in the README's preset list.

## Run the tests

```bash
pip install -r requirements-dev.txt
python -m pytest -q tests/
```

No test may touch the network or require an API key. If you add behavior, add a
test; the suite is fast on purpose.

## House rules for code

- Python only; keep runtime dependencies minimal (heavy/dev-only tools go in
  `requirements-dev.txt`).
- **Fail-open**: a broken feed, dead state file, or network hiccup must never
  kill the daily run. Log a warning and continue.
- Every behavior knob is an environment variable with a sensible default —
  follow the style in `src/config.py` and document it in `.env.example`.
- Match the existing code style (logging via module loggers, type hints,
  section-comment headers).

## Pull requests

- One logical change per PR, with a clear message.
- Run the test suite before pushing.
- For new sources/presets, paste the relevant `DRY_RUN` log lines in the PR
  description so reviewers can see the feeds are healthy.
