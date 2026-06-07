# vizai — Daily AI Intelligence Agent

An autonomous agent that, **every day**, fetches the latest from frontier AI labs,
top newsletters, and arXiv, then uses an LLM (**Gemini or Claude — your choice**)
to synthesize a curated briefing and emails it to you. Built to help you **stay
ahead in AI, ship better AI solutions, and find publishable open problems in
agentic AI.**

Each digest contains five sections:

1. **🔭 Top Stories — What Actually Matters Today** — curated, deduped, ranked, each with *why it matters*.
2. **🧠 Key Learnings & Your Next Steps** — what the day's signal means + concrete actions to take this week.
3. **🚀 OSS & Product Opportunity Ideas** — buildable ideas riding current trends.
4. **🔬 Open Problems in Agentic AI** — unsolved/under-explored research problems worth working on or publishing, with a suggested angle.
5. **📑 arXiv Picks** — the most relevant recent papers.

## Sources

| Type | Covered |
|------|---------|
| Frontier labs / tech giants | Google (DeepMind + AI blog), Microsoft (Research + AI), OpenAI, Anthropic, Meta AI, DeepSeek, Hugging Face |
| Newsletters | The Neuron, The Rundown AI |
| Research | arXiv (`cs.AI`, `cs.LG`, `cs.CL`, `cs.MA`) — agentic-AI focused queries |

Labs/newsletters are pulled via RSS where available; the LLM's **web grounding**
(Gemini → Google Search, Claude → web_search tool) backfills anything without a
reliable feed (Anthropic, DeepSeek, newsletters that move their feed) and
verifies/augments the rest, so coverage stays robust even when a feed breaks.

## Provider (Gemini or Claude)

Analysis is pluggable via the `PROVIDER` env var — no code change to switch:

| `PROVIDER` | Default model | Web grounding | Key needed |
|------------|---------------|---------------|------------|
| `gemini` (default) | `gemini-2.5-flash` | Google Search | `GEMINI_API_KEY` |
| `claude` | `claude-sonnet-4-6` | web_search tool | `ANTHROPIC_API_KEY` |

Override the model anytime with `DIGEST_MODEL` (e.g. `gemini-2.5-pro`,
`claude-opus-4-8`). Only the selected provider's key is required.

## Architecture

```
fetchers.py  ──►  analyzer.py  ──►  providers.py  ──►  emailer.py (Resend)
  RSS + arXiv     build prompt     gemini | claude       styled HTML email
                       ▲           (+ web grounding)
                  sources.py (registry)
```

Everything is orchestrated by `src/main.py` and scheduled by a GitHub Actions cron
(`.github/workflows/daily-ai-digest.yml`) — no servers to run.

## Setup (one-time, ~5 minutes)

### 1. Get the two keys
- **Gemini API key** → https://aistudio.google.com/apikey (default provider; free tier covers a daily run)
  _(or, if `PROVIDER=claude`, an **Anthropic key** → https://console.anthropic.com/settings/keys)_
- **Resend API key** → https://resend.com/api-keys (free tier covers a daily email)

> The default sender `onboarding@resend.dev` can only send to the **email of the
> Resend account owner**. Sign up for Resend with `mukeshatnyc1@gmail.com` (or
> verify a domain and set `EMAIL_FROM`) so delivery works.

### 2. Add them to GitHub
In the repo: **Settings → Secrets and variables → Actions**.

**Secrets** (add the one for your provider + Resend):
- `GEMINI_API_KEY`  *(default provider)*
- `ANTHROPIC_API_KEY`  *(only if `PROVIDER=claude`)*
- `RESEND_API_KEY`

**Variables** (optional — defaults shown):
- `PROVIDER` = `gemini`  *(or `claude`)*
- `EMAIL_TO` = `mukeshatnyc1@gmail.com`
- `EMAIL_FROM` = `AI Daily Digest <onboarding@resend.dev>`
- `DIGEST_MODEL` = *(blank → provider default; e.g. `gemini-2.5-pro`)*
- `LOOKBACK_DAYS` = `3`
- `ENABLE_WEB_SEARCH` = `true`

### 3. Run it
- **Manually first:** Actions tab → *Daily AI Digest* → **Run workflow**. Check your inbox.
- **Automatic:** runs daily at **13:00 UTC** (~8 AM US Eastern). Change the `cron`
  in the workflow to your preferred time.

## Run locally

```bash
pip install -r requirements.txt
cp .env.example .env          # fill in GEMINI_API_KEY (or ANTHROPIC_API_KEY) + RESEND_API_KEY
set -a; source .env; set +a   # export the vars
python -m src.main            # builds digest, writes digest_YYYYMMDD.html, emails it
```

### Test the whole pipeline for free (no tokens, no email)

Use the local **Ollama** provider + **DRY_RUN** to exercise fetch → synthesize →
render end-to-end without spending API tokens or sending anything:

```bash
# one-time: install ollama (https://ollama.com), then
ollama serve &
ollama pull llama3.1            # or qwen2.5, llama3.2, etc.

PROVIDER=ollama DRY_RUN=true python -m src.main
# → writes digest_YYYYMMDD.html locally; skips Resend entirely. Open it in a browser.
```

When that looks right, switch back to `PROVIDER=gemini` (drop `DRY_RUN`) for the
real run. You can also dry-run Gemini/Claude (`DRY_RUN=true` alone) to verify the
model output without sending email.

> **Resilience:** transient `503 / 429 / overloaded` errors (e.g. Gemini "high
> demand") are retried automatically with exponential backoff (5s → 10s → 20s)
> before failing, so brief capacity spikes don't kill a run.

## Tests

```bash
python -m unittest discover -s tests
```

## Configuration reference

All knobs are environment variables; see [`.env.example`](.env.example). Notable:

- `PROVIDER=gemini|claude` — pick the analysis engine.
- `DIGEST_MODEL` — override the model (e.g. `gemini-2.5-pro`, `claude-opus-4-8`).
- `ENABLE_WEB_SEARCH=false` — run purely from RSS + arXiv (cheaper, narrower coverage).
- `LOOKBACK_DAYS` — how many days count as "latest" (3 covers weekends).

## Cost

On the default **Gemini 2.5 Flash**, a daily run typically fits within Google's
free tier (or costs a few cents). Claude Sonnet 4.6 with web search runs a few
cents to a few tens of cents per day. Resend's free tier covers the email.

## Customizing sources

Edit `src/sources.py`:
- `RSS_FEEDS` — add/remove feeds (name, url, category).
- `WEB_SEARCH_TARGETS` — plain-language sources for Claude to search/verify.
- `ARXIV_CATEGORIES` / `ARXIV_QUERIES` — tune the research net.
