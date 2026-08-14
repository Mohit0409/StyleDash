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
import urllib.parse
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
        self.payments: dict[str, dict] = {}

    def create_order(self, payload: dict) -> dict:
        self.calls.append(payload)
        return {"id": f"order_test_{len(self.calls):03d}"}

    def fetch_payment(self, payment_id: str) -> dict:
        return dict(self.payments[payment_id])


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

    def browser_verification(self, created: dict, payment_id: str, status: str = "captured") -> dict:
        self.gateway.payments[payment_id] = {
            "id": payment_id,
            "order_id": created["razorpayOrderId"],
            "amount": created["amount"],
            "currency": created["currency"],
            "status": status,
        }
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

    def operational_webhook_body(
        self,
        created: dict,
        payment_id: str,
        event: str,
        entity_id: str,
    ) -> bytes:
        entity_name = "refund" if event == "refund.failed" else "dispute"
        payload = {
            "event": event,
            "payload": {
                "payment": {"entity": {
                    "id": payment_id,
                    "order_id": created["razorpayOrderId"],
                    "status": "captured",
                }},
                entity_name: {"entity": {
                    "id": entity_id,
                    "payment_id": payment_id,
                    "status": "failed" if event == "refund.failed" else "open",
                }},
            },
        }
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

    def test_rejects_forged_wallet_without_business_mutation(self) -> None:
        state_before = json.loads(json.dumps(self.service.store.state))
        gateway_calls_before = list(self.gateway.calls)

        self.assert_api_error(
            "wallet_unavailable",
            lambda: self.service.create_razorpay_order(
                self.payload(walletAmount=100), "forged-wallet-online-001"
            ),
        )
        self.assert_api_error(
            "wallet_unavailable",
            lambda: self.service.place_cod_order(
                self.payload(walletAmount=100, paymentMethod="cod"), "forged-wallet-cod-001"
            ),
        )

        self.assertEqual(self.service.store.state, state_before)
        self.assertEqual(self.gateway.calls, gateway_calls_before)

    def test_historical_zero_wallet_order_remains_publicly_readable(self) -> None:
        historical = {
            "id": "SD-HISTORICAL-WALLET-ZERO",
            "userId": "test-user",
            "walletAmount": 0,
            "paymentStatus": "paid",
        }

        self.assertEqual(self.service._public_order(historical), historical)

    def test_rejects_insufficient_stock_and_unsupported_pincode(self) -> None:
        self.assert_api_error("insufficient_stock", lambda: self.service.calculate_order(self.payload(
            items=[{"productId": "sd-prod-001", "variantId": "sd-prod-001-var-7", "quantity": 1}],
        )))
        address = dict(self.payload()["address"], pincode="458440")
        self.assert_api_error("unsupported_pincode", lambda: self.service.calculate_order(self.payload(address=address)))

    def test_public_inventory_availability_is_safe_fresh_and_read_only(self) -> None:
        state_before = json.loads(json.dumps(self.service.store.state))
        first = self.service.public_inventory_availability("sd-prod-001-var-2")
        self.assertEqual(first, {"success": True, "availability": [{
            "productId": "sd-prod-001", "variantId": "sd-prod-001-var-2", "available": True,
        }]})
        self.assertEqual(self.service.store.state, state_before)
        self.assertNotIn("stock", json.dumps(first))
        self.assertNotIn("price", json.dumps(first))
        self.assertNotIn("sku", json.dumps(first))

        with self.service.store.lock:
            self.service.store.state["inventory"]["sd-prod-001-var-2"] = 0
            self.service.store.save()
        changed = self.service.public_inventory_availability("sd-prod-001-var-2")
        self.assertFalse(changed["availability"][0]["available"])

        state_after_stock_change = json.loads(json.dumps(self.service.store.state))
        self.assert_api_error("insufficient_stock", lambda: self.service.create_razorpay_order(
            self.payload(), "inventory-insufficient-stock-001",
        ))
        self.assertEqual(self.service.store.state, state_after_stock_change)
        self.assertEqual(self.gateway.calls, [])

    def test_public_inventory_availability_rejects_invalid_variant_safely(self) -> None:
        state_before = json.loads(json.dumps(self.service.store.state))
        for variant_id in ("", 42, "x" * 129):
            self.assert_api_error(
                "invalid_variant",
                lambda variant_id=variant_id: self.service.public_inventory_availability(variant_id),
            )
        self.assertEqual(self.service.store.state, state_before)

    def test_serviceability_uses_same_authority_as_checkout(self) -> None:
        supported = self.service.check_serviceability("458441")
        unsupported = self.service.check_serviceability("458440")

        self.assertTrue(supported["serviceable"])
        self.assertEqual(supported["city"], "Neemuch")
        self.assertFalse(unsupported["serviceable"])
        self.assertNotIn("supportedPincodes", json.dumps(supported))
        self.assertNotIn("458442", json.dumps(supported))

        self.service.calculate_order(self.payload())
        address = dict(self.payload()["address"], pincode="458440")
        self.assert_api_error("unsupported_pincode", lambda: self.service.calculate_order(self.payload(address=address)))

    def test_serviceability_rejects_malformed_pincodes_safely(self) -> None:
        malformed = (
            "", "1", "45844", "4584411", "abcdef", "45844a", "45 8441", "+458441", "458-441",
            " 458441", "458441 ", "458\t441", "458441\t", "458441\n", "458441\r",
            "４５８４４１", "45844١", "४५८४४१",
        )
        for pincode in malformed:
            self.assert_api_error(
                "invalid_pincode",
                lambda pincode=pincode: self.service.check_serviceability(pincode),
            )

    def test_checkout_rejects_noncanonical_pincodes_without_mutation(self) -> None:
        malformed = (
            "", "1", "45844", "4584411", "abcdef", "45844a", "45 8441", "+458441", "458-441",
            " 458441", "458441 ", "458\t441", "458441\t", "458441\n", "458441\r",
            "４５８４４１", "45844١", "४५८४४१",
        )
        for pincode in malformed:
            state_before = json.loads(json.dumps(self.service.store.state))
            gateway_calls_before = list(self.gateway.calls)
            address = dict(self.payload()["address"], pincode=pincode)
            self.assert_api_error(
                "unsupported_pincode",
                lambda address=address: self.service.create_razorpay_order(
                    self.payload(address=address), "invalid-pincode-001"
                ),
            )
            self.assertEqual(self.service.store.state, state_before)
            self.assertEqual(self.gateway.calls, gateway_calls_before)

    def test_supported_pincode_environment_override_drives_public_check_and_checkout(self) -> None:
        previous = os.environ.get("STYLEDASH_SUPPORTED_PINCODES")
        os.environ["STYLEDASH_SUPPORTED_PINCODES"] = "111111,222222"
        try:
            overridden = SERVER.PaymentService(
                ROOT / "server" / "payment-data" / "catalog.json",
                ROOT / "server" / "payment-data" / "settings.json",
                self.data_directory,
                key_id="rzp_test_placeholder",
                key_secret="test_secret_placeholder",
                webhook_secret="webhook_secret_placeholder",
                mode="test",
                gateway=self.gateway,
            )
        finally:
            if previous is None:
                os.environ.pop("STYLEDASH_SUPPORTED_PINCODES", None)
            else:
                os.environ["STYLEDASH_SUPPORTED_PINCODES"] = previous

        self.assertTrue(overridden.check_serviceability("111111")["serviceable"])
        self.assertFalse(overridden.check_serviceability("458441")["serviceable"])
        overridden.calculate_order(self.payload(address=dict(self.payload()["address"], pincode="111111")))
        self.assert_api_error(
            "unsupported_pincode",
            lambda: overridden.calculate_order(self.payload()),
        )

    def test_unsupported_checkout_has_no_business_mutation(self) -> None:
        state_before = json.loads(json.dumps(self.service.store.state))
        gateway_calls_before = list(self.gateway.calls)
        address = dict(self.payload()["address"], pincode="458440")

        self.assert_api_error(
            "unsupported_pincode",
            lambda: self.service.create_razorpay_order(
                self.payload(address=address), "unsupported-pincode-001"
            ),
        )

        self.assertEqual(self.service.store.state, state_before)
        self.assertEqual(self.gateway.calls, gateway_calls_before)

    def test_verifies_signature_and_decrements_inventory_once(self) -> None:
        created = self.service.create_razorpay_order(self.payload(), "checkout-test-003")
        payment_id = "pay_test_001"
        verification = self.browser_verification(created, payment_id)

        first = self.service.verify_payment(verification)
        stock_after_first = self.service.store.state["inventory"]["sd-prod-001-var-2"]
        second = self.service.verify_payment(verification)

        self.assertTrue(first["success"])
        self.assertEqual(first["order"]["paymentStatus"], "paid")
        self.assertEqual(stock_after_first, 13)
        self.assertTrue(second["idempotent"])
        self.assertEqual(self.service.store.state["inventory"]["sd-prod-001-var-2"], 13)

    def test_authorized_browser_payment_remains_pending_until_captured_webhook(self) -> None:
        created = self.create_payment("authorized-browser-001")
        payment_id = "pay_authorized_001"
        verification = self.browser_verification(created, payment_id, status="authorized")

        first = self.service.verify_payment(verification)
        second = self.service.verify_payment(verification)
        order = self.service.store.state["orders"][created["styleDashOrderId"]]
        self.assertTrue(first["pending"])
        self.assertTrue(second["pending"])
        self.assertTrue(second["idempotent"])
        self.assertEqual(order["paymentStatus"], "pending")
        self.assertNotIn("sd-prod-001-var-2", self.service.store.state["inventory"])
        self.assertNotIn(payment_id, self.service.store.state["processedPayments"])

        captured = self.deliver(self.webhook_body(created, payment_id))
        self.assertEqual(captured, {"success": True})
        order = self.service.store.state["orders"][created["styleDashOrderId"]]
        self.assertEqual(order["paymentStatus"], "paid")
        self.assertEqual(self.service.store.state["inventory"]["sd-prod-001-var-2"], 13)

    def test_browser_verification_rejects_non_captured_gateway_state(self) -> None:
        created = self.create_payment("not-captured-browser-001")
        verification = self.browser_verification(created, "pay_failed_fetch", status="failed")
        self.assert_api_error("payment_not_captured", lambda: self.service.verify_payment(verification))
        order = self.service.store.state["orders"][created["styleDashOrderId"]]
        self.assertEqual(order["paymentStatus"], "pending")
        self.assertNotIn("sd-prod-001-var-2", self.service.store.state["inventory"])

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

    def test_refund_failed_records_one_private_alert_without_business_mutation(self) -> None:
        created = self.create_payment("refund-failed-001")
        payment_id = "pay_refund_failed_001"
        self.deliver(self.webhook_body(created, payment_id))
        order = self.service.store.state["orders"][created["styleDashOrderId"]]
        inventory_before = dict(self.service.store.state["inventory"])
        history_before = list(order["statusHistory"])
        body = self.operational_webhook_body(created, payment_id, "refund.failed", "rfnd_failed_001")
        signature = hmac.new(b"webhook_secret_placeholder", body, hashlib.sha256).hexdigest()

        first = self.service.process_webhook(body, signature, "event-refund-001")
        retry = self.service.process_webhook(body, signature, "event-refund-001")
        redelivery = self.service.process_webhook(body, signature, "event-refund-redelivery")
        order = self.service.store.state["orders"][created["styleDashOrderId"]]

        self.assertEqual(first, {"success": True})
        self.assertTrue(retry["duplicate"])
        self.assertTrue(redelivery["duplicate"])
        self.assertEqual(len(self.service.store.state["operationalAlerts"]), 1)
        self.assertTrue(order["requiresAdminAttention"])
        self.assertTrue(order["refundFailureAttention"])
        self.assertEqual(order["paymentStatus"], "paid")
        self.assertEqual(order["statusHistory"], history_before)
        self.assertEqual(self.service.store.state["inventory"], inventory_before)

    def test_payment_dispute_created_flags_paid_order_without_refund_or_inventory_change(self) -> None:
        created = self.create_payment("payment-dispute-001")
        payment_id = "pay_dispute_001"
        self.deliver(self.webhook_body(created, payment_id))
        order = self.service.store.state["orders"][created["styleDashOrderId"]]
        inventory_before = dict(self.service.store.state["inventory"])
        history_before = list(order["statusHistory"])
        body = self.operational_webhook_body(
            created, payment_id, "payment.dispute.created", "disp_created_001"
        )
        signature = hmac.new(b"webhook_secret_placeholder", body, hashlib.sha256).hexdigest()

        first = self.service.process_webhook(body, signature, "event-dispute-001")
        retry = self.service.process_webhook(body, signature, "event-dispute-001")
        order = self.service.store.state["orders"][created["styleDashOrderId"]]

        self.assertEqual(first, {"success": True})
        self.assertTrue(retry["duplicate"])
        self.assertTrue(order["requiresAdminAttention"])
        self.assertTrue(order["paymentDisputed"])
        self.assertEqual(order["paymentDisputeId"], "disp_created_001")
        self.assertEqual(order["paymentStatus"], "paid")
        self.assertEqual(order["statusHistory"], history_before)
        self.assertEqual(self.service.store.state["inventory"], inventory_before)

    def test_operational_alert_for_unknown_payment_is_preserved_for_admin_review(self) -> None:
        created = self.create_payment("unknown-refund-alert-001")
        webhook = json.loads(self.operational_webhook_body(
            created, "pay_not_in_styledash", "refund.failed", "rfnd_unknown_001"
        ))
        webhook["payload"]["payment"]["entity"]["order_id"] = "order_not_in_styledash"
        body = json.dumps(webhook, separators=(",", ":")).encode()
        signature = hmac.new(b"webhook_secret_placeholder", body, hashlib.sha256).hexdigest()
        self.assertEqual(
            self.service.process_webhook(body, signature, "event-refund-unknown"),
            {"success": True},
        )
        alert = self.service.store.state["operationalAlerts"]["refund.failed:rfnd_unknown_001"]
        self.assertIsNone(alert["styleDashOrderId"])

    def test_payment_authorized_webhook_never_fulfills(self) -> None:
        created = self.create_payment("authorized-webhook-001")
        body = self.webhook_body(
            created, "pay_authorized_webhook", "payment.authorized", status="authorized"
        )
        self.assertEqual(self.deliver(body), {"success": True})
        order = self.service.store.state["orders"][created["styleDashOrderId"]]
        self.assertEqual(order["paymentStatus"], "pending")
        self.assertNotIn("sd-prod-001-var-2", self.service.store.state["inventory"])

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
        self.reset_deliveries = []
        security_store = SERVER.SecurityStore(
            root / "styledash.db", Fernet.generate_key().decode(),
            password_reset_sender=lambda email, token: self.reset_deliveries.append((email, token)),
        )
        service = SERVER.PaymentService(
            ROOT / "server" / "payment-data" / "catalog.json",
            ROOT / "server" / "payment-data" / "settings.json",
            root / "data",
            key_id="rzp_test_placeholder",
            key_secret="test_secret_placeholder",
            webhook_secret="webhook_secret_placeholder",
            mode="test",
            gateway=FakeGateway(),
            security_store=security_store,
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

    def post_webhook(self, body: bytes, signature: str | None = None, event_id: str | None = None):
        headers = {"Content-Type": "application/json"}
        if signature is not None:
            headers["X-Razorpay-Signature"] = signature
        if event_id is not None:
            headers["X-Razorpay-Event-Id"] = event_id
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

    def test_event_id_header_makes_operational_webhook_http_route_idempotent(self) -> None:
        body = json.dumps({
            "event": "refund.failed",
            "payload": {
                "payment": {"entity": {"id": "pay_http_alert", "order_id": "order_http_alert"}},
                "refund": {"entity": {
                    "id": "rfnd_http_alert", "payment_id": "pay_http_alert", "status": "failed",
                }},
            },
        }, separators=(",", ":")).encode()
        signature = hmac.new(b"webhook_secret_placeholder", body, hashlib.sha256).hexdigest()
        first_status, first = self.post_webhook(body, signature, "event-http-alert")
        second_status, second = self.post_webhook(body, signature, "event-http-alert")
        self.assertEqual((first_status, first), (200, {"success": True}))
        self.assertEqual(second_status, 200)
        self.assertTrue(second["duplicate"])
        self.assertEqual(len(self.service.store.state["operationalAlerts"]), 1)

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

    def get_json(self, path: str):
        try:
            response = urllib.request.urlopen(f"{self.base_url}{path}")
        except urllib.error.HTTPError as error:
            body = json.loads(error.read()); status = error.code; response_headers = error.headers; error.close()
            return status, body, response_headers
        with response:
            return response.status, json.load(response), response.headers

    def test_public_serviceability_endpoint_is_read_only_and_safe(self) -> None:
        state_before = json.loads(json.dumps(self.service.store.state))

        status, supported, _headers = self.get_json("/api/serviceability?pincode=458441")
        self.assertEqual(status, 200)
        self.assertEqual(supported["serviceable"], True)
        self.assertEqual(supported["city"], "Neemuch")
        self.assertEqual(supported["estimatedDeliveryMinutes"], 60)

        status, unsupported, _headers = self.get_json("/api/serviceability?pincode=458440")
        self.assertEqual(status, 200)
        self.assertEqual(unsupported, {"success": True, "pincode": "458440", "serviceable": False})

        malformed_pincodes = (
            "", "1", "45844", "4584411", "abcdef", "45844a", "45 8441", "+458441", "458-441",
            " 458441", "458441 ", "458\t441", "458441\t", "458441\n", "458441\r",
            "４５８４４１", "45844١", "४५८४४१",
        )
        for pincode in malformed_pincodes:
            encoded = urllib.parse.quote(pincode, safe="")
            status, malformed, _headers = self.get_json(f"/api/serviceability?pincode={encoded}")
            self.assertEqual(status, 400, pincode)
            self.assertEqual(malformed["code"], "invalid_pincode", pincode)
            self.assertNotIn("traceback", json.dumps(malformed).lower(), pincode)

        status, _body, _headers = self.post_json("/api/serviceability?pincode=458441", {})
        self.assertEqual(status, 404)
        self.assertEqual(self.service.store.state, state_before)

        serialized = json.dumps(supported) + json.dumps(unsupported)
        self.assertNotIn("supportedPincodes", serialized)
        self.assertNotIn("458442", serialized)

    def test_public_inventory_endpoint_is_read_only_safe_and_current(self) -> None:
        state_before = json.loads(json.dumps(self.service.store.state))
        status, payload, _headers = self.get_json("/api/inventory/availability?variantId=sd-prod-001-var-2")
        self.assertEqual(status, 200)
        self.assertEqual(payload, {"success": True, "availability": [{
            "productId": "sd-prod-001", "variantId": "sd-prod-001-var-2", "available": True,
        }]})
        self.assertEqual(self.service.store.state, state_before)
        self.assertNotIn("stock", json.dumps(payload))
        self.assertNotIn("price", json.dumps(payload))
        self.assertNotIn("sku", json.dumps(payload))

        with self.service.store.lock:
            self.service.store.state["inventory"]["sd-prod-001-var-2"] = 0
            self.service.store.save()
        status, changed, _headers = self.get_json("/api/inventory/availability?variantId=sd-prod-001-var-2")
        self.assertEqual(status, 200)
        self.assertFalse(changed["availability"][0]["available"])

        status, invalid, _headers = self.get_json("/api/inventory/availability?variantId=&variantId=duplicate")
        self.assertEqual((status, invalid["code"]), (400, "invalid_variant"))
        status, _body, _headers = self.post_json("/api/inventory/availability", {})
        self.assertEqual(status, 404)

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

    def test_password_reset_http_is_generic_rate_limited_and_never_returns_tokens(self) -> None:
        registered_payload = {
            "name": "Recovery Customer", "email": "recovery@example.test",
            "password": "long recovery password 123", "phone": "9999999999",
        }
        self.assertEqual(self.post_json("/api/auth/register", registered_payload)[0], 201)
        status, known, _headers = self.post_json("/api/auth/password-reset/request", {"email": "recovery@example.test"})
        self.assertEqual(status, 200)
        status, unknown, _headers = self.post_json("/api/auth/password-reset/request", {"email": "unknown@example.test"})
        self.assertEqual((status, unknown), (200, known))
        status, invalid_email, _headers = self.post_json("/api/auth/password-reset/request", {"email": "not an email"})
        self.assertEqual((status, invalid_email), (200, known))
        self.assertEqual(len(self.reset_deliveries), 1)
        token = self.reset_deliveries[0][1]
        self.assertNotIn(token, json.dumps(known))
        with self.service.security.connect() as db:
            self.assertIsNone(db.execute("SELECT 1 FROM password_reset_tokens WHERE token_hash=?", (token,)).fetchone())

        status, invalid, _headers = self.post_json("/api/auth/password-reset/confirm", {"token": "not-a-real-token", "newPassword": "new recovery password 456"})
        self.assertEqual((status, invalid["code"]), (400, "invalid_reset_token"))
        status, confirmed, _headers = self.post_json("/api/auth/password-reset/confirm", {"token": token, "newPassword": "new recovery password 456"})
        self.assertEqual(status, 200)
        self.assertNotIn(token, json.dumps(confirmed))
        self.assertEqual(self.post_json("/api/auth/login", {"email": "recovery@example.test", "password": "new recovery password 456"})[0], 200)

        for _ in range(2):
            self.post_json("/api/auth/password-reset/request", {"email": "unknown@example.test"})
        status, limited, _headers = self.post_json("/api/auth/password-reset/request", {"email": "unknown@example.test"})
        self.assertEqual((status, limited["code"]), (429, "rate_limited"))

    def test_password_reset_rate_limits_hashed_email_across_distinct_client_ips(self) -> None:
        previous = os.environ.get("STYLEDASH_TRUST_LOOPBACK_PROXY")
        os.environ["STYLEDASH_TRUST_LOOPBACK_PROXY"] = "1"
        try:
            payload = {"email": "rate-limit@example.test"}
            for suffix in range(1, 4):
                status, body, _headers = self.post_json(
                    "/api/auth/password-reset/request", payload,
                    {"X-Forwarded-For": f"198.51.100.{suffix}"},
                )
                self.assertEqual((status, body), (200, {"success": True, "message": "If an account exists, reset instructions will be sent shortly."}))
            status, limited, _headers = self.post_json(
                "/api/auth/password-reset/request", payload,
                {"X-Forwarded-For": "198.51.100.4"},
            )
            self.assertEqual((status, limited["code"]), (429, "rate_limited"))
        finally:
            if previous is None:
                os.environ.pop("STYLEDASH_TRUST_LOOPBACK_PROXY", None)
            else:
                os.environ["STYLEDASH_TRUST_LOOPBACK_PROXY"] = previous


if __name__ == "__main__":
    unittest.main()
