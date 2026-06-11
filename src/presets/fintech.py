"""SOURCE_PRESET=fintech — daily fintech / payments briefing.

Payments infrastructure, banking tech, fraud/risk, and the startup landscape.
Feeds listed here use long-stable URLs; paywalled outlets (American Banker,
The Information) are web-search targets instead.
"""

from __future__ import annotations

from ..sources import Feed

RSS_FEEDS: list[Feed] = [
    # ── Industry vendors / platforms ──────────────────────────────────────────
    Feed("Stripe Blog", "https://stripe.com/blog/feed.rss", "infra"),

    # ── Industry reporting ────────────────────────────────────────────────────
    Feed("Finextra", "https://www.finextra.com/rss/headlines.aspx", "newsletter"),
    Feed("TechCrunch Fintech", "https://techcrunch.com/category/fintech/feed/", "newsletter"),

    # ── Community ─────────────────────────────────────────────────────────────
    Feed("r/fintech (top/day)", "https://www.reddit.com/r/fintech/top/.rss?t=day", "community"),
    Feed("r/payments (top/day)", "https://www.reddit.com/r/payments/top/.rss?t=day", "community"),
    Feed("HN fintech (50+ pts)", "https://hnrss.org/newest?q=fintech+OR+payments+OR+banking&points=50", "community"),
]

WEB_SEARCH_TARGETS: list[str] = [
    "American Banker — latest banking technology stories (americanbanker.com)",
    "Plaid, Adyen, Wise, Marqeta product launches and engineering blog posts",
    "a16z fintech and QED Investors — latest theses and portfolio launches",
    "Federal Reserve, OCC, CFPB — payments/fintech regulatory actions this week",
    "Stablecoin and real-time payments (FedNow, SEPA Instant, UPI) developments",
    "Fraud, AML, and identity-verification tooling launches in the last week",
    "Y Combinator fintech launches in the last week (ycombinator.com/launches)",
    "Fintech funding rounds in the last 7 days (TechCrunch, Finextra, Crunchbase)",
    "Earnings and product news from public fintechs (Block, PayPal, Visa, Mastercard)",
]

ARXIV_CATEGORIES: list[str] = ["q-fin.ST", "q-fin.TR", "q-fin.RM", "cs.CE"]

ARXIV_QUERIES: list[str] = [
    'abs:"fraud detection" OR abs:"anti-money laundering" OR abs:"credit risk"',
    'abs:"language model" AND (abs:"finance" OR abs:"financial" OR abs:"trading")',
    'abs:"market" AND (abs:"prediction" OR abs:"forecasting") AND abs:"deep learning"',
    'abs:"payments" OR abs:"blockchain" AND abs:"settlement"',
]
