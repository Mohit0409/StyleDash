"""Prove recovered GST Phase 1 source is the authentic production version.

No private data, network, production access or test-only substitute.
"""
import hashlib
import importlib.util
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from scripts import gst_phase1_registry as registry

ROOT = Path(__file__).resolve().parents[2]
REGISTRY_SHA = "3244c8adf4d387474462b3ab9a3d1aa6884ad2fdba30ffcbc37c427d7f824c3f"
PROD_RECEIPT_SHA = "eee783b343739237d9bcab2e59e5fe1c0c9d6b35300733bb6edaa64db9f84c3f"


def load_production_receipt():
    path = ROOT / "deployment-snapshots/vibe4you-20261116-gst-r2/deployed/admin/receipt_pdf.py"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == PROD_RECEIPT_SHA
    spec = importlib.util.spec_from_file_location("v4y_exact_live_receipt_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class AuthenticPhase1Tests(unittest.TestCase):
    def test_byte_for_byte_matches_both_pinned_live_sources(self):
        source = (ROOT / "scripts/gst_phase1_registry.py").read_bytes()
        self.assertEqual(hashlib.sha256(source).hexdigest(), REGISTRY_SHA)
        self.assertEqual(len(registry.APPROVED_IDENTITIES), 12)
        self.assertEqual(registry.GST_RATE, Decimal("18"))
        self.assertEqual(registry.HSN_CODE, "9102")

    def test_all_twelve_approved_identity_snapshots(self):
        for product_id, (name, brand) in registry.APPROVED_IDENTITIES.items():
            with self.subTest(product_id=product_id):
                product = {
                    "id": product_id,
                    "name": name,
                    "brand": brand,
                    "category": "Accessories",
                    "subcategory": "Watches",
                }
                data = registry.classification_for_product(
                    product, as_of=date.fromisoformat("2026-11-07")
                )
                self.assertEqual(data["productId"], product_id)
                self.assertEqual(data["gstRate"], "18")
                self.assertEqual(data["hsnCode"], "9102")
                self.assertEqual(data["policyId"], registry.POLICY_ID)
                self.assertEqual(data["priceTreatment"], "GST_INCLUSIVE")

    def test_unknown_identity_and_identity_drift_fail_closed(self):
        pid, (name, brand) = next(iter(registry.APPROVED_IDENTITIES.items()))
        template = {"id": pid, "name": name, "brand": brand,
                    "category": "Accessories", "subcategory": "Watches"}
        for override in (
            {"id": "nonapproved-casio-id"},
            {"name": name + " forged"},
            {"brand": "not-casio"},
            {"category": "Footwear"},
            {"subcategory": "Bags"},
        ):
            with self.subTest(override=override):
                item = {**template, **override}
                with self.assertRaises(registry.GstPhase1ClassificationError):
                    registry.classification_for_product(item, as_of=date(2026, 11, 7))

    def test_never_applies_rate_before_effective_date(self):
        pid, (name, brand) = next(iter(registry.APPROVED_IDENTITIES.items()))
        item = {"id": pid, "name": name, "brand": brand,
                "category": "Accessories", "subcategory": "Watches"}
        with self.assertRaises(registry.GstPhase1ClassificationError):
            registry.classification_for_product(item, as_of=date(2025, 9, 21))

    def test_deployed_receipt_imports_authentic_phase1(self):
        receipt = load_production_receipt()
        self.assertEqual(receipt.GST_RATE, Decimal("18"))
        self.assertEqual(receipt.APPROVED_IDENTITIES, registry.APPROVED_IDENTITIES)
        pid, (name, _) = next(iter(registry.APPROVED_IDENTITIES.items()))
        self.assertEqual(
            receipt._approved_receipt_rate(
                {"productId": pid, "productName": name}, "2026-11-07", None
            ), Decimal("18")
        )
        self.assertIsNone(
            receipt._approved_receipt_rate(
                {"productId": pid, "productName": name + " spoofed"},
                "2026-11-07", None
            )
        )


if __name__ == "__main__":
    unittest.main()
