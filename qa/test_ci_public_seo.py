"""Unit tests for the read-only public SEO checker (synthetic fixtures only)."""
from __future__ import annotations

import unittest

from ci_public_seo import ORIGIN, evaluate


def sitemap(*paths: str) -> str:
    urls = "".join(f"<url><loc>{ORIGIN}{path}</loc></url>" for path in paths)
    return f'<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>'


ROBOTS = f"User-agent: *\nAllow: /\nSitemap: {ORIGIN}/sitemap.xml\n"
STORES = [
    {"slug": "alpha-01", "active": True, "approved": True, "productCount": 3},
    {"slug": "empty-02", "active": True, "approved": True, "productCount": 0},
    {"slug": "inactive-03", "active": False, "approved": True, "productCount": 5},
]


class PublicSeoAuditTests(unittest.TestCase):
    def test_complete_canonical_sitemap_passes(self) -> None:
        result = evaluate(ROBOTS, sitemap("/", "/stores", "/store/alpha-01"), STORES)
        self.assertTrue(result["passed"])
        self.assertEqual(result["warnings"], [])
        self.assertEqual(result["totals"]["missing_active_stores"], 0)

    def test_missing_active_store_is_warning_not_early_deployment_failure(self) -> None:
        result = evaluate(ROBOTS, sitemap("/", "/stores"), STORES)
        self.assertTrue(result["passed"])
        self.assertEqual(result["totals"]["missing_active_stores"], 1)
        self.assertEqual(result["missing_sample"], [f"{ORIGIN}/store/alpha-01"])
        self.assertEqual(len(result["warnings"]), 1)

    def test_invalid_sitemap_fails(self) -> None:
        result = evaluate(ROBOTS, "<urlset", STORES)
        self.assertFalse(result["passed"])
        self.assertTrue(any("invalid XML" in issue for issue in result["errors"]))

    def test_duplicate_sitemap_urls_fail(self) -> None:
        result = evaluate(ROBOTS, sitemap("/", "/"), STORES)
        self.assertFalse(result["passed"])
        self.assertIn("duplicate sitemap URLs", result["errors"])

    def test_invalid_host_fails(self) -> None:
        body = sitemap("/").replace(ORIGIN, "http://www.vibe4you.in")
        result = evaluate(ROBOTS, body, STORES)
        self.assertFalse(result["passed"])
        self.assertIn("sitemap contains noncanonical host or scheme", result["errors"])

    def test_robots_missing_sitemap_declaration_fails(self) -> None:
        result = evaluate("User-agent: *\nAllow: /\n", sitemap("/"), [])
        self.assertFalse(result["passed"])
        self.assertIn("robots.txt does not advertise the canonical sitemap URL", result["errors"])


if __name__ == "__main__":
    unittest.main()
