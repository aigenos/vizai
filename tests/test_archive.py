"""Archive tests: publish pipeline, private stripping, index previews, Atom
feed, and the receipts log — all on a temp dir, no network."""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timezone
from unittest import mock

from src import archive
from src.config import Config

BODY = (
    "<!--SECTION:pulse-->\n<h2>⚡ The Pulse (90 sec read)</h2>"
    "<h3>🎯 Today's Game-Changer</h3>"
    '<p><a href="https://x.com/m">MegaModel 9</a> shipped with 1M context — '
    "the new default for agent stacks.</p>\n"
    "<!--SECTION:opp_teaser-->\n<h2>🚀 Opportunity of the Day (2 min read)</h2>"
    "<h3>AgentLint</h3><ul><li><strong>The gap:</strong> nobody lints agent "
    "traces.</li></ul>\n"
    "<!--SECTION:opportunity_map-->\n<h2>🗺️ Full Opportunity Map (5 min read)</h2>"
    "<p>SECRET-MAP-CONTENT</p>\n"
    "<!--SECTION:stack-->\n<h2>📊 Stack Signals (3 min read)</h2><p>x</p>"
)


def _cfg(tmp, **env):
    base = {
        "PROVIDER": "ollama",
        "DRY_RUN": "true",
        "PUBLISH_ARCHIVE": "true",
        "ARCHIVE_DIR": tmp,
        "SITE_URL": "https://me.github.io/dAIly",
        "SUBSCRIBE_URL": "https://buttondown.com/me",
    }
    base.update(env)
    with mock.patch.dict(os.environ, base, clear=True):
        return Config.from_env()


class TestPublish(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.now = datetime(2026, 6, 10, tzinfo=timezone.utc)

    def tearDown(self):
        self.tmp.cleanup()

    def _publish(self, cfg=None, sentinels=("Full Opportunity Map",)):
        cfg = cfg or _cfg(self.tmp.name)
        return archive.publish(
            cfg, BODY, self.now, "test (model)", ["opportunity_map"], list(sentinels)
        )

    def test_private_section_stripped_from_archive(self):
        path = self._publish()
        with open(path, encoding="utf-8") as fh:
            html = fh.read()
        self.assertNotIn("SECRET-MAP-CONTENT", html)
        self.assertNotIn("🗺️", html)  # the private section's heading
        self.assertIn("The Pulse", html)
        # The public Opportunity of the Day teaser stays.
        self.assertIn("AgentLint", html)

    def test_leak_check_refuses_to_publish(self):
        # Sentinel content that survives both marker- and heading-based
        # stripping (no marker, not in an <h2>) must fail closed.
        cfg = _cfg(self.tmp.name)
        with self.assertRaises(RuntimeError):
            archive.publish(
                cfg, BODY, self.now, "e", [], ["SECRET-MAP-CONTENT"]
            )

    def test_index_lists_issue_with_gamechanger_preview(self):
        self._publish()
        with open(os.path.join(self.tmp.name, "index.html"), encoding="utf-8") as fh:
            index = fh.read()
        self.assertIn("digest_20260610.html", index)
        self.assertIn("MegaModel 9", index)  # preview headline

    def test_feed_xml_written_with_entry(self):
        self._publish()
        with open(os.path.join(self.tmp.name, "feed.xml"), encoding="utf-8") as fh:
            feed = fh.read()
        self.assertIn("<feed xmlns=\"http://www.w3.org/2005/Atom\">", feed)
        self.assertIn("digests/digest_20260610.html", feed)
        self.assertIn("MegaModel 9", feed)

    def test_feed_skipped_without_site_url(self):
        self._publish(cfg=_cfg(self.tmp.name, SITE_URL=""))
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, "feed.xml")))

    def test_receipts_logged_and_idempotent(self):
        self._publish()
        self._publish()  # re-run same day must not duplicate
        with open(os.path.join(self.tmp.name, "receipts.md"), encoding="utf-8") as fh:
            receipts = fh.read()
        self.assertEqual(receipts.count("AgentLint"), 1)
        self.assertIn("2026-06-10", receipts)
        self.assertIn("digest_20260610.html", receipts)

    def test_subscribe_embed_html_injected(self):
        cfg = _cfg(self.tmp.name, SUBSCRIBE_EMBED_HTML='<form id="bd">x</form>')
        self._publish(cfg=cfg)
        with open(os.path.join(self.tmp.name, "index.html"), encoding="utf-8") as fh:
            index = fh.read()
        self.assertIn('<form id="bd">x</form>', index)

    def test_digest_page_has_subscribe_cta_and_footer(self):
        path = self._publish()
        with open(path, encoding="utf-8") as fh:
            html = fh.read()
        self.assertIn("https://buttondown.com/me", html)
        self.assertNotIn("Unsubscribe", html)  # archive never shows unsubscribe


class TestIssueHeadline(unittest.TestCase):
    def test_missing_file_fails_open(self):
        self.assertEqual(archive.issue_headline("/nonexistent/x.html"), "")

    def test_truncates_long_headlines(self):
        with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as fh:
            fh.write(
                "<h3>🎯 Today's Game-Changer</h3><p>" + ("word " * 80) + "</p>"
            )
            path = fh.name
        try:
            headline = archive.issue_headline(path)
            self.assertLessEqual(len(headline), 175)
            self.assertTrue(headline.endswith("…"))
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
