from __future__ import annotations

import hashlib
import hmac
import importlib.util
import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from cryptography.fernet import Fernet


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("styledash_server", ROOT / "scripts" / "termux-spa-server.py")
assert SPEC and SPEC.loader
SERVER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SERVER)


class FakeGateway:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def create_order(self, payload: dict) -> dict:
        self.calls.append(payload)
        return {"id": f"order_test_{len(self.calls):03d}"}


class PaymentServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.data_directory = Path(self.temporary.name)
        self.gateway = FakeGateway()
        self.service = SERVER.PaymentService(
            ROOT / "server" / "payment-data" / "catalog.json",
            ROOT / "server" / "payment-data" / "settings.json",
            self.data_directory,
            key_id="rzp_test_placeholder",
            key_secret="test_secret_placeholder",
            webhook_secret="webhook_secret_placeholder",
            mode="test",
            gateway=self.gateway,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def payload(self, **overrides):
        payload = {
            "items": [{"productId": "sd-prod-001", "variantId": "sd-prod-001-var-2", "quantity": 2}],
            "address": {
                "name": "Test Customer",
                "phone": "9999999999",
                "street": "123 Test Street",
                "city": "Neemuch",
                "pincode": "458441",
            },
            "userId": "test-user",
            "deliveryMethod": "express",
            "couponCode": None,
            "walletAmount": 0,
            "paymentMethod": "upi",
        }
        payload.update(overrides)
        return payload

    def assert_api_error(self, code: str, callback) -> None:
        with self.assertRaises(SERVER.ApiError) as caught:
            callback()
        self.assertEqual(caught.exception.code, code)

    def create_payment(self, key: str, **payload_overrides):
        return self.service.create_razorpay_order(self.payload(**payload_overrides), key)

    def browser_verification(self, created: dict, payment_id: str) -> dict:
        signature = hmac.new(
            b"test_secret_placeholder",
            f"{created['razorpayOrderId']}|{payment_id}".encode(),
            hashlib.sha256,
        ).hexdigest()
        return {
            "styleDashOrderId": created["styleDashOrderId"],
            "razorpay_order_id": created["razorpayOrderId"],
            "razorpay_payment_id": payment_id,
            "razorpay_signature": signature,
        }

    def webhook_body(self, created: dict, payment_id: str, event: str = "payment.captured", **overrides) -> bytes:
        payment = {
            "id": payment_id,
            "order_id": created["razorpayOrderId"],
            "amount": created["amount"],
            "currency": created["currency"],
            "status": "captured",
        }
        payment.update(overrides)
        payload = {"event": event, "payload": {"payment": {"entity": payment}}}
        if event == "order.paid":
            payload["payload"]["order"] = {"entity": {
                "id": created["razorpayOrderId"],
                "amount_paid": created["amount"],
                "currency": created["currency"],
                "status": "paid",
            }}
        return json.dumps(payload, separators=(",", ":")).encode()

    def deliver(self, body: bytes) -> dict:
        signature = hmac.new(b"webhook_secret_placeholder", body, hashlib.sha256).hexdigest()
        return self.service.process_webhook(body, signature)

    def test_server_calculates_trusted_amount_in_paise(self) -> None:
        response = self.service.create_razorpay_order(self.payload(), "checkout-test-001")
        self.assertEqual(response["trustedTotals"], {
            "subtotal": 946,
            "discount": 0,
            "deliveryFee": 79,
            "taxes": 47,
            "grandTotal": 1072,
        })
        self.assertEqual(response["amount"], 107200)
        self.assertEqual(self.gateway.calls[0]["amount"], 107200)
        self.assertEqual(self.gateway.calls[0]["currency"], "INR")

    def test_create_order_is_idempotent(self) -> None:
        first = self.service.create_razorpay_order(self.payload(), "checkout-test-002")
        second = self.service.create_razorpay_order(self.payload(), "checkout-test-002")
        self.assertEqual(first, second)
        self.assertEqual(len(self.gateway.calls), 1)

    def test_rejects_missing_and_invalid_cart_values(self) -> None:
        self.assert_api_error("invalid_cart", lambda: self.service.calculate_order(self.payload(items=[])))
        self.assert_api_error("invalid_product", lambda: self.service.calculate_order(self.payload(
            items=[{"productId": "missing", "variantId": "missing", "quantity": 1}],
        )))
        self.assert_api_error("invalid_variant", lambda: self.service.calculate_order(self.payload(
            items=[{"productId": "sd-prod-001", "variantId": "missing", "quantity": 1}],
        )))
        for quantity in (0, -1, 11):
            self.assert_api_error("invalid_quantity", lambda quantity=quantity: self.service.calculate_order(self.payload(
                items=[{"productId": "sd-prod-001", "variantId": "sd-prod-001-var-2", "quantity": quantity}],
            )))

    def test_rejects_insufficient_stock_and_unsupported_pincode(self) -> None:
        self.assert_api_error("insufficient_stock", lambda: self.service.calculate_order(self.payload(
            items=[{"productId": "sd-prod-001", "variantId": "sd-prod-001-var-7", "quantity": 1}],
        )))
        address = dict(self.payload()["address"], pincode="458440")
        self.assert_api_error("unsupported_pincode", lambda: self.service.calculate_order(self.payload(address=address)))

    def test_verifies_signature_and_decrements_inventory_once(self) -> None:
        created = self.service.create_razorpay_order(self.payload(), "checkout-test-003")
        payment_id = "pay_test_001"
        signature = hmac.new(
            b"test_secret_placeholder",
            f"{created['razorpayOrderId']}|{payment_id}".encode(),
            hashlib.sha256,
        ).hexdigest()
        verification = {
            "styleDashOrderId": created["styleDashOrderId"],
            "razorpay_order_id": created["razorpayOrderId"],
            "razorpay_payment_id": payment_id,
            "razorpay_signature": signature,
        }

        first = self.service.verify_payment(verification)
        stock_after_first = self.service.store.state["inventory"]["sd-prod-001-var-2"]
        second = self.service.verify_payment(verification)

        self.assertTrue(first["success"])
        self.assertEqual(first["order"]["paymentStatus"], "paid")
        self.assertEqual(stock_after_first, 13)
        self.assertTrue(second["idempotent"])
        self.assertEqual(self.service.store.state["inventory"]["sd-prod-001-var-2"], 13)

    def test_rejects_invalid_signature_and_missing_fields(self) -> None:
        created = self.service.create_razorpay_order(self.payload(), "checkout-test-004")
        self.assert_api_error("signature_mismatch", lambda: self.service.verify_payment({
            "styleDashOrderId": created["styleDashOrderId"],
            "razorpay_order_id": created["razorpayOrderId"],
            "razorpay_payment_id": "pay_test_002",
            "razorpay_signature": "invalid",
        }))
        self.assert_api_error("missing_payment_fields", lambda: self.service.verify_payment({}))

    def test_cod_is_server_authoritative_and_idempotent(self) -> None:
        payload = self.payload(paymentMethod="cod")
        first = self.service.place_cod_order(payload, "checkout-cod-001")
        second = self.service.place_cod_order(payload, "checkout-cod-001")
        self.assertEqual(first["order"]["grandTotal"], 1072)
        self.assertEqual(first["order"]["paymentStatus"], "pending")
        self.assertTrue(second["idempotent"])
        self.assertEqual(self.service.store.state["inventory"]["sd-prod-001-var-2"], 13)

    def test_payment_captured_success_and_duplicate(self) -> None:
        created = self.create_payment("webhook-captured-001")
        body = self.webhook_body(created, "pay_captured_001")
        first = self.deliver(body)
        second = self.deliver(body)
        self.assertFalse(first.get("duplicate", False))
        self.assertTrue(second["duplicate"])
        self.assertEqual(self.service.store.state["inventory"]["sd-prod-001-var-2"], 13)

    def test_order_paid_success_and_duplicate(self) -> None:
        created = self.create_payment("webhook-orderpaid-001")
        body = self.webhook_body(created, "pay_orderpaid_001", "order.paid")
        self.assertEqual(self.deliver(body), {"success": True})
        self.assertTrue(self.deliver(body)["duplicate"])

    def test_captured_and_order_paid_share_finalization(self) -> None:
        created = self.create_payment("webhook-both-001")
        self.deliver(self.webhook_body(created, "pay_both_001"))
        duplicate = self.deliver(self.webhook_body(created, "pay_both_001", "order.paid"))
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(self.service.store.state["inventory"]["sd-prod-001-var-2"], 13)

    def test_browser_then_webhook_and_webhook_then_browser(self) -> None:
        first = self.create_payment("arrival-browser-first")
        self.service.verify_payment(self.browser_verification(first, "pay_browser_first"))
        self.assertTrue(self.deliver(self.webhook_body(first, "pay_browser_first"))["duplicate"])

        second = self.create_payment("arrival-webhook-first")
        self.deliver(self.webhook_body(second, "pay_webhook_first"))
        verified = self.service.verify_payment(self.browser_verification(second, "pay_webhook_first"))
        self.assertTrue(verified["idempotent"])

    def test_repeated_webhooks_decrement_exactly_once(self) -> None:
        payload = self.payload(items=[{"productId": "sd-prod-001", "variantId": "sd-prod-001-var-4", "quantity": 1}])
        created = self.service.create_razorpay_order(payload, "exactly-once-001")
        browser = self.browser_verification(created, "pay_exactly_once")
        self.service.verify_payment(browser)
        for event in ("payment.captured", "order.paid", "payment.captured", "order.paid"):
            self.deliver(self.webhook_body(created, "pay_exactly_once", event))
        self.assertEqual(self.service.store.state["inventory"]["sd-prod-001-var-4"], 14)

    def test_webhook_rejects_amount_currency_and_unknown_order(self) -> None:
        created = self.create_payment("webhook-mismatch-001")
        self.assert_api_error("amount_mismatch", lambda: self.deliver(
            self.webhook_body(created, "pay_wrong_amount", amount=created["amount"] + 1)
        ))
        self.assert_api_error("currency_mismatch", lambda: self.deliver(
            self.webhook_body(created, "pay_wrong_currency", currency="USD")
        ))
        unknown = dict(created, razorpayOrderId="order_unknown")
        self.assert_api_error("order_not_found", lambda: self.deliver(
            self.webhook_body(unknown, "pay_unknown")
        ))

    def test_payment_failed_does_not_commit_or_revert_paid(self) -> None:
        created = self.create_payment("webhook-failed-001")
        failed = self.webhook_body(created, "pay_failed_001", "payment.failed", status="failed")
        self.assertEqual(self.deliver(failed), {"success": True})
        order = self.service.store.state["orders"][created["styleDashOrderId"]]
        self.assertEqual(order["paymentStatus"], "pending")
        self.assertNotIn("sd-prod-001-var-2", self.service.store.state["inventory"])
        self.service.verify_payment(self.browser_verification(created, "pay_success_after_failure"))
        self.deliver(failed)
        order = self.service.store.state["orders"][created["styleDashOrderId"]]
        self.assertEqual(order["paymentStatus"], "paid")
        self.assertEqual(self.service.store.state["inventory"]["sd-prod-001-var-2"], 13)

    def test_unknown_signed_event_is_ignored(self) -> None:
        body = b'{"event":"refund.processed","payload":{}}'
        self.assertEqual(self.deliver(body), {"success": True})

    def test_negative_inventory_is_prevented(self) -> None:
        created = self.create_payment("negative-stock-001")
        with self.service.store.lock:
            self.service.store.state["inventory"]["sd-prod-001-var-2"] = 1
            self.service.store.save()
        self.assert_api_error("stock_changed", lambda: self.deliver(
            self.webhook_body(created, "pay_no_stock")
        ))
        self.assertEqual(self.service.store.state["inventory"]["sd-prod-001-var-2"], 1)
        self.assertEqual(
            self.service.store.state["orders"][created["styleDashOrderId"]]["paymentStatus"], "pending"
        )

    def test_concurrent_browser_and_webhook_finalize_once(self) -> None:
        created = self.create_payment("concurrent-finalize-001")
        browser = self.browser_verification(created, "pay_concurrent")
        body = self.webhook_body(created, "pay_concurrent")
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda callback: callback(), [
                lambda: self.service.verify_payment(browser),
                lambda: self.deliver(body),
            ]))
        self.assertEqual(len(results), 2)
        self.assertEqual(self.service.store.state["inventory"]["sd-prod-001-var-2"], 13)
        self.assertEqual(len(self.service.store.state["processedPayments"]), 1)

    def test_restart_preserves_payment_idempotency(self) -> None:
        created = self.create_payment("restart-idempotency-001")
        body = self.webhook_body(created, "pay_restart")
        self.deliver(body)
        restarted = SERVER.PaymentService(
            ROOT / "server" / "payment-data" / "catalog.json",
            ROOT / "server" / "payment-data" / "settings.json",
            self.data_directory,
            key_id="rzp_test_placeholder",
            key_secret="test_secret_placeholder",
            webhook_secret="webhook_secret_placeholder",
            mode="test",
            gateway=self.gateway,
        )
        signature = hmac.new(b"webhook_secret_placeholder", body, hashlib.sha256).hexdigest()
        self.assertTrue(restarted.process_webhook(body, signature)["duplicate"])
        self.assertEqual(restarted.store.state["inventory"]["sd-prod-001-var-2"], 13)


class HttpApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        web_root = root / "web"
        web_root.mkdir()
        (web_root / "index.html").write_text("<!doctype html><title>StyleDash</title>", encoding="utf-8")
        service = SERVER.PaymentService(
            ROOT / "server" / "payment-data" / "catalog.json",
            ROOT / "server" / "payment-data" / "settings.json",
            root / "data",
            key_id="rzp_test_placeholder",
            key_secret="test_secret_placeholder",
            webhook_secret="webhook_secret_placeholder",
            mode="test",
            gateway=FakeGateway(),
            security_store=SERVER.SecurityStore(root / "styledash.db", Fernet.generate_key().decode()),
        )
        self.previous_origin = os.environ.get("STYLEDASH_PUBLIC_ORIGIN")
        os.environ["STYLEDASH_PUBLIC_ORIGIN"] = "https://styledash.test"
        self.service = service
        self.server = SERVER.create_server(
            "127.0.0.1", 0, web_root,
            ROOT / "server" / "payment-data" / "catalog.json",
            ROOT / "server" / "payment-data" / "settings.json",
            root / "data",
            service=service,
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        if self.previous_origin is None:
            os.environ.pop("STYLEDASH_PUBLIC_ORIGIN", None)
        else:
            os.environ["STYLEDASH_PUBLIC_ORIGIN"] = self.previous_origin
        self.temporary.cleanup()

    def test_health_and_security_headers(self) -> None:
        with urllib.request.urlopen(f"{self.base_url}/api/health") as response:
            payload = json.load(response)
            self.assertEqual(payload, {"status": "ok", "service": "StyleDash", "paymentMode": "test", "database": "ok"})
            self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
            self.assertIn("checkout.razorpay.com", response.headers["Content-Security-Policy"])

    def test_malformed_json_returns_safe_400(self) -> None:
        request = urllib.request.Request(
            f"{self.base_url}/api/create-order",
            data=b"{not-json",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(request)
        self.assertEqual(caught.exception.code, 400)
        payload = json.loads(caught.exception.read())
        caught.exception.close()
        self.assertEqual(payload["code"], "malformed_request")
        self.assertNotIn("traceback", json.dumps(payload).lower())

    def post_webhook(self, body: bytes, signature: str | None = None):
        headers = {"Content-Type": "application/json"}
        if signature is not None:
            headers["X-Razorpay-Signature"] = signature
        request = urllib.request.Request(
            f"{self.base_url}/api/webhooks/razorpay",
            data=body,
            headers=headers,
            method="POST",
        )
        try:
            response = urllib.request.urlopen(request)
        except urllib.error.HTTPError as error:
            payload = json.loads(error.read())
            status = error.code
            error.close()
            return status, payload
        with response:
            return response.status, json.load(response)

    def test_webhook_route_missing_and_invalid_signature(self) -> None:
        body = b'{"event":"unknown.event","payload":{}}'
        status, payload = self.post_webhook(body)
        self.assertEqual(status, 400)
        self.assertEqual(payload["code"], "missing_webhook_signature")
        status, payload = self.post_webhook(body, "deliberately-invalid")
        self.assertEqual(status, 401)
        self.assertEqual(payload["code"], "webhook_signature_mismatch")

    def test_valid_signature_and_unknown_event_return_200(self) -> None:
        body = b'{"event":"refund.processed","payload":{}}'
        signature = hmac.new(b"webhook_secret_placeholder", body, hashlib.sha256).hexdigest()
        status, payload = self.post_webhook(body, signature)
        self.assertEqual(status, 200)
        self.assertEqual(payload, {"success": True})

    def test_signed_malformed_json_returns_400(self) -> None:
        body = b"{not-json"
        signature = hmac.new(b"webhook_secret_placeholder", body, hashlib.sha256).hexdigest()
        status, payload = self.post_webhook(body, signature)
        self.assertEqual(status, 400)
        self.assertEqual(payload["code"], "malformed_request")

    def post_json(self, path: str, payload: dict, headers: dict | None = None):
        request = urllib.request.Request(
            f"{self.base_url}{path}", data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json", **(headers or {})}, method="POST",
        )
        try:
            response = urllib.request.urlopen(request)
        except urllib.error.HTTPError as error:
            body = json.loads(error.read()); status = error.code; response_headers = error.headers; error.close()
            return status, body, response_headers
        with response:
            return response.status, json.load(response), response.headers

    def test_auth_cookie_csrf_public_admin_absent_and_server_user_ownership(self) -> None:
        status, registered, headers = self.post_json("/api/auth/register", {
            "name": "HTTP Customer", "email": "http-customer@example.test",
            "password": "long http test password 123", "phone": "9999999999",
        })
        self.assertEqual(status, 201)
        set_cookie = headers["Set-Cookie"]
        for flag in ("__Host-styledash_session=", "HttpOnly", "Secure", "SameSite=Lax", "Path=/"):
            self.assertIn(flag, set_cookie)
        cookie = set_cookie.split(";", 1)[0]
        csrf = registered["csrfToken"]

        unauthenticated = urllib.request.Request(f"{self.base_url}/api/orders")
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(unauthenticated)
        self.assertEqual(caught.exception.code, 401); caught.exception.close()

        customer_admin = urllib.request.Request(f"{self.base_url}/api/admin/orders", headers={"Cookie": cookie})
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(customer_admin)
        self.assertEqual(caught.exception.code, 404); caught.exception.close()

        public_admin_ui = urllib.request.Request(f"{self.base_url}/admin")
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(public_admin_ui)
        self.assertEqual(caught.exception.code, 404); caught.exception.close()

        payment_payload = {
            "items": [{"productId": "sd-prod-001", "variantId": "sd-prod-001-var-2", "quantity": 1}],
            "address": {"name": "HTTP Customer", "phone": "9999999999", "street": "123 Test Street", "city": "Neemuch", "pincode": "458441"},
            "deliveryMethod": "express", "paymentMethod": "upi", "userId": "attacker-controlled-user",
        }
        base_headers = {"Cookie": cookie, "X-CSRF-Token": csrf, "Idempotency-Key": "http-auth-test"}
        status, body, _headers = self.post_json("/api/create-order", payment_payload, {**base_headers, "Origin": "https://evil.test"})
        self.assertEqual((status, body["code"]), (403, "invalid_origin"))
        status, body, _headers = self.post_json("/api/create-order", payment_payload, {**base_headers, "Origin": "https://styledash.test"})
        self.assertEqual(status, 201)
        stored = self.service.store.state["orders"][body["styleDashOrderId"]]
        self.assertEqual(stored["userId"], registered["user"]["id"])
        self.assertNotEqual(stored["userId"], "attacker-controlled-user")

        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(f"{self.base_url}/styledash.db")
        self.assertEqual(caught.exception.code, 404); caught.exception.close()
        for private_path in ("/serve.py", "/styledash_security.py", "/tools/set_admin.py"):
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(f"{self.base_url}{private_path}")
            self.assertEqual(caught.exception.code, 404); caught.exception.close()

        patch_admin = urllib.request.Request(
            f"{self.base_url}/api/admin/orders/ORDER/status", data=b'{"status":"delivered"}',
            headers={"Content-Type": "application/json"}, method="PATCH",
        )
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(patch_admin)
        self.assertEqual(caught.exception.code, 404); caught.exception.close()

        oversized = urllib.request.Request(
            f"{self.base_url}/api/auth/register", data=b"{}",
            headers={"Content-Type": "application/json", "Content-Length": str(SERVER.MAX_BODY_BYTES + 1)}, method="POST",
        )
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(oversized)
        self.assertEqual(caught.exception.code, 413); caught.exception.close()


if __name__ == "__main__":
    unittest.main()
