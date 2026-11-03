"""No-network tests for offline production HTML/asset integrity gate."""
from __future__ import annotations

import hashlib
import unittest

from frontend_asset_manifest_gate import inspect


class FrontendAssetManifestGateTests(unittest.TestCase):
    def setUp(self):
        self.head = (
            '<head><script src="/assets/review-v2.js"></script>'
            '<script type="module" src="/assets/index.js"></script>'
            '<link rel="stylesheet" href="/assets/index-BIT.css"></head>'
        )
        self.html = ("<!DOCTYPE html><html>" + self.head + "<body></body></html>").encode()
        self.assets = {
            "server/assets/review-v2.js": b"photo",
            "server/assets/index.js": b"app",
            "server/assets/index-BIT.css": b"style",
        }

    def manifest(self, html=None, omit=None):
        body = self.html if html is None else html
        records = {"server/index.html": body, **self.assets}
        if omit:
            records.pop(omit)
        return ("\n".join(
            hashlib.sha256(data).hexdigest()+"  "+path
            for path,data in sorted(records.items())
        )+"\n").encode()

    def test_clean_html_with_complete_manifest_passes(self):
        report=inspect(self.html,self.manifest(),required_script="/assets/review-v2.js")
        self.assertTrue(report["passed"],report)
        self.assertEqual(report["local_asset_references"],3)

    def test_literal_backtick_n_is_rejected(self):
        artifact=chr(96)+"n"
        bad=self.html.replace(b"</script><script type",("</script>"+artifact+"<script type").encode(),1)
        report=inspect(bad,self.manifest(html=bad))
        self.assertFalse(report["passed"])
        self.assertIn("literal_backtick_n_in_html",report["problems"])

    def test_missing_asset_manifest_entry_is_rejected(self):
        report=inspect(self.html,self.manifest(omit="server/assets/index-BIT.css"))
        self.assertIn("unmanifested_asset:server/assets/index-BIT.css",report["problems"])

    def test_stale_html_digest_is_rejected(self):
        other=self.html.replace(b"<!DOCTYPE html>",b"<!DOCTYPE HTML>")
        report=inspect(other,self.manifest())
        self.assertIn("html_checksum_mismatch",report["problems"])

    def test_required_review_overlay_cannot_be_dropped(self):
        report=inspect(self.html,self.manifest(),required_script="/assets/missing-review.js")
        self.assertFalse(report["passed"])
        self.assertIn("required_script_not_referenced:/assets/missing-review.js",report["problems"])

    def test_duplicate_manifest_records_are_rejected(self):
        manifest=self.manifest()
        double=manifest+manifest.splitlines()[0]+b"\n"
        report=inspect(self.html,double)
        self.assertTrue(any("duplicate_manifest_entry" in p for p in report["problems"]))

    def test_module_script_must_remain_in_head(self):
        html=self.html.replace(b'<script type="module" src="/assets/index.js"></script>',b"")
        html=html.replace(b"</body>",b'<script type="module" src="/assets/index.js"></script></body>')
        report=inspect(html,self.manifest(html=html))
        self.assertIn("module_script_missing_from_head",report["problems"])

    def test_main_stylesheet_must_remain_in_head(self):
        html=self.html.replace(b'<link rel="stylesheet" href="/assets/index-BIT.css">',b"")
        html=html.replace(b"</body>",b'<link rel="stylesheet" href="/assets/index-BIT.css"></body>')
        report=inspect(html,self.manifest(html=html))
        self.assertIn("main_stylesheet_missing_from_head",report["problems"])


if __name__ == "__main__":
    unittest.main()


