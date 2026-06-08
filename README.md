# dAIly — by aigenos

> Daily AI Intelligence Agent — stay at the cutting edge of AI in 90 seconds a day.

An autonomous agent that **every day** fetches the latest from frontier AI labs,
AI-engineer newsletters, infra vendors, community feeds (Reddit/HN), arXiv, and
**Hugging Face Daily Papers**, then uses an LLM (**Gemini, Claude, or local
Ollama — your choice**) to synthesize a curated, **source-linked** briefing and
emails it to you in a clean **light/dark themed** layout.

Built to help you **stay at the cutting edge of the AI stack, ship better AI
products, and spot the gaps worth turning into an OSS project, paper, or
startup.**

## The briefing — an information pyramid

Structured so 90 seconds gets you everything essential; 10 minutes gets you
depth. Each section carries a read-time budget; every claim carries a source link
you can click to verify.

1. **⚡ The Pulse (90 sec)** — *Today's Game-Changer* (the one thing) + *In a
   Nutshell* (8–12 one-line bullets covering everything else). Stands alone.
2. **🚀 Opportunity of the Day (2 min)** — the single most compelling thing to
   build today, with the gap, why-now, build-as, wedge & moat, validation, and a
   first step. *(Public/free — the viral hook.)*
3. **🗺️ Full Opportunity Map (5 min)** — 4–6 *more* buildable bets in the same
   format. *(Private — your secret sauce / paid tier; see freemium model below.)*
4. **📊 Stack Signals (3 min)** — benchmark/eval leaderboard moves, repo & model
   velocity, and funding/launches *with the thesis extracted*.
5. **🔬 Deep Reads (optional)** — the one paper to read end-to-end + a scanning
   list of supporting research.

### Freemium model

The **Opportunity of the Day** ships publicly (in the email, the archive, and the
chat teaser) as the hook. The **Full Opportunity Map** is a private section
(`src/private/`, gitignored) — it's in *your* email but is automatically stripped
from the public archive, which instead shows a subscribe CTA (`SUBSCRIBE_URL`).
Free tier drives distribution; the full map is your paid/private tier.

## Sources

Only feeds verified reachable (HTTP 200) are fetched deterministically; anything
without a reliable RSS is backfilled by the LLM's web grounding.

| Type | Covered |
|------|---------|
| Frontier labs | OpenAI, Google DeepMind, Google AI, Microsoft (Research + AI), Hugging Face, Cohere |
| Newsletters | Latent Space, Import AI, Ahead of AI, Interconnects, The Gradient, TLDR AI, Last Week in AI, Gradient Flow, The Rundown AI |
| Infra / tooling | LangChain, Together AI, NVIDIA Developer, AWS ML Blog |
| Community | r/LocalLLaMA, r/MachineLearning, r/OpenAI, Hacker News (AI/LLM/agent, 50+ pts) |
| Research | arXiv (`cs.AI`, `cs.LG`, `cs.CL`, `cs.MA`) + **HF Daily Papers** (community-upvoted "must-reads") |
| Web-grounded backfill | Anthropic, Meta AI, Mistral, xAI, DeepSeek, Qwen, The Batch, The Neuron, LlamaIndex/Pinecone/Weaviate/Modal, LMSYS/SWE-bench leaderboards, GitHub & HF trending, YC/Product Hunt launches, AI funding rounds |

HF Daily Papers are ranked by community upvotes so genuine must-reads beat merely
recent ones. arXiv keyword queries stay agentic-focused (agents, tool-use,
memory, planning, RAG, reasoning benchmarks).

## Provider (Gemini, Claude, or Ollama)

Analysis is pluggable via the `PROVIDER` env var — no code change to switch:

| `PROVIDER` | Default model | Web grounding | Key needed |
|------------|---------------|---------------|------------|
| `gemini` (default) | `gemini-2.5-flash` | Google Search | `GEMINI_API_KEY` |
| `claude` | `claude-sonnet-4-6` | web_search tool | `ANTHROPIC_API_KEY` |
| `ollama` | `llama3.1` | none (RSS + arXiv only) | *(none — local)* |

Override the model anytime with `DIGEST_MODEL` (e.g. `gemini-2.5-pro`,
`claude-opus-4-8`, `qwen2.5:14b`). Only the selected provider's key is required.
Ollama streams output to the terminal so you can watch generation live.

> **Note:** web-grounded backfill (Stack Signals funding/benchmarks, dropped-feed
> labs) only runs on Gemini/Claude. Ollama produces a solid digest from the RSS +
> arXiv + HF candidate set, but won't fill gaps that need live search.

## Architecture

```
fetchers.py  ──►  analyzer.py  ──►  providers.py  ──►  emailer.py (Resend)
  RSS + arXiv      rank + cap +     gemini|claude|       light/dark themed,
  + HF Papers      build prompt     ollama (+ web        source-linked HTML
                        ▲           grounding)
                   sources.py (registry)
```

Orchestrated by `src/main.py`, scheduled by a GitHub Actions cron
(`.github/workflows/daily-ai-digest.yml`) — no servers to run.

## Setup (one-time, ~5 minutes)

### 1. Get the keys
- **Gemini API key** → https://aistudio.google.com/apikey (default; free tier covers a daily run)
  _(or, if `PROVIDER=claude`, an **Anthropic key** → https://console.anthropic.com/settings/keys)_
- **Resend API key** → https://resend.com/api-keys (free tier covers a daily email)

> The default sender `onboarding@resend.dev` can only send to the **email of the
> Resend account owner**. Sign up for Resend with your inbox (or verify a domain
> and set `EMAIL_FROM`) so delivery works.

### 2. Add them to GitHub
**Settings → Secrets and variables → Actions**.

**Secrets:** `GEMINI_API_KEY` (or `ANTHROPIC_API_KEY`) + `RESEND_API_KEY`
**Variables (optional):** `PROVIDER`, `EMAIL_TO`, `EMAIL_FROM`, `DIGEST_MODEL`,
`LOOKBACK_DAYS`, `ENABLE_WEB_SEARCH`.

### 3. Run it
- **Manually:** Actions tab → *Daily AI Digest* → **Run workflow**. Check your inbox.
- **Automatic:** daily at **13:00 UTC**. Change the `cron` in the workflow to taste.

## Run locally

```bash
pip install -r requirements.txt
cp .env.example .env          # fill in GEMINI_API_KEY (or ANTHROPIC_API_KEY) + RESEND_API_KEY
python -m src.main            # builds digest, writes digest_YYYYMMDD.html, emails it
```

### Test the whole pipeline for free (no tokens, no email)

```bash
# one-time: install ollama (https://ollama.com), then
ollama serve &
ollama pull qwen2.5:14b        # or llama3.1, qwen3:8b, etc.

PROVIDER=ollama DRY_RUN=true python -m src.main
# → writes digest_YYYYMMDD.html locally; skips Resend. Open it in a browser.
```

To preview the light/dark theme: open the HTML in Chrome, then DevTools →
**Rendering → Emulate prefers-color-scheme** to flip modes (or toggle your OS theme).

> **Resilience:** transient `503 / 429 / overloaded` errors are retried with
> exponential backoff (5s → 10s → 20s) before failing. Broken feeds are skipped
> with a warning, never aborting the run. arXiv gets a wide enough lookback that
> weekends (no new submissions) don't leave the research section empty.

## Tests

```bash
python -m unittest discover -s tests
```

## Configuration reference

All knobs are environment variables; see [`.env.example`](.env.example). Notable:

- `PROVIDER=gemini|claude|ollama` — pick the analysis engine.
- `DIGEST_MODEL` — override the model.
- `ENABLE_WEB_SEARCH=false` — run purely from RSS + arXiv + HF (cheaper, narrower).
- `LOOKBACK_DAYS` — how many days count as "latest" (7 recommended so weekend
  arXiv gaps don't empty the research section).

## Customizing sources

Edit `src/sources.py`:
- `RSS_FEEDS` — add/remove feeds (name, url, category). Keep only reachable ones.
- `WEB_SEARCH_TARGETS` — plain-language sources for the LLM to search/verify.
- `ARXIV_CATEGORIES` / `ARXIV_QUERIES` — tune the research net.

## Publish a public archive (GitHub Pages)

Set `PUBLISH_ARCHIVE=true` and each run writes a browsable site to `docs/`:
`docs/index.html` lists every issue, `docs/digests/digest_YYYYMMDD.html` is each
day's digest. Enable serving in **Settings → Pages → Deploy from branch → `main`
→ `/docs`**. The workflow commits `docs/` back automatically. Set `SITE_URL` to
your Pages URL so chat posts can link the full issue.

## Multi-channel delivery

Besides email, post a short teaser (The Pulse + a link to the full issue) to chat:
set any of `SLACK_WEBHOOK_URL`, `DISCORD_WEBHOOK_URL`, or
`TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`. Unconfigured channels are skipped.

## Audio digest

Set `ENABLE_AUDIO=true` (needs `pip install gTTS`, free, no key) to voice The
Pulse to an MP3 in `AUDIO_DIR` — a listen-on-your-commute version. In CI it's
uploaded as a build artifact.

## Custom & private sections

The digest's sections are composable. Public sections live in `src/analyzer.py`;
you can add your own **private** sections under `src/private/` (gitignored) that
never ship in the public repo and are **automatically stripped from the public
archive** via their `<!--SECTION:id-->` markers. See
[`src/private/README.md`](src/private/README.md). To run a private section in CI
without committing it, base64-encode the module into the `OPPORTUNITY_B64` secret
— the workflow restores it for the run only.
