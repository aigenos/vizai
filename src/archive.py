"""Public digest archive for GitHub Pages.

Writes each day's digest to ``<archive_dir>/digests/digest_YYYYMMDD.html`` and
regenerates ``<archive_dir>/index.html`` listing every past issue, so people can
read the output before cloning — the single biggest driver of stars for a digest
tool.

SAFETY: private sections (e.g. the Opportunity Map) are stripped here BEFORE
anything is written, using the ``<!--SECTION:id-->`` markers the model emits.
The published archive therefore never contains your secret sauce, even though the
emailed copy does.
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime

from .emailer import render_html, subscribe_cta

log = logging.getLogger("aigenos.archive")

_DIGEST_RX = re.compile(r"digest_(\d{8})\.html$")


def strip_private_sections(body_fragment: str, private_ids: list[str]) -> str:
    """Remove each private section: from its <!--SECTION:id--> marker up to the
    next <!--SECTION:...--> marker (or end of fragment if it's the last one)."""
    out = body_fragment
    for sid in private_ids:
        # Match the marker, then everything up to (but not including) the next
        # section marker, or the end of the string.
        pattern = re.compile(
            r"<!--SECTION:" + re.escape(sid) + r"-->.*?(?=<!--SECTION:|\Z)",
            flags=re.DOTALL,
        )
        out = pattern.sub("", out)
    return out


def _list_issues(digests_dir: str) -> list[tuple[str, datetime]]:
    """Return (filename, date) for each archived digest, newest first."""
    issues: list[tuple[str, datetime]] = []
    if not os.path.isdir(digests_dir):
        return issues
    for name in os.listdir(digests_dir):
        m = _DIGEST_RX.search(name)
        if not m:
            continue
        try:
            d = datetime.strptime(m.group(1), "%Y%m%d")
        except ValueError:
            continue
        issues.append((name, d))
    issues.sort(key=lambda t: t[1], reverse=True)
    return issues


_INDEX_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="color-scheme" content="light dark">
<title>{title}</title>
<style>
:root {{
  color-scheme: light dark;
  --bg:#f3f4f8; --surface:#fff; --text:#14142a; --muted:#6b6b85;
  --accent:#6366f1; --border:#e8e6f5; --shadow:0 1px 2px rgba(20,20,42,.04),0 8px 24px rgba(20,20,42,.06);
}}
@media (prefers-color-scheme: dark) {{
  :root {{
    --bg:#0a0a14; --surface:#14141f; --text:#ececf5; --muted:#8e8ea8;
    --accent:#8b8cff; --border:#2a2a3d; --shadow:0 1px 2px rgba(0,0,0,.4),0 8px 24px rgba(0,0,0,.35);
  }}
}}
* {{ box-sizing:border-box; }}
body {{
  margin:0; background:var(--bg); color:var(--text);
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI Variable','Segoe UI',Roboto,Arial,sans-serif;
  -webkit-font-smoothing:antialiased; line-height:1.6;
}}
.wrap {{ max-width:720px; margin:0 auto; padding:32px 18px 64px; }}
.hero {{
  background:linear-gradient(135deg,#4f46e5 0%,#7c3aed 55%,#c026d3 100%);
  border-radius:20px; padding:34px 30px; color:#fff;
  box-shadow:0 8px 32px rgba(79,70,229,.25);
}}
.hero .kicker {{ font-size:11px; letter-spacing:2px; text-transform:uppercase; opacity:.8; font-weight:600; }}
.hero h1 {{ margin:10px 0 6px; font-size:30px; font-weight:700; letter-spacing:-.02em; }}
.hero p {{ margin:0; font-size:15px; opacity:.92; }}
ul.issues {{ list-style:none; margin:24px 0 0; padding:0; }}
li.issue a {{
  display:flex; justify-content:space-between; align-items:center;
  background:var(--surface); border:1px solid var(--border); border-radius:14px;
  padding:16px 20px; margin:12px 0; text-decoration:none; color:var(--text);
  box-shadow:var(--shadow); transition:transform .12s ease, border-color .12s ease;
}}
li.issue a:hover {{ transform:translateY(-2px); border-color:var(--accent); }}
li.issue .date {{ font-weight:650; font-size:16px; }}
li.issue .go {{ color:var(--accent); font-weight:700; font-size:14px; }}
.empty {{ color:var(--muted); margin-top:24px; }}
.foot {{ text-align:center; color:var(--muted); font-size:12px; margin-top:40px; }}
.foot a {{ color:var(--accent); text-decoration:none; }}
</style>
</head>
<body>
<div class="wrap">
  <div class="hero">
    <div class="kicker">by aigenos · daily ai intelligence</div>
    <h1>d<span style="color:#fcd34d;">AI</span>ly</h1>
    <p>{tagline}</p>
  </div>
  {body}
  <div class="foot">
    Built with <a href="https://github.com/aigenos/aigenos">aigenos</a> · curated from frontier labs, newsletters, infra, community &amp; arXiv.
  </div>
</div>
</body>
</html>"""


def _render_index(cfg, issues: list[tuple[str, datetime]]) -> str:
    if issues:
        rows = "\n".join(
            f'    <li class="issue"><a href="digests/{name}">'
            f'<span class="date">{d.strftime("%A, %B %-d, %Y") if os.name != "nt" else d.strftime("%A, %B %d, %Y")}</span>'
            f'<span class="go">Read →</span></a></li>'
            for name, d in issues
        )
        body = f'  <ul class="issues">\n{rows}\n  </ul>'
    else:
        body = '  <p class="empty">No issues published yet — check back tomorrow.</p>'
    return _INDEX_TEMPLATE.format(
        title=cfg.site_title,
        tagline="Stay at the cutting edge of AI — in 90 seconds a day.",
        body=body,
    )


def publish(cfg, body_fragment: str, now: datetime, engine: str, private_ids: list[str]) -> str:
    """Strip private sections, write the public issue, regenerate the index.

    Returns the path to the written issue file.
    """
    public_fragment = strip_private_sections(body_fragment, private_ids)
    # Public archive gets the subscribe CTA (the freemium upsell); the email does
    # not need it. No-op when SUBSCRIBE_URL is unset.
    cta = subscribe_cta(getattr(cfg, "subscribe_url", ""))
    public_html = render_html(public_fragment, now, engine=engine, cta=cta)

    digests_dir = os.path.join(cfg.archive_dir, "digests")
    os.makedirs(digests_dir, exist_ok=True)

    issue_name = f"digest_{now.strftime('%Y%m%d')}.html"
    issue_path = os.path.join(digests_dir, issue_name)
    with open(issue_path, "w", encoding="utf-8") as fh:
        fh.write(public_html)

    # Regenerate the index over all issues now on disk.
    index_html = _render_index(cfg, _list_issues(digests_dir))
    index_path = os.path.join(cfg.archive_dir, "index.html")
    with open(index_path, "w", encoding="utf-8") as fh:
        fh.write(index_html)

    log.info("archived public issue → %s (index regenerated)", issue_path)
    if private_ids:
        log.info("stripped %d private section(s) from public copy: %s", len(private_ids), ", ".join(private_ids))
    return issue_path
