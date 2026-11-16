"""Production GST-inclusive receipt breakdown regression.

Synthetic records only: no live customer data or owner approvals used.
"""
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
import json
import sqlite3
import tempfile
import unittest

from scripts.receipt_pdf import _verified_receipt_gst_breakdown


def fixture_order(name, product_id, product_gross, delivery, date, state):
    return {
        "id": name, "createdAt": date + "T11:00:00+05:30",
        "status": "delivered", "paymentStatus": "paid",
        "address": {"state": state},
        "subtotal": product_gross, "discount": "0.00",
        "deliveryFee": delivery, "tryAtHomeFee": "0.00",
        "grandTotal": str(Decimal(product_gross) + Decimal(delivery)),
        "items": [{
            "productId": product_id, "productName": "Synthetic taxable goods",
            "quantity": 1, "unitPrice": product_gross,
            "lineTotal": product_gross
        }]
    }


class VerifiedHistoricalDeliveryGST(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.registry = self.root / "verified_classifications.sqlite3"
        self.policy = self.root / "synthetic_owner_delivery_policy.json"
        with sqlite3.connect(self.registry) as conn:
            conn.execute(
                "CREATE TABLE tax_classifications("
                "product_id TEXT PRIMARY KEY,gst_rate TEXT,"
                "supply_type TEXT,effective_from TEXT,evidence TEXT)"
            )
            conn.executemany(
                "INSERT INTO tax_classifications VALUES (?,?,?,?,?)",
                [
                    ("fixture-taxable-5","5","taxable","2026-10-01",
                     "Synthetic product tax approval evidence"),
                    ("fixture-taxable-18","18","taxable","2026-10-01",
                     "Synthetic product tax approval evidence")
                ]
            )
        # sqlite3.Connection context manager commits but does NOT close;
        # explicitly release Windows file handles before temp-dir cleanup.
        conn.close()
        self.five = fixture_order(
            "TEST-INCLUSIVE-5","fixture-taxable-5","76.00","1.00",
            "2026-11-07","madhyapradesh")
        self.eighteen = fixture_order(
            "TEST-INCLUSIVE-18","fixture-taxable-18","2174.00","100.00",
            "2026-11-02","Rajasthan")
        self.approval = {
            "approved": False, "approved_by": "",
            "evidence": "Synthetic GST composite-delivery policy for unit tests.",
            "components": {
                "delivery": {
                    "treatment": "incidental_to_single_principal_goods_supply",
                    "supply_type": "taxable",
                    "order_authorizations": {
                        "TEST-INCLUSIVE-5": {
                            "confirmed_as_part_of_goods_sale": False,
                            "order_date": "2026-11-07",
                            "customer_paid_total": "77.00",
                            "delivery_charge": "1.00",
                            "principal_goods_gst_rate": "5",
                            "evidence": "Synthetic 5pct seller-charged goods delivery confirmation"
                        },
                        "TEST-INCLUSIVE-18": {
                            "confirmed_as_part_of_goods_sale": False,
                            "order_date": "2026-11-02",
                            "customer_paid_total": "2274.00",
                            "delivery_charge": "100.00",
                            "principal_goods_gst_rate": "18",
                            "evidence": "Synthetic 18pct seller-charged goods delivery confirmation"
                        }
                    }
                }
            }
        }

    def authorize(self):
        self.approval["approved"] = True
        self.approval["approved_by"] = "Synthetic test administrator"
        for permit in self.approval["components"]["delivery"]["order_authorizations"].values():
            permit["confirmed_as_part_of_goods_sale"] = True
        self.write_policy()

    def write_policy(self):
        self.policy.write_text(json.dumps(self.approval),encoding="utf-8")

    def check(self, order):
        return _verified_receipt_gst_breakdown(
            order,registry_path=self.registry,service_policy_path=self.policy)

    def test_no_approval_keeps_both_orders_unverified(self):
        self.write_policy()
        self.assertIsNone(self.check(self.five))
        self.assertIsNone(self.check(self.eighteen))

    def test_no_policy_keeps_both_orders_unverified(self):
        self.assertIsNone(self.check(self.five))
        self.assertIsNone(self.check(self.eighteen))

    def test_gst_inclusive_five_percent_with_historical_alias(self):
        self.authorize()
        before = deepcopy(self.five)
        value = self.check(self.five)
        self.assertIsNotNone(value)
        self.assertEqual(value["gst"],Decimal("3.67"))
        self.assertEqual(value["taxable"],Decimal("73.33"))
        self.assertEqual(value["gst"]+value["taxable"],Decimal("77.00"))
        self.assertEqual(value["type"],"intrastate")
        self.assertEqual(value["cgst"]+value["sgst"],Decimal("3.67"))
        self.assertEqual(self.five,before)

    def test_gst_inclusive_eighteen_percent_interstate(self):
        self.authorize()
        before = deepcopy(self.eighteen)
        value = self.check(self.eighteen)
        self.assertIsNotNone(value)
        self.assertEqual(value["gst"],Decimal("346.88"))
        self.assertEqual(value["taxable"],Decimal("1927.12"))
        self.assertEqual(value["type"],"interstate")
        self.assertEqual(value["igst"],Decimal("346.88"))
        self.assertEqual(value["gst"]+value["taxable"],Decimal("2274.00"))
        self.assertEqual(self.eighteen,before)

    def test_unlisted_order_remains_unverified(self):
        self.authorize()
        fake = dict(self.five,id="TEST-NOT-ON-APPROVAL")
        self.assertIsNone(self.check(fake))

    def test_approved_rate_mismatch_rejected(self):
        self.authorize()
        self.approval["components"]["delivery"]["order_authorizations"]["TEST-INCLUSIVE-5"]["principal_goods_gst_rate"]="18"
        self.write_policy()
        self.assertIsNone(self.check(self.five))

    def test_unverified_product_rejected(self):
        self.authorize()
        fake=deepcopy(self.five)
        fake["items"][0]["productId"]="synthetic-unapproved-product"
        self.assertIsNone(self.check(fake))

    def test_repriced_order_rejected(self):
        self.authorize()
        fake=deepcopy(self.five)
        fake["grandTotal"]="78.00"
        self.assertIsNone(self.check(fake))

    def test_delivery_fee_change_rejected(self):
        self.authorize()
        fake=deepcopy(self.five)
        fake["deliveryFee"]="2.00"
        fake["grandTotal"]="78.00"
        self.assertIsNone(self.check(fake))

    def test_date_change_rejected(self):
        self.authorize()
        fake=deepcopy(self.five)
        fake["createdAt"]="2026-11-08T11:00:00+05:30"
        self.assertIsNone(self.check(fake))

    def test_unknown_near_state_alias_rejected(self):
        self.authorize()
        for invalid in ("madhyapradesh-other","madhyapradesh2","madhyapradesh/delhi"):
            with self.subTest(state=invalid):
                fake=deepcopy(self.five)
                fake["address"]["state"]=invalid
                self.assertIsNone(self.check(fake))

    def test_try_at_home_cannot_inherit_delivery_policy(self):
        self.authorize()
        fake=deepcopy(self.five)
        fake["tryAtHomeFee"]="10.00"
        fake["grandTotal"]="87.00"
        self.assertIsNone(self.check(fake))

    def test_test_payment_and_unfulfilled_orders_rejected(self):
        self.authorize()
        fake=deepcopy(self.five)
        fake["isPaymentTestOrder"]=True
        self.assertIsNone(self.check(fake))
        fake=deepcopy(self.five)
        fake["fulfillmentRequired"]=False
        self.assertIsNone(self.check(fake))

    def test_wrong_item_sum_fails_closed(self):
        self.authorize()
        fake=deepcopy(self.five)
        fake["items"][0]["lineTotal"]="75.00"
        self.assertIsNone(self.check(fake))


if __name__=="__main__":
    unittest.main()
