"""Email rendering + delivery via the Resend HTTP API."""

from __future__ import annotations

import logging
from datetime import datetime

import requests

from .config import Config

log = logging.getLogger("vizai.emailer")

RESEND_ENDPOINT = "https://api.resend.com/emails"

_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
</head>
<body style="margin:0;padding:0;background:#f4f5f7;">
<div style="max-width:680px;margin:0 auto;padding:24px 16px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#1a1a2e;line-height:1.6;">
  <div style="background:linear-gradient(135deg,#4f46e5,#7c3aed);border-radius:14px;padding:28px 28px 22px;color:#fff;">
    <div style="font-size:13px;letter-spacing:1.5px;text-transform:uppercase;opacity:.85;">vizai · daily ai intelligence</div>
    <h1 style="margin:8px 0 4px;font-size:24px;font-weight:700;">🤖 Your AI Daily Digest</h1>
    <div style="font-size:14px;opacity:.9;">{date}</div>
  </div>
  <div style="background:#ffffff;border-radius:14px;padding:8px 28px 24px;margin-top:16px;box-shadow:0 1px 3px rgba(0,0,0,.06);">
    {body}
  </div>
  <div style="text-align:center;color:#8a8a9a;font-size:12px;padding:18px 8px;">
    Curated by <strong>vizai</strong> from frontier labs, top newsletters &amp; arXiv ·
    {engine}<br>Stay ahead. Ship great AI.
  </div>
</div>
</body>
</html>"""

# Inline styling for the model-produced tags so the email renders cleanly across
# clients (no <style> blocks — many mail clients strip them).
_TAG_STYLES = {
    "<h2>": '<h2 style="font-size:19px;margin:26px 0 8px;padding-bottom:6px;border-bottom:2px solid #ece9fb;color:#4f46e5;">',
    "<h3>": '<h3 style="font-size:16px;margin:18px 0 4px;color:#1a1a2e;">',
    "<p>": '<p style="margin:8px 0;font-size:15px;color:#2a2a3a;">',
    "<ul>": '<ul style="margin:8px 0 8px 0;padding-left:22px;">',
    "<li>": '<li style="margin:6px 0;font-size:15px;color:#2a2a3a;">',
    "<a ": '<a style="color:#7c3aed;text-decoration:none;font-weight:600;" ',
    "<blockquote>": '<blockquote style="margin:10px 0;padding:8px 14px;border-left:3px solid #c7c2f0;background:#faf9ff;color:#3a3a4a;">',
    "<strong>": '<strong style="color:#1a1a2e;">',
}


def _inline_styles(body: str) -> str:
    out = body
    for tag, styled in _TAG_STYLES.items():
        out = out.replace(tag, styled)
    return out


def render_html(body_fragment: str, now: datetime, engine: str = "") -> str:
    engine_label = f"powered by {engine}." if engine else "powered by AI."
    return _TEMPLATE.format(
        title="Your AI Daily Digest",
        date=now.strftime("%A, %B %d, %Y"),
        body=_inline_styles(body_fragment),
        engine=engine_label,
    )


def subject_line(now: datetime) -> str:
    return f"🤖 AI Daily Digest — {now.strftime('%b %d, %Y')}"


def send_email(cfg: Config, subject: str, html: str) -> dict:
    """Send via Resend. Raises on non-2xx so CI surfaces failures."""
    resp = requests.post(
        RESEND_ENDPOINT,
        headers={
            "Authorization": f"Bearer {cfg.resend_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "from": cfg.email_from,
            "to": [cfg.email_to],
            "subject": subject,
            "html": html,
        },
        timeout=30,
    )
    if resp.status_code >= 300:
        raise RuntimeError(
            f"Resend send failed ({resp.status_code}): {resp.text[:500]}"
        )
    data = resp.json()
    log.info("email sent to %s (id=%s)", cfg.email_to, data.get("id"))
    return data
