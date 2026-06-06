"""Lightweight unit tests — no network, no API keys required.

Run: python -m pytest -q   (or: python -m unittest discover tests)
"""

from __future__ import annotations

import os
import unittest
from datetime import datetime, timezone
from unittest import mock

from src.config import Config
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


class TestConfig(unittest.TestCase):
    def _env(self, **overrides):
        base = {
            "PROVIDER": "",
            "GEMINI_API_KEY": "",
            "GOOGLE_API_KEY": "",
            "ANTHROPIC_API_KEY": "",
            "RESEND_API_KEY": "",
            "DIGEST_MODEL": "",
        }
        base.update(overrides)
        return base

    def test_gemini_default_provider_and_model(self):
        env = self._env(GEMINI_API_KEY="g", RESEND_API_KEY="r")
        with mock.patch.dict(os.environ, env, clear=True):
            cfg = Config.from_env()
        self.assertEqual(cfg.provider, "gemini")
        self.assertEqual(cfg.model, "gemini-2.5-flash")

    def test_claude_provider_default_model(self):
        env = self._env(PROVIDER="claude", ANTHROPIC_API_KEY="a", RESEND_API_KEY="r")
        with mock.patch.dict(os.environ, env, clear=True):
            cfg = Config.from_env()
        self.assertEqual(cfg.provider, "claude")
        self.assertEqual(cfg.model, "claude-sonnet-4-6")

    def test_explicit_model_overrides_default(self):
        env = self._env(
            GEMINI_API_KEY="g", RESEND_API_KEY="r", DIGEST_MODEL="gemini-2.5-pro"
        )
        with mock.patch.dict(os.environ, env, clear=True):
            cfg = Config.from_env()
        self.assertEqual(cfg.model, "gemini-2.5-pro")

    def test_missing_provider_key_aborts(self):
        env = self._env(RESEND_API_KEY="r")  # no GEMINI key
        with mock.patch.dict(os.environ, env, clear=True):
            with self.assertRaises(SystemExit):
                Config.from_env()

    def test_invalid_provider_aborts(self):
        env = self._env(PROVIDER="openai", RESEND_API_KEY="r")
        with mock.patch.dict(os.environ, env, clear=True):
            with self.assertRaises(SystemExit):
                Config.from_env()

    def test_google_api_key_accepted_as_gemini_key(self):
        env = self._env(GOOGLE_API_KEY="g", RESEND_API_KEY="r")
        with mock.patch.dict(os.environ, env, clear=True):
            cfg = Config.from_env()
        self.assertEqual(cfg.gemini_api_key, "g")


if __name__ == "__main__":
    unittest.main()
