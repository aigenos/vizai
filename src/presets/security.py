"""SOURCE_PRESET=security — daily infosec briefing.

Vulnerabilities, breaches, offensive/defensive tooling, and security research
(cs.CR). Feeds listed here returned HTTP 200 from well-known, long-stable URLs;
anything paywalled or feed-less is a web-search target instead.
"""

from __future__ import annotations

from ..sources import Feed

RSS_FEEDS: list[Feed] = [
    # ── Vendor / lab research ─────────────────────────────────────────────────
    Feed("Google Project Zero", "https://googleprojectzero.blogspot.com/feeds/posts/default", "lab"),
    Feed("Microsoft Security Blog", "https://www.microsoft.com/en-us/security/blog/feed/", "lab"),

    # ── Reporting / analysis ──────────────────────────────────────────────────
    Feed("Krebs on Security", "https://krebsonsecurity.com/feed/", "newsletter"),
    Feed("Schneier on Security", "https://www.schneier.com/feed/atom/", "newsletter"),
    Feed("The Hacker News", "https://feeds.feedburner.com/TheHackersNews", "newsletter"),
    Feed("BleepingComputer", "https://www.bleepingcomputer.com/feed/", "newsletter"),

    # ── Operational signal ────────────────────────────────────────────────────
    Feed("SANS Internet Storm Center", "https://isc.sans.edu/rssfeed.xml", "infra"),

    # ── Community / where exploits break first ────────────────────────────────
    Feed("r/netsec (top/day)", "https://www.reddit.com/r/netsec/top/.rss?t=day", "community"),
    Feed("r/cybersecurity (top/day)", "https://www.reddit.com/r/cybersecurity/top/.rss?t=day", "community"),
    Feed("HN security (50+ pts)", "https://hnrss.org/newest?q=security+OR+vulnerability+OR+CVE&points=50", "community"),
]

WEB_SEARCH_TARGETS: list[str] = [
    "CISA Known Exploited Vulnerabilities catalog — new entries this week (cisa.gov/known-exploited-vulnerabilities-catalog)",
    "CISA advisories and alerts (cisa.gov/news-events/cybersecurity-advisories)",
    "Cisco Talos Intelligence blog — latest threat research (blog.talosintelligence.com)",
    "Google Threat Analysis Group and Mandiant threat intelligence reports",
    "Microsoft MSRC advisories and Patch Tuesday analysis (msrc.microsoft.com)",
    "NVD / CVE: high-severity CVEs published in the last few days with public PoCs",
    "GitHub trending security tools and PoC repos for the last 24–72 hours",
    "Black Hat / DEF CON / USENIX Security — notable new talks, tools, and papers",
    "Major breach disclosures and incident reports in the last 7 days",
    "Security startup funding rounds in the last 7 days (TechCrunch, The Record)",
]

ARXIV_CATEGORIES: list[str] = ["cs.CR"]

ARXIV_QUERIES: list[str] = [
    'abs:"vulnerability" AND (abs:"detection" OR abs:"discovery" OR abs:"exploit")',
    'abs:"malware" OR abs:"ransomware" OR abs:"intrusion detection"',
    'abs:"fuzzing" OR abs:"binary analysis" OR abs:"program analysis"',
    'abs:"adversarial" AND (abs:"attack" OR abs:"robustness")',
    'abs:"LLM" AND (abs:"security" OR abs:"jailbreak" OR abs:"prompt injection")',
]
