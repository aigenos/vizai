"""Link checker tests — all network access is mocked."""

from __future__ import annotations

import unittest
from unittest import mock

import requests

from src import linkcheck


class TestExtractLinks(unittest.TestCase):
    def test_unique_in_order(self):
        html = (
            '<a href="https://a.com/1">a</a> <a href="https://b.com/2">b</a> '
            '<a href="https://a.com/1">again</a>'
        )
        self.assertEqual(
            linkcheck.extract_links(html), ["https://a.com/1", "https://b.com/2"]
        )

    def test_ignores_non_http(self):
        html = '<a href="mailto:x@y.com">m</a> <a href="{{{UNSUB}}}">u</a>'
        self.assertEqual(linkcheck.extract_links(html), [])


def _resp(status):
    r = mock.Mock()
    r.status_code = status
    return r


class TestCheckUrl(unittest.TestCase):
    @mock.patch("src.linkcheck.requests.request", return_value=_resp(200))
    def test_ok(self, req):
        self.assertTrue(linkcheck.check_url("https://a.com"))
        self.assertEqual(req.call_args[0][0], "HEAD")

    @mock.patch("src.linkcheck.requests.request", return_value=_resp(404))
    def test_dead_after_get_retry(self, req):
        self.assertFalse(linkcheck.check_url("https://a.com"))
        # HEAD 404 → retried as GET.
        self.assertEqual([c[0][0] for c in req.call_args_list], ["HEAD", "GET"])

    @mock.patch("src.linkcheck.requests.request", return_value=_resp(405))
    def test_method_not_allowed_treated_alive(self, _req):
        # 405/403/429 are bot walls / HEAD quirks, not dead pages.
        self.assertTrue(linkcheck.check_url("https://a.com"))

    @mock.patch(
        "src.linkcheck.requests.request",
        side_effect=requests.ConnectionError("boom"),
    )
    def test_network_error_dead(self, _req):
        self.assertFalse(linkcheck.check_url("https://a.com"))

    @mock.patch(
        "src.linkcheck.requests.request",
        side_effect=[requests.Timeout("slow"), _resp(200)],
    )
    def test_retry_recovers(self, _req):
        self.assertTrue(linkcheck.check_url("https://a.com"))


class TestVerifyLinks(unittest.TestCase):
    HTML = (
        '<li><a href="https://alive.com/x">Alive</a></li>'
        '<li><a href="https://dead.com/y">Dead</a></li>'
    )

    def test_dead_links_flagged_alive_untouched(self):
        with mock.patch.object(
            linkcheck, "check_url", side_effect=lambda u, **kw: "alive" in u
        ):
            out = linkcheck.verify_links(self.HTML)
        self.assertIn('>Dead</a><sup class="aigenos-deadlink"', out)
        self.assertNotIn('>Alive</a><sup', out)

    def test_fail_open_on_unexpected_error(self):
        with mock.patch.object(
            linkcheck, "find_dead_links", side_effect=RuntimeError("boom")
        ):
            out = linkcheck.verify_links(self.HTML)
        self.assertEqual(out, self.HTML)

    def test_no_links_noop(self):
        self.assertEqual(linkcheck.verify_links("<p>plain</p>"), "<p>plain</p>")


if __name__ == "__main__":
    unittest.main()
