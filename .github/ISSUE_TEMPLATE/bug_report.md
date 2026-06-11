---
name: Bug report
about: Something in the pipeline broke or produced wrong output
title: "[bug] "
labels: bug
---

**What happened?**
A clear description of the problem (broken run, bad digest output, rendering
issue, etc.).

**How are you running it?**
- Provider: <!-- gemini | claude | ollama -->
- Model (`DIGEST_MODEL` / `OPPORTUNITY_MODEL`):
- Where: <!-- GitHub Actions | local -->
- `SOURCE_PRESET` (if any):

**Logs / output**
Paste the relevant log lines (Actions run log or terminal). For digest-quality
bugs, paste the offending HTML snippet or attach a screenshot.

**Expected behavior**
What you expected instead.
