from __future__ import annotations

import hashlib
import hmac
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from cryptography.fernet import Fernet

ROOT = Path(__file__).resolve().parents[2]

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

SERVER = load_module("styledash_release_server", ROOT / "scripts" / "termux-spa-server.py")
ADMIN = load_module("styledash_release_admin", ROOT / "scripts" / "termux-admin-server.py")
ADMIN.load_public_module = lambda: SERVER

class FakeGateway:
    def __init__(self): self.calls = []
    def create_order(self, payload):
        self.calls.append(payload)
        return {"id": f"order_release_{len(self.calls):03d}"}

class ReleasePaymentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.data = Path(self.temp.name)
        self.service = SERVER.PaymentService(
            ROOT / "server/payment-data/catalog.json",
            ROOT / "server/payment-data/settings.json",
            self.data,
            key_id="rzp_test_placeholder",
            key_secret="test_secret_placeholder",
            webhook_secret="webhook_secret_placeholder",
            mode="test",
            gateway=FakeGateway(),
        )
    def tearDown(self): self.temp.cleanup()
    def payload(self):
        return {
            "items":[{"productId":"sd-prod-001","variantId":"sd-prod-001-var-2","quantity":2}],
            "address":{"name":"Release Test","phone":"9999999999","street":"123 Release Street","city":"Neemuch","pincode":"458441"},
            "deliveryMethod":"express","couponCode":None,"paymentMethod":"upi",
        }
    def create(self, key): return self.service.create_razorpay_order(self.payload(), key)
    def captured(self, created, payment_id):
        return json.dumps({"event":"payment.captured","payload":{"payment":{"entity":{"id":payment_id,"order_id":created["razorpayOrderId"],"amount":created["amount"],"currency":created["currency"],"status":"captured"}}}}, separators=(",",":")).encode()
    def refund(self, created, payment_id, refund_id, amount, cumulative=None):
        if cumulative is None:
            cumulative = amount
        total = created["amount"]
        return json.dumps({
            "event":"refund.processed",
            "payload":{
                "refund":{"entity":{
                    "id":refund_id,
                    "payment_id":payment_id,
                    "amount":amount,
                    "currency":created["currency"],
                    "status":"processed",
                }},
                "payment":{"entity":{
                    "id":payment_id,
                    "order_id":created["razorpayOrderId"],
                    "amount":total,
                    "currency":created["currency"],
                    "amount_refunded":cumulative,
                    "refund_status":"full" if cumulative == total else "partial",
                }},
            },
        }, separators=(",",":")).encode()
    def send(self, body, event_id):
        sig = hmac.new(b"webhook_secret_placeholder", body, hashlib.sha256).hexdigest()
        return self.service.process_webhook(body, sig, event_id)

    def test_captured_shortfall_is_paid_review_and_idempotent(self):
        created = self.create("release-shortfall-001")
        payment_id = "pay_release_shortfall"
        with self.service.store.lock:
            self.service.store.state["inventory"]["sd-prod-001-var-2"] = 1
            self.service.store.save()
        body = self.captured(created, payment_id)
        self.assertEqual(self.send(body, "evt-shortfall-1"), {"success":True})
        order = self.service.store.state["orders"][created["styleDashOrderId"]]
        self.assertEqual((order["paymentStatus"], order["status"]), ("paid","payment_review_required"))
        self.assertFalse(order["inventoryCommitted"])
        self.assertTrue(order["requiresAdminAttention"])
        self.assertEqual(self.service.store.state["inventory"]["sd-prod-001-var-2"], 1)
        self.assertTrue(self.send(body, "evt-shortfall-2")["duplicate"])

    def test_catalog_change_after_order_still_records_captured_payment(self):
        created = self.create("release-catalog-change-001")
        payment_id = "pay_release_catalog_change"
        self.service.products.pop("sd-prod-001")
        result = self.send(
            self.captured(created, payment_id),
            "evt-catalog-change",
        )
        self.assertEqual(result, {"success":True})
        order = self.service.store.state["orders"][created["styleDashOrderId"]]
        self.assertEqual(
            (order["paymentStatus"], order["status"]),
            ("paid", "payment_review_required"),
        )
        self.assertFalse(order["inventoryCommitted"])
        self.assertTrue(order["requiresAdminAttention"])

    def test_full_refund_marks_refunded_but_does_not_auto_restock(self):
        created = self.create("release-refund-001")
        payment_id = "pay_release_refund"
        self.send(self.captured(created, payment_id), "evt-capture")
        stock = self.service.store.state["inventory"]["sd-prod-001-var-2"]
        body = self.refund(created, payment_id, "rfnd_release_full", created["amount"])
        self.assertEqual(self.send(body, "evt-refund"), {"success":True})
        order = self.service.store.state["orders"][created["styleDashOrderId"]]
        self.assertEqual(order["paymentStatus"], "refunded")
        self.assertEqual(order["status"], "placed")
        self.assertEqual(self.service.store.state["inventory"]["sd-prod-001-var-2"], stock)
        self.assertTrue(self.send(body, "evt-refund-redelivery")["duplicate"])

    def test_partial_refund_is_review_only(self):
        created = self.create("release-partial-001")
        payment_id = "pay_release_partial"
        self.send(self.captured(created, payment_id), "evt-capture-partial")
        result = self.send(self.refund(created, payment_id, "rfnd_partial", created["amount"] // 2), "evt-partial")
        self.assertTrue(result["reviewRequired"])
        order = self.service.store.state["orders"][created["styleDashOrderId"]]
        self.assertEqual(order["paymentStatus"], "paid")
        self.assertNotIn("refundId", order)

    def test_split_refunds_become_full_when_cumulative_total_matches(self):
        created = self.create("release-split-refund-001")
        payment_id = "pay_release_split"
        self.send(self.captured(created, payment_id), "evt-split-capture")
        first_amount = created["amount"] // 2
        second_amount = created["amount"] - first_amount

        first = self.send(
            self.refund(
                created,
                payment_id,
                "rfnd_split_1",
                first_amount,
                first_amount,
            ),
            "evt-split-refund-1",
        )
        self.assertTrue(first["reviewRequired"])
        self.assertEqual(
            self.service.store.state["orders"][created["styleDashOrderId"]]["paymentStatus"],
            "paid",
        )

        second = self.send(
            self.refund(
                created,
                payment_id,
                "rfnd_split_2",
                second_amount,
                created["amount"],
            ),
            "evt-split-refund-2",
        )
        self.assertEqual(second, {"success":True})
        order = self.service.store.state["orders"][created["styleDashOrderId"]]
        self.assertEqual(order["paymentStatus"], "refunded")
        self.assertEqual(order["refundId"], "rfnd_split_2")
        self.assertEqual(order["refundAmount"], created["amount"])

    def test_late_capture_cannot_resurrect_refunded_order(self):
        created = self.create("release-late-001")
        payment_id = "pay_release_late"
        capture = self.captured(created, payment_id)
        self.send(capture, "evt-cap-before")
        self.send(self.refund(created, payment_id, "rfnd_late", created["amount"]), "evt-refund-late")
        self.assertTrue(self.send(capture, "evt-cap-after")["duplicate"])
        self.assertEqual(self.service.store.state["orders"][created["styleDashOrderId"]]["paymentStatus"], "refunded")

class AdminCancellationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.app = ADMIN.AdminApplication(root / "styledash.db", Fernet.generate_key().decode(), ROOT / "server/payment-data/catalog.json", ROOT / "server/payment-data/settings.json", root / "data")
        self.app.identity.record_action = lambda *args, **kwargs: None
    def tearDown(self): self.temp.cleanup()
    def seed(self, order, stock=13):
        with self.app.payments.store.lock:
            self.app.payments.store.state["inventory"]["sd-prod-001-var-2"] = stock
            self.app.payments.store.state["orders"][order["id"]] = order
            self.app.payments.store.save()
    def order(self, order_id, method, payment, status, committed=True):
        o = {"id":order_id,"items":[{"productId":"sd-prod-001","variantId":"sd-prod-001-var-2","quantity":2}],"paymentMethod":method,"paymentStatus":payment,"status":status,"statusHistory":[]}
        if committed is not None: o["inventoryCommitted"] = committed
        return o

    def test_cod_cancel_releases_inventory_once(self):
        o = self.order("SD-COD", "cod", "pending", "placed", None)
        self.seed(o)
        result = self.app.update_order_status("adm_test", o["id"], "cancelled")
        self.assertEqual(result["status"], "cancelled")
        self.assertEqual(self.app.payments.store.state["inventory"]["sd-prod-001-var-2"], 15)
        with self.assertRaises(ADMIN.SecurityError): self.app.update_order_status("adm_test", o["id"], "cancelled")
        self.assertEqual(self.app.payments.store.state["inventory"]["sd-prod-001-var-2"], 15)

    def test_paid_online_requires_refund_before_cancel(self):
        o = self.order("SD-ONLINE", "upi", "paid", "placed")
        self.seed(o)
        with self.assertRaises(ADMIN.SecurityError) as caught: self.app.update_order_status("adm_test", o["id"], "cancelled")
        self.assertEqual(caught.exception.code, "refund_required")
        with self.app.payments.store.lock:
            self.app.payments.store.state["orders"][o["id"]]["paymentStatus"] = "refunded"
            self.app.payments.store.save()
        self.app.update_order_status("adm_test", o["id"], "cancelled")
        self.assertEqual(self.app.payments.store.state["inventory"]["sd-prod-001-var-2"], 15)

    def test_refunded_payment_pending_order_closes_without_restock(self):
        o = self.order(
            "SD-REFUNDED-PENDING",
            "upi",
            "refunded",
            "payment_pending",
            None,
        )
        self.seed(o, stock=13)
        cancelled = self.app.update_order_status(
            "adm_test",
            o["id"],
            "cancelled",
        )
        self.assertEqual(cancelled["status"], "cancelled")
        self.assertFalse(cancelled.get("inventoryCommitted", False))
        self.assertEqual(
            self.app.payments.store.state["inventory"]["sd-prod-001-var-2"],
            13,
        )

    def test_refunded_order_cannot_resume_fulfillment(self):
        o = self.order("SD-REFUNDED", "upi", "refunded", "placed")
        self.seed(o)
        with self.assertRaises(ADMIN.SecurityError) as caught:
            self.app.update_order_status("adm_test", o["id"], "confirmed")
        self.assertEqual(caught.exception.code, "refunded_order")
        self.assertEqual(
            self.app.payments.store.state["orders"][o["id"]]["status"],
            "placed",
        )

        cancelled = self.app.update_order_status(
            "adm_test",
            o["id"],
            "cancelled",
        )
        self.assertEqual(cancelled["status"], "cancelled")
        self.assertEqual(
            self.app.payments.store.state["inventory"]["sd-prod-001-var-2"],
            15,
        )

    def test_packed_cannot_cancel(self):
        o = self.order("SD-PACKED", "cod", "pending", "packed")
        self.seed(o)
        with self.assertRaises(ADMIN.SecurityError) as caught: self.app.update_order_status("adm_test", o["id"], "cancelled")
        self.assertEqual(caught.exception.code, "invalid_transition")

    def test_stock_review_can_place_after_restock(self):
        o = self.order("SD-REVIEW", "upi", "paid", "payment_review_required", False)
        o["inventoryShortfall"] = True
        o["requiresAdminAttention"] = True
        self.seed(o, 15)
        with self.app.payments.store.lock:
            aid = "inventory_shortfall_after_capture:SD-REVIEW"
            self.app.payments.store.state["operationalAlerts"][aid] = {"id":aid,"type":"inventory_shortfall_after_capture","entityId":o["id"],"razorpayPaymentId":"pay_review","styleDashOrderId":o["id"],"status":"open","recordedAt":"2026-08-14T00:00:00+00:00"}
            self.app.payments.store.save()
        result = self.app.update_order_status("adm_test", o["id"], "placed")
        self.assertTrue(result["inventoryCommitted"])
        self.assertEqual(self.app.payments.store.state["inventory"]["sd-prod-001-var-2"], 13)

class DeploymentAndTaxTests(unittest.TestCase):
    def test_preflight_precedes_code_mutation(self):
        text = (ROOT / "scripts/termux/deploy-payment-release").read_text(encoding="utf-8")
        self.assertLess(
            text.index('PYTHONPATH="$STAGE/scripts'),
            text.index("PRAGMA integrity_check"),
        )
        self.assertLess(
            text.index("empty Firebase web configuration"),
            text.index("PRAGMA integrity_check"),
        )
        self.assertLess(
            text.index("missing a complete Firebase web configuration"),
            text.index("PRAGMA integrity_check"),
        )
        self.assertLess(
            text.index("Firebase browser and server project IDs do not match"),
            text.index("PRAGMA integrity_check"),
        )
        self.assertIn('firebase_assets=("$STAGE"/dist/assets/*.js)', text)
        self.assertNotIn('auth_assets=("$STAGE"/dist/assets/AuthPage-*.js)', text)
        self.assertIn(
            'grep -Fq "projectId:\\"$STYLEDASH_FIREBASE_PROJECT_ID\\\"" "${firebase_assets[@]}"',
            text,
        )
        self.assertLess(text.index("PRAGMA integrity_check"), text.index('bash "$BACKUP_SCRIPT"'))
        self.assertLess(
            text.index('audit_identity_duplicates.py" "$LIVE_DB"'),
            text.index('bash "$BACKUP_SCRIPT"'),
        )
        self.assertLess(text.index('bash "$BACKUP_SCRIPT"'), text.index('if [ -d "$HOME/server/assets" ]'))
        self.assertLess(text.index("printf 'rollback=%s"), text.index('if [ -d "$HOME/server/assets" ]'))
        self.assertIn(
            'install -m 600 "$STAGE/scripts/styledash_mail.py" "$HOME/server/styledash_mail.py"',
            text,
        )
        self.assertIn(
            'install -m 600 "$STAGE/scripts/styledash_mail.py" "$HOME/admin/styledash_mail.py"',
            text,
        )
        self.assertIn(
            'install -m 600 "$STAGE/scripts/styledash_notify.py" "$HOME/server/styledash_notify.py"',
            text,
        )
        self.assertIn(
            'install -m 600 "$STAGE/scripts/styledash_notify.py" "$HOME/admin/styledash_notify.py"',
            text,
        )
        self.assertIn(
            'install -m 600 "$STAGE/scripts/styledash_firebase.py" "$HOME/server/styledash_firebase.py"',
            text,
        )
        self.assertIn(
            'install -m 600 "$STAGE/scripts/styledash_shops.py" "$HOME/server/styledash_shops.py"',
            text,
        )
        self.assertIn(
            'install -m 600 "$STAGE/scripts/styledash_shops.py" "$HOME/admin/styledash_shops.py"',
            text,
        )
        self.assertIn(
            'install -m 600 "$STAGE/scripts/audit_identity_duplicates.py" "$HOME/server/audit_identity_duplicates.py"',
            text,
        )
        self.assertIn("styledash_migrations=ok", text)
        self.assertIn("duplicate applications exist for", text)
        self.assertIn(
            "from styledash_firebase import _initialize_app",
            text,
        )
        self.assertIn("STYLEDASH_FIREBASE_PROJECT_ID", text)
        self.assertIn("STYLEDASH_FIREBASE_CREDENTIALS", text)
        self.assertIn("Firebase credentials path must be absolute", text)
        self.assertIn("Firebase credentials must remain inside the private StyleDash configuration directory", text)
        self.assertIn("realpath -e", text)
        self.assertIn("stat -c '%u'", text)
        self.assertIn(
            'cp -a "$DATA_ROOT/$authoritative_config" "$BACKUP/data/$authoritative_config"',
            text,
        )

    def test_boot_uses_only_the_managed_ngrok_stack(self):
        text = (ROOT / "scripts/termux/boot-start-styledash").read_text(encoding="utf-8")
        self.assertIn('"$HOME/bin/start-styledash-stack"', text)
        self.assertNotIn("cloudflare", text.casefold())

        verifier = (ROOT / "scripts/termux/verify-styledash-processes").read_text(encoding="utf-8")
        self.assertIn("styledash_cloudflare=absent", verifier)

    def test_refund_processed_is_documented_for_live_webhook(self):
        readme = (ROOT / "server/README.md").read_text(encoding="utf-8")
        self.assertIn("`refund.processed`", readme)
    def test_choice_a(self):
        settings = json.loads((ROOT / "server/payment-data/settings.json").read_text(encoding="utf-8"))
        self.assertEqual(settings["taxRate"], 0.05)
        product = (ROOT / "src/pages/ProductDetail.tsx").read_text(encoding="utf-8")
        self.assertIn("GST calculated at checkout", product)
        self.assertNotIn("Inclusive of all GST taxes", product)

if __name__ == "__main__": unittest.main()
