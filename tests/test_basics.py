"""Lightweight unit tests — no network, no API keys required.

Run: python -m pytest -q   (or: python -m unittest discover tests)
"""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from src.emailer import _inline_styles, render_html, subject_line
from src.fetchers import Item, _strip_html, dedupe


class TestFetchers(unittest.TestCase):
    def test_strip_html(self):
        self.assertEqual(_strip_html("<p>Hello&nbsp;<b>world</b></p>"), "Hello world")

    def test_dedupe_by_url(self):
        a = Item("OpenAI", "lab", "GPT release", "https://x.com/a", None)
        b = Item("Mirror", "newsletter", "Different title", "https://x.com/a/", None)
        c = Item("Meta", "lab", "Llama news", "https://y.com/b", None)
        out = dedupe([a, b, c])
        self.assertEqual(len(out), 2)

    def test_dedupe_by_title(self):
        a = Item("A", "lab", "The Big Model Launch!", "https://x.com/a", None)
        b = Item("B", "newsletter", "the big model launch", "https://z.com/b", None)
        out = dedupe([a, b])
        self.assertEqual(len(out), 1)

    def test_age_days(self):
        now = datetime(2026, 1, 10, tzinfo=timezone.utc)
        it = Item("A", "lab", "t", "u", datetime(2026, 1, 8, tzinfo=timezone.utc))
        self.assertAlmostEqual(it.age_days(now), 2.0, places=1)
        undated = Item("A", "lab", "t", "u", None)
        self.assertGreater(undated.age_days(now), 1000)


class TestEmailer(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 6, 5, tzinfo=timezone.utc)

    def test_subject_has_date(self):
        self.assertIn("Jun 05, 2026", subject_line(self.now))

    def test_inline_styles_applied(self):
        styled = _inline_styles("<h2>Title</h2><p>Body</p>")
        self.assertIn("style=", styled)
        self.assertNotIn("<h2>Title", styled)  # bare tag replaced

    def test_render_html_wraps_body(self):
        html = render_html("<h2>Hi</h2>", self.now)
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("June 05, 2026", html)
        self.assertIn("Hi", html)


if __name__ == "__main__":
    unittest.main()
