"""Read-only SHA-256 checks for the captured Vibe4You GST R2 production baseline.

No SSH, network, prod code writes, secrets or personal data required.
This is a data-provenance test, not a substitute for full application tests.
"""
import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / "deployment-snapshots/vibe4you-20261116-gst-r2"
MANIFEST_SHA = "ec13b4f28f99b26f3cf468412d77a651b8596decc1cb5afb1012170bac11a126"
SOURCE_PROMOTIONS = (
    "admin/billing_audit.py",
    "admin/gst_catalog_review.py",
    "admin/gst_invoice_draft.py",
    "admin/gst_official_suggestions.py",
    "admin/invoice_ledger.py",
    "admin/invoice_order_adapter.py",
    "admin/order_documents.py",
    "admin/order_profit.py",
    "admin/tax_document_pdf.py",
    "server/styledash_registration_email.py",
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ProductionSnapshotParity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((SNAPSHOT / "code-manifest.json").read_text(encoding="utf-8"))
        cls.hashes = {row["path"]: row["sha256"] for row in cls.manifest["code_files"]}

    def test_exact_production_manifest(self):
        self.assertEqual(self.manifest["production_manifest_sha256"], MANIFEST_SHA)

    def test_all_59_production_code_files_are_byte_identical(self):
        self.assertEqual(len(self.hashes), 59)
        for rel, expected in self.hashes.items():
            with self.subTest(path=rel):
                self.assertEqual(digest(SNAPSHOT / "deployed" / rel), expected)

    def test_source_promotions_match_exact_live_bytes(self):
        self.assertEqual(len(SOURCE_PROMOTIONS), 10)
        for rel in SOURCE_PROMOTIONS:
            with self.subTest(path=rel):
                self.assertIn(rel, self.hashes)
                src = ROOT / "scripts" / Path(rel).name
                self.assertEqual(digest(src), self.hashes[rel])
                other = ("server/" if rel.startswith("admin/") else "admin/") + Path(rel).name
                if other in self.hashes:
                    self.assertEqual(self.hashes[rel], self.hashes[other])

    def test_exact_deployed_static_pages_in_vite_public(self):
        locations = {
            "server/verify-email.html": "public/verify-email.html",
            "server/verify-email.js": "public/verify-email.js",
            "server/account-deletion.html": "public/account-deletion.html",
            "server/account-deletion.js": "public/account-deletion.js",
            "server/.well-known/assetlinks.json": "public/.well-known/assetlinks.json",
        }
        for deployed, source in locations.items():
            with self.subTest(deployed=deployed):
                self.assertEqual(digest(ROOT / source), self.hashes[deployed])
        self.assertFalse((ROOT / "public/.gitattributes").exists())

    def test_unreadable_modules_are_explicitly_excluded(self):
        self.assertEqual(
            sorted(self.manifest.get("unreadable_paths", [])),
            ["admin/gst_phase1_registry.py", "server/gst_phase1_registry.py"],
        )
        self.assertFalse((ROOT / "scripts/gst_phase1_registry.py").exists())


if __name__ == "__main__":
    unittest.main()
