# vizai — Daily AI Intelligence Agent

An autonomous agent that, **every day**, fetches the latest from frontier AI labs,
top newsletters, and arXiv, then uses Claude to synthesize a curated briefing and
emails it to you. Built to help you **stay ahead in AI, ship better AI solutions,
and find publishable open problems in agentic AI.**

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

Labs/newsletters are pulled via RSS where available; **Claude's web-search tool
backfills** anything without a reliable feed (Anthropic, DeepSeek, newsletters that
move their feed) and verifies/augments the rest, so coverage stays robust even when
a feed breaks.

## Architecture

```
fetchers.py  ──►  analyzer.py (Claude + web_search)  ──►  emailer.py (Resend)
  RSS + arXiv        curate · learn · ideate · find gaps      styled HTML email
                                   ▲
                              sources.py (registry)
```

Everything is orchestrated by `src/main.py` and scheduled by a GitHub Actions cron
(`.github/workflows/daily-ai-digest.yml`) — no servers to run.

## Setup (one-time, ~5 minutes)

### 1. Get the two keys
- **Anthropic API key** → https://console.anthropic.com/settings/keys
- **Resend API key** → https://resend.com/api-keys (free tier covers a daily email)

> The default sender `onboarding@resend.dev` can only send to the **email of the
> Resend account owner**. Sign up for Resend with `mukeshatnyc1@gmail.com` (or
> verify a domain and set `EMAIL_FROM`) so delivery works.

### 2. Add them to GitHub
In the repo: **Settings → Secrets and variables → Actions**.

**Secrets** (required):
- `ANTHROPIC_API_KEY`
- `RESEND_API_KEY`

**Variables** (optional — defaults shown):
- `EMAIL_TO` = `mukeshatnyc1@gmail.com`
- `EMAIL_FROM` = `AI Daily Digest <onboarding@resend.dev>`
- `DIGEST_MODEL` = `claude-sonnet-4-6`
- `LOOKBACK_DAYS` = `3`
- `ENABLE_WEB_SEARCH` = `true`

### 3. Run it
- **Manually first:** Actions tab → *Daily AI Digest* → **Run workflow**. Check your inbox.
- **Automatic:** runs daily at **13:00 UTC** (~8 AM US Eastern). Change the `cron`
  in the workflow to your preferred time.

## Run locally

```bash
pip install -r requirements.txt
cp .env.example .env          # fill in ANTHROPIC_API_KEY and RESEND_API_KEY
set -a; source .env; set +a   # export the vars
python -m src.main            # builds digest, writes digest_YYYYMMDD.html, emails it
```

## Tests

```bash
python -m unittest discover -s tests
```

## Configuration reference

All knobs are environment variables; see [`.env.example`](.env.example). Notable:

- `ENABLE_WEB_SEARCH=false` — run purely from RSS + arXiv (cheaper, narrower coverage).
- `DIGEST_MODEL=claude-opus-4-8` — switch to Opus for deeper analysis (higher cost).
- `LOOKBACK_DAYS` — how many days count as "latest" (3 covers weekends).

## Cost

Roughly a few cents to a few tens of cents per day on Sonnet 4.6 with web search,
depending on how much the model searches. Resend's free tier covers the email.

## Customizing sources

Edit `src/sources.py`:
- `RSS_FEEDS` — add/remove feeds (name, url, category).
- `WEB_SEARCH_TARGETS` — plain-language sources for Claude to search/verify.
- `ARXIV_CATEGORIES` / `ARXIV_QUERIES` — tune the research net.
