"""Preset loading tests — no network."""

from __future__ import annotations

import importlib
import os
import unittest
from unittest import mock

import src.sources as sources
from src.sources import Feed

_VALID_CATEGORIES = {"lab", "newsletter", "infra", "community", "research"}


def _reload_with_preset(preset: str):
    with mock.patch.dict(os.environ, {"SOURCE_PRESET": preset}):
        return importlib.reload(sources)


class TestPresetLoading(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        # Restore the default AI sources for the rest of the suite.
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SOURCE_PRESET", None)
            importlib.reload(sources)

    def test_default_is_ai(self):
        mod = _reload_with_preset("")
        self.assertTrue(any(f.name == "OpenAI" for f in mod.RSS_FEEDS))
        self.assertIn("cs.AI", mod.ARXIV_CATEGORIES)

    def test_explicit_ai_is_default(self):
        mod = _reload_with_preset("ai")
        self.assertTrue(any(f.name == "OpenAI" for f in mod.RSS_FEEDS))

    def test_security_preset_swaps_sources(self):
        mod = _reload_with_preset("security")
        names = [f.name for f in mod.RSS_FEEDS]
        self.assertIn("Krebs on Security", names)
        self.assertNotIn("OpenAI", names)
        self.assertEqual(mod.ARXIV_CATEGORIES, ["cs.CR"])

    def test_unknown_preset_fails_open_to_ai(self):
        mod = _reload_with_preset("underwater-basket-weaving")
        self.assertTrue(any(f.name == "OpenAI" for f in mod.RSS_FEEDS))

    def test_all_presets_well_formed(self):
        from src.presets import AVAILABLE

        for name in AVAILABLE:
            if name == "ai":
                continue
            with self.subTest(preset=name):
                mod = importlib.import_module(f"src.presets.{name}")
                feeds = mod.RSS_FEEDS
                self.assertGreaterEqual(len(feeds), 3)
                for f in feeds:
                    self.assertIsInstance(f, Feed)
                    self.assertTrue(f.url.startswith("https://"), f.url)
                    self.assertIn(f.category, _VALID_CATEGORIES)
                self.assertTrue(mod.WEB_SEARCH_TARGETS)
                self.assertTrue(mod.ARXIV_CATEGORIES)
                self.assertTrue(mod.ARXIV_QUERIES)


if __name__ == "__main__":
    unittest.main()
