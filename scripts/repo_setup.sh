#!/usr/bin/env bash
# One-time repo metadata setup — description + topics can't be set from code,
# so this uses the GitHub CLI. Run once after forking/renaming:
#   bash scripts/repo_setup.sh [owner/repo]
set -euo pipefail

REPO="${1:-$(gh repo view --json nameWithOwner -q .nameWithOwner)}"

gh repo edit "$REPO" \
  --description "Daily AI intelligence agent — your personal AI analyst in 90 seconds a day" \
  --add-topic ai \
  --add-topic agents \
  --add-topic newsletter \
  --add-topic llm \
  --add-topic rss \
  --add-topic arxiv \
  --add-topic gemini \
  --add-topic claude \
  --add-topic ollama \
  --add-topic digest \
  --add-topic automation

echo "✓ description + topics set on $REPO"
echo "Manual steps that need the web UI:"
echo "  - Settings → Pages → Deploy from branch → main → /docs   (live demo)"
echo "  - Settings → General → Features → enable Discussions     (launch Q&A)"
