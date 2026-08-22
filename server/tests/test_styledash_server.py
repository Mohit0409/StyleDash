from __future__ import annotations

import hashlib
import hmac
import importlib.util
import io
import json
import os
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

from cryptography.fernet import Fernet

from scripts import styledash_notify as NOTIFY


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

    def test_catalog_refresh_does_not_take_payment_state_file_lock(self) -> None:
        class ForbiddenStateLock:
            def __enter__(self):
                raise AssertionError("catalog refresh entered the payment-state lock")

            def __exit__(self, *_args):
                return False

        original = self.service.store.lock
        self.service.store.lock = ForbiddenStateLock()
        try:
            self.service.refresh_shop_products()
        finally:
            self.service.store.lock = original

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

    def test_payment_notification_is_exactly_once_across_callback_and_webhook(self) -> None:
        created = self.create_payment(
            "payment-notification-exactly-once"
        )

        callback = self.browser_verification(
            created,
            "pay_notification_exactly_once",
        )

        with patch.object(
            SERVER,
            "owner_notifier",
        ) as notifier_factory:
            notifier = notifier_factory.return_value

            first = self.service.verify_payment(callback)

            self.assertFalse(first["idempotent"])
            self.assertEqual(
                first["order"]["paymentStatus"],
                "paid",
            )
            self.assertEqual(
                notifier.send.call_count,
                1,
            )

            body = self.webhook_body(
                created,
                "pay_notification_exactly_once",
                event="order.paid",
            )

            duplicate = self.deliver(body)

            self.assertTrue(duplicate["duplicate"])

            # payment.captured/browser callback + order.paid
            # still results in one phone notification.
            self.assertEqual(
                notifier.send.call_count,
                1,
            )

            notification = notifier.send.call_args.kwargs

            self.assertEqual(
                notification["event"],
                "payment_captured",
            )
            self.assertEqual(
                notification["priority"],
                5,
            )
            self.assertIn(
                first["order"]["id"],
                notification["message"],
            )
            self.assertIn(
                f"?{first['order']['grandTotal']}",
                notification["message"],
            )
            self.assertIn(
                "Status: Paid",
                notification["message"],
            )

    def test_payment_review_notification_failure_never_breaks_paid_state(self) -> None:
        created = self.create_payment(
            "payment-notification-review"
        )

        # Simulate stock disappearing after Razorpay order creation
        # but before captured-payment finalization.
        with self.service.store.lock:
            self.service.store.state["inventory"][
                "sd-prod-001-var-2"
            ] = 0
            self.service.store.save()

        callback = self.browser_verification(
            created,
            "pay_notification_review",
        )

        notification_env = {
            "STYLEDASH_NTFY_ENABLED": "true",
            "STYLEDASH_NTFY_BASE_URL": "https://ntfy.test",
            "STYLEDASH_NTFY_TOPIC":
                "styledash-test-private-topic-1234567890",
        }

        captured_notifications = []

        def fail_after_capture(request, timeout=None):
            captured_notifications.append(
                json.loads(request.data.decode("utf-8"))
            )
            raise TimeoutError(
                "simulated payment notification timeout"
            )

        with patch.dict(
            os.environ,
            notification_env,
            clear=False,
        ):
            with patch(
                "scripts.styledash_notify.urlopen",
                side_effect=fail_after_capture,
            ):
                result = self.service.verify_payment(callback)

        # Financial truth survives notification failure.
        self.assertEqual(
            result["order"]["paymentStatus"],
            "paid",
        )
        self.assertEqual(
            result["order"]["status"],
            "payment_review_required",
        )
        self.assertFalse(
            result["order"]["inventoryCommitted"]
        )

        stored = self.service.store.state["orders"][
            created["styleDashOrderId"]
        ]

        self.assertEqual(
            stored["paymentStatus"],
            "paid",
        )
        self.assertEqual(
            stored["status"],
            "payment_review_required",
        )
        self.assertTrue(
            stored["requiresAdminAttention"]
        )

        # We attempted exactly one urgent owner alert.
        self.assertEqual(
            len(captured_notifications),
            1,
        )

        notification = captured_notifications[0]

        self.assertEqual(
            notification["title"],
            "PAYMENT NEEDS ATTENTION",
        )
        self.assertEqual(
            notification["priority"],
            5,
        )
        self.assertIn(
            created["styleDashOrderId"],
            notification["message"],
        )
        self.assertIn(
            "review required",
            notification["message"].lower(),
        )

        # Topic is transport metadata, never human-visible content.
        visible = (
            notification["title"]
            + "\n"
            + notification["message"]
        )

        self.assertNotIn(
            notification_env["STYLEDASH_NTFY_TOPIC"],
            visible,
        )


    def test_payment_failed_notification_is_deduplicated(self) -> None:
        created = self.create_payment(
            "notification-payment-failed"
        )

        body = self.webhook_body(
            created,
            "pay_notify_failed",
            event="payment.failed",
            status="failed",
        )

        with patch.object(SERVER, "owner_notifier") as factory:
            notifier = factory.return_value

            first = self.deliver(body)
            second = self.deliver(body)

            self.assertEqual(first, {"success": True})
            self.assertEqual(second, {"success": True})
            self.assertEqual(notifier.send.call_count, 1)

            notification = notifier.send.call_args.kwargs

            self.assertEqual(
                notification["event"],
                "payment_failed",
            )
            self.assertIn(
                created["styleDashOrderId"],
                notification["message"],
            )
            self.assertNotIn(
                "pay_notify_failed",
                notification["message"],
            )

    def test_refund_processed_notification_is_exactly_once(self) -> None:
        created = self.create_payment(
            "notification-refund-processed"
        )

        callback = self.browser_verification(
            created,
            "pay_notify_refund",
        )

        with patch.object(SERVER, "owner_notifier") as factory:
            notifier = factory.return_value

            paid = self.service.verify_payment(callback)
            self.assertEqual(
                paid["order"]["paymentStatus"],
                "paid",
            )

            # Ignore the initial payment-received notification.
            notifier.send.reset_mock()

            refund_body = json.dumps({
                "event": "refund.processed",
                "payload": {
                    "payment": {
                        "entity": {
                            "id": "pay_notify_refund",
                            "order_id": created["razorpayOrderId"],
                            "amount": created["amount"],
                            "amount_refunded": created["amount"],
                            "currency": created["currency"],
                            "status": "captured",
                        }
                    },
                    "refund": {
                        "entity": {
                            "id": "rfnd_notify_full",
                            "payment_id": "pay_notify_refund",
                            "amount": created["amount"],
                            "currency": created["currency"],
                            "status": "processed",
                        }
                    },
                },
            }, separators=(",", ":")).encode()

            first = self.deliver(refund_body)
            second = self.deliver(refund_body)

            self.assertEqual(first, {"success": True})
            self.assertTrue(second["duplicate"])
            self.assertEqual(notifier.send.call_count, 1)

            notification = notifier.send.call_args.kwargs

            self.assertEqual(
                notification["event"],
                "refund_processed",
            )
            self.assertIn(
                created["styleDashOrderId"],
                notification["message"],
            )
            self.assertIn(
                "Status: Refunded",
                notification["message"],
            )

    def test_refund_failed_notification_is_deduplicated(self) -> None:
        created = self.create_payment(
            "notification-refund-failed"
        )

        callback = self.browser_verification(
            created,
            "pay_notify_refund_failed",
        )

        with patch.object(SERVER, "owner_notifier") as factory:
            notifier = factory.return_value

            self.service.verify_payment(callback)

            # Ignore payment-received notification.
            notifier.send.reset_mock()

            body = self.operational_webhook_body(
                created,
                "pay_notify_refund_failed",
                "refund.failed",
                "rfnd_notify_failed",
            )

            first = self.deliver(body)
            second = self.deliver(body)

            self.assertEqual(first, {"success": True})
            self.assertTrue(second["duplicate"])
            self.assertEqual(notifier.send.call_count, 1)

            notification = notifier.send.call_args.kwargs

            self.assertEqual(
                notification["event"],
                "refund_failed",
            )
            self.assertIn(
                created["styleDashOrderId"],
                notification["message"],
            )
            self.assertNotIn(
                "rfnd_notify_failed",
                notification["message"],
            )


    def test_partial_refund_review_notification_is_exactly_once(self) -> None:
        created = self.create_payment(
            "notification-refund-review"
        )

        callback = self.browser_verification(
            created,
            "pay_notify_refund_review",
        )

        with patch.object(SERVER, "owner_notifier") as factory:
            notifier = factory.return_value

            paid = self.service.verify_payment(callback)
            self.assertEqual(
                paid["order"]["paymentStatus"],
                "paid",
            )

            notifier.send.reset_mock()

            partial_amount = created["amount"] // 2

            body = json.dumps({
                "event": "refund.processed",
                "payload": {
                    "payment": {
                        "entity": {
                            "id": "pay_notify_refund_review",
                            "order_id": created["razorpayOrderId"],
                            "amount": created["amount"],
                            "amount_refunded": partial_amount,
                            "currency": created["currency"],
                            "status": "captured",
                        }
                    },
                    "refund": {
                        "entity": {
                            "id": "rfnd_notify_review",
                            "payment_id": "pay_notify_refund_review",
                            "amount": partial_amount,
                            "currency": created["currency"],
                            "status": "processed",
                        }
                    },
                },
            }, separators=(",", ":")).encode()

            first = self.deliver(body)
            second = self.deliver(body)

            self.assertTrue(first["reviewRequired"])
            self.assertTrue(second["duplicate"])
            self.assertTrue(second["reviewRequired"])

            self.assertEqual(
                notifier.send.call_count,
                1,
            )

            notification = notifier.send.call_args.kwargs

            self.assertEqual(
                notification["event"],
                "refund_review_required",
            )
            self.assertEqual(
                notification["priority"],
                5,
            )
            self.assertEqual(
                notification["title"],
                "REFUND NEEDS ATTENTION",
            )
            self.assertIn(
                created["styleDashOrderId"],
                notification["message"],
            )
            self.assertIn(
                "Review required",
                notification["message"],
            )

    def test_payment_dispute_notification_is_deduplicated(self) -> None:
        created = self.create_payment(
            "notification-payment-dispute"
        )

        callback = self.browser_verification(
            created,
            "pay_notify_dispute",
        )

        with patch.object(SERVER, "owner_notifier") as factory:
            notifier = factory.return_value

            self.service.verify_payment(callback)

            notifier.send.reset_mock()

            body = self.operational_webhook_body(
                created,
                "pay_notify_dispute",
                "payment.dispute.created",
                "disp_notify_001",
            )

            first = self.deliver(body)
            second = self.deliver(body)

            self.assertEqual(first, {"success": True})
            self.assertTrue(second["duplicate"])

            self.assertEqual(
                notifier.send.call_count,
                1,
            )

            notification = notifier.send.call_args.kwargs

            self.assertEqual(
                notification["event"],
                "payment_dispute",
            )
            self.assertEqual(
                notification["priority"],
                5,
            )
            self.assertEqual(
                notification["title"],
                "PAYMENT DISPUTE ALERT",
            )
            self.assertIn(
                created["styleDashOrderId"],
                notification["message"],
            )

            # Only a shortened reference may be visible.
            self.assertNotIn(
                "disp_notify_001",
                notification["message"],
            )


    def test_cod_low_stock_threshold_notifies_only_on_crossing(self) -> None:
        variant_id = "sd-prod-001-var-2"

        with self.service.store.lock:
            self.service.store.state["inventory"][variant_id] = 6
            self.service.store.save()

        payload = self.payload(
                paymentMethod="cod",
                items=[{
                    "productId": "sd-prod-001",
                    "variantId": "sd-prod-001-var-2",
                    "quantity": 1,
                }],
            )

        with patch.object(
            SERVER,
            "owner_notifier",
        ) as notifier_factory:
            notifier = notifier_factory.return_value

            first = self.service.place_cod_order(
                payload,
                "inventory-low-stock-cod-001",
            )

            self.assertFalse(first["idempotent"])
            self.assertEqual(
                self.service.store.state["inventory"][variant_id],
                5,
            )

            self.assertEqual(notifier.send.call_count, 1)

            notification = notifier.send.call_args.kwargs

            self.assertEqual(
                notification["event"],
                "inventory_low_stock",
            )
            self.assertEqual(notification["priority"], 5)
            self.assertIn(
                "Remaining: 5",
                notification["message"],
            )

            # Idempotent retry must not ring again.
            duplicate = self.service.place_cod_order(
                payload,
                "inventory-low-stock-cod-001",
            )

            self.assertTrue(duplicate["idempotent"])
            self.assertEqual(notifier.send.call_count, 1)

            # 5 -> 4 remains inside the low-stock range and must
            # therefore stay silent.
            second = self.service.place_cod_order(
                payload,
                "inventory-low-stock-cod-002",
            )

            self.assertFalse(second["idempotent"])
            self.assertEqual(
                self.service.store.state["inventory"][variant_id],
                4,
            )

            self.assertEqual(notifier.send.call_count, 1)

    def test_out_of_stock_notification_failure_does_not_break_cod(self) -> None:
        variant_id = "sd-prod-001-var-2"

        with self.service.store.lock:
            self.service.store.state["inventory"][variant_id] = 1
            self.service.store.save()

        with patch.object(
            SERVER,
            "owner_notifier",
            side_effect=RuntimeError(
                "simulated inventory notification failure"
            ),
        ):
            result = self.service.place_cod_order(
                self.payload(
                paymentMethod="cod",
                items=[{
                    "productId": "sd-prod-001",
                    "variantId": "sd-prod-001-var-2",
                    "quantity": 1,
                }],
            ),
                "inventory-out-of-stock-failure-001",
            )

        self.assertFalse(result["idempotent"])

        self.assertEqual(
            self.service.store.state["inventory"][variant_id],
            0,
        )

        order_id = result["order"]["id"]

        self.assertIn(
            order_id,
            self.service.store.state["orders"],
        )

        self.assertEqual(
            self.service.store.state["orders"][order_id]["status"],
            "placed",
        )

    def test_captured_payment_low_stock_notification_is_exactly_once(self) -> None:
        variant_id = "sd-prod-001-var-2"

        created = self.create_payment(
            "inventory-payment-low-stock-001",
            items=[{
                "productId": "sd-prod-001",
                "variantId": "sd-prod-001-var-2",
                "quantity": 1,
            }],
        )

        with self.service.store.lock:
            self.service.store.state["inventory"][variant_id] = 6
            self.service.store.save()

        callback = self.browser_verification(
            created,
            "pay_inventory_low_stock",
        )

        with patch.object(
            SERVER,
            "owner_notifier",
        ) as notifier_factory:
            notifier = notifier_factory.return_value

            first = self.service.verify_payment(callback)

            self.assertFalse(first["idempotent"])
            self.assertEqual(
                self.service.store.state["inventory"][variant_id],
                5,
            )

            events = [
                call.kwargs["event"]
                for call in notifier.send.call_args_list
            ]

            self.assertEqual(
                events.count("payment_captured"),
                1,
            )

            self.assertEqual(
                events.count("inventory_low_stock"),
                1,
            )

            calls_before_duplicate = notifier.send.call_count

            duplicate = self.deliver(
                self.webhook_body(
                    created,
                    "pay_inventory_low_stock",
                    event="order.paid",
                )
            )

            self.assertTrue(duplicate["duplicate"])

            self.assertEqual(
                notifier.send.call_count,
                calls_before_duplicate,
            )

            self.assertEqual(
                self.service.store.state["inventory"][variant_id],
                5,
            )

    def test_payment_test_order_never_emits_inventory_alert(self) -> None:
        variant_id = "sd-prod-001-var-2"

        created = self.create_payment(
            "inventory-payment-test-skip-001"
        )

        with self.service.store.lock:
            order = self.service.store.state["orders"][
                created["styleDashOrderId"]
            ]

            # Convert this isolated test fixture into the same
            # no-fulfillment state used by the hidden validation item.
            order["isPaymentTestOrder"] = True
            order["fulfillmentRequired"] = False
            order["inventoryCommitted"] = False

            self.service.store.state["inventory"][variant_id] = 6
            self.service.store.save()

        callback = self.browser_verification(
            created,
            "pay_inventory_payment_test_skip",
        )

        with patch.object(
            SERVER,
            "owner_notifier",
        ) as notifier_factory:
            notifier = notifier_factory.return_value

            result = self.service.verify_payment(callback)

            self.assertEqual(
                result["order"]["status"],
                "payment_test_completed",
            )

            self.assertEqual(
                self.service.store.state["inventory"][variant_id],
                6,
            )

            events = [
                call.kwargs["event"]
                for call in notifier.send.call_args_list
            ]

            self.assertFalse(
                any(
                    event.startswith("inventory_")
                    for event in events
                )
            )


    def test_ntfy_background_delivery_is_non_blocking(self) -> None:
        delivered = threading.Event()

        class Response:
            status = 200

            def __enter__(self):
                return self

            def __exit__(
                self,
                exc_type,
                exc,
                traceback,
            ):
                return False

        def slow_urlopen(
            request,
            timeout=None,
        ):
            time.sleep(0.35)
            delivered.set()
            return Response()

        notifier = NOTIFY.NtfyNotifier(
            enabled=True,
            base_url="https://ntfy.test",
            topic="private-test-topic",
            timeout=1.0,
            background=True,
        )

        with patch(
            "scripts.styledash_notify.urlopen",
            side_effect=slow_urlopen,
        ) as mocked_urlopen:
            started = time.perf_counter()

            queued = notifier.send(
                event="background_test",
                title="Background Test",
                message="Safe test message",
                priority=5,
            )

            elapsed = (
                time.perf_counter()
                - started
            )

            self.assertTrue(queued)

            # Network sleeps for 350ms; enqueueing must
            # return substantially earlier than that.
            self.assertLess(elapsed, 0.20)

            self.assertTrue(
                NOTIFY.wait_for_notifications(
                    timeout=2.0
                )
            )

            self.assertTrue(
                delivered.is_set()
            )

            self.assertEqual(
                mocked_urlopen.call_count,
                1,
            )

    def test_ntfy_background_network_failure_is_isolated(self) -> None:
        notifier = NOTIFY.NtfyNotifier(
            enabled=True,
            base_url="https://ntfy.test",
            topic="private-test-topic",
            timeout=1.0,
            background=True,
        )

        with patch(
            "scripts.styledash_notify.urlopen",
            side_effect=TimeoutError(
                "simulated background timeout"
            ),
        ) as mocked_urlopen:
            queued = notifier.send(
                event="background_failure_test",
                title="Background Failure Test",
                message="Safe test message",
                priority=5,
            )

            self.assertTrue(queued)

            self.assertTrue(
                NOTIFY.wait_for_notifications(
                    timeout=2.0
                )
            )

            self.assertEqual(
                mocked_urlopen.call_count,
                1,
            )


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
        body = b'{"event":"subscription.charged","payload":{}}'
        self.assertEqual(self.deliver(body), {"success": True})

    def test_captured_payment_stock_shortfall_records_paid_review_state(self) -> None:
        created = self.create_payment("negative-stock-001")
        payment_id = "pay_no_stock"
        with self.service.store.lock:
            self.service.store.state["inventory"]["sd-prod-001-var-2"] = 1
            self.service.store.save()
        first = self.deliver(self.webhook_body(created, payment_id))
        self.assertEqual(first, {"success": True})
        order = self.service.store.state["orders"][created["styleDashOrderId"]]
        self.assertEqual(order["paymentStatus"], "paid")
        self.assertEqual(order["status"], "payment_review_required")
        self.assertFalse(order["inventoryCommitted"])
        self.assertTrue(order["requiresAdminAttention"])
        self.assertEqual(self.service.store.state["inventory"]["sd-prod-001-var-2"], 1)
        self.assertEqual(self.service.store.state["processedPayments"][payment_id], created["styleDashOrderId"])
        duplicate = self.deliver(self.webhook_body(created, payment_id))
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(self.service.store.state["inventory"]["sd-prod-001-var-2"], 1)

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


class PaymentTestProductTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.data_directory = Path(self.temporary.name)
        self.gateway = FakeGateway()
        self.allowed_user = {
            "id": "usr_payment_test_owner",
            "email": "Owner.Payment.Test@Example.Test",
            "name": "Payment Test Owner",
            "emailVerified": True,
        }
        self.service = SERVER.PaymentService(
            ROOT / "server" / "payment-data" / "catalog.json",
            ROOT / "server" / "payment-data" / "settings.json",
            self.data_directory,
            key_id="rzp_live_placeholder",
            key_secret="live_secret_placeholder",
            webhook_secret="live_webhook_placeholder",
            mode="live",
            gateway=self.gateway,
            payment_test_enabled=True,
            payment_test_allowed_emails={"owner.payment.test@example.test"},
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def assert_api_error(self, code: str, callback) -> None:
        with self.assertRaises(SERVER.ApiError) as caught:
            callback()
        self.assertEqual(caught.exception.code, code)

    def create(self, key: str = "payment-test-create-001", method: str = "upi") -> dict:
        return self.service.create_payment_test_order(
            self.allowed_user, {"paymentMethod": method}, key
        )

    def browser_verification(self, created: dict, payment_id: str, status: str = "captured") -> dict:
        self.gateway.payments[payment_id] = {
            "id": payment_id,
            "order_id": created["razorpayOrderId"],
            "amount": created["amount"],
            "currency": created["currency"],
            "status": status,
        }
        signature = hmac.new(
            b"live_secret_placeholder",
            f"{created['razorpayOrderId']}|{payment_id}".encode(),
            hashlib.sha256,
        ).hexdigest()
        return {
            "styleDashOrderId": created["styleDashOrderId"],
            "razorpay_order_id": created["razorpayOrderId"],
            "razorpay_payment_id": payment_id,
            "razorpay_signature": signature,
        }

    @staticmethod
    def webhook_body(created: dict, payment_id: str, **overrides) -> bytes:
        payment = {
            "id": payment_id,
            "order_id": created["razorpayOrderId"],
            "amount": created["amount"],
            "currency": created["currency"],
            "status": "captured",
        }
        payment.update(overrides)
        return json.dumps({
            "event": "payment.captured",
            "payload": {"payment": {"entity": payment}},
        }, separators=(",", ":")).encode()

    def deliver(self, body: bytes, service=None) -> dict:
        signature = hmac.new(b"live_webhook_placeholder", body, hashlib.sha256).hexdigest()
        return (service or self.service).process_webhook(body, signature)

    def test_flag_and_normalized_session_email_gate_metadata(self) -> None:
        metadata = self.service.payment_test_product({
            **self.allowed_user,
            "email": "  OWNER.PAYMENT.TEST@example.test ",
        })
        self.assertEqual(metadata, {"success": True, "product": {
            "id": "styledash-payment-test-item",
            "slug": "styledash-payment-test-item",
            "name": "StyleDash Payment Test Item",
            "price": 10,
            "amount": 1000,
            "currency": "INR",
            "fulfillmentRequired": False,
        }})
        self.assert_api_error("not_found", lambda: self.service.payment_test_product(None))
        self.assert_api_error("not_found", lambda: self.service.payment_test_product({
            "id": "usr_unverified", "email": self.allowed_user["email"], "emailVerified": False,
        }))
        self.assert_api_error("not_found", lambda: self.service.payment_test_product({
            "id": "usr_attacker", "email": "attacker@example.test", "emailVerified": True,
        }))

        disabled = SERVER.PaymentService(
            ROOT / "server" / "payment-data" / "catalog.json",
            ROOT / "server" / "payment-data" / "settings.json",
            self.data_directory / "disabled",
            key_id="rzp_live_placeholder", key_secret="live_secret_placeholder",
            webhook_secret="live_webhook_placeholder", mode="live", gateway=FakeGateway(),
            payment_test_enabled=False,
            payment_test_allowed_emails={"owner.payment.test@example.test"},
        )
        self.assert_api_error("not_found", lambda: disabled.payment_test_product(self.allowed_user))

    def test_private_environment_flag_and_allowlist_are_applied_case_insensitively(self) -> None:
        with patch.dict(os.environ, {
            "STYLEDASH_ENABLE_TEST_PRODUCT": "TrUe",
            "STYLEDASH_TEST_PRODUCT_ALLOWED_EMAILS": "First.Owner@Example.Test, second.owner@example.test",
        }):
            configured = SERVER.PaymentService(
                ROOT / "server" / "payment-data" / "catalog.json",
                ROOT / "server" / "payment-data" / "settings.json",
                self.data_directory / "configured",
                key_id="rzp_live_placeholder", key_secret="live_secret_placeholder",
                webhook_secret="live_webhook_placeholder", mode="live", gateway=FakeGateway(),
            )
        self.assertTrue(configured.can_access_payment_test_product({
            "email": "FIRST.OWNER@example.test", "emailVerified": True,
        }))
        self.assertTrue(configured.can_access_payment_test_product({
            "email": "second.owner@EXAMPLE.TEST", "emailVerified": True,
        }))
        self.assertFalse(configured.can_access_payment_test_product({
            "email": "unlisted@example.test", "emailVerified": True,
        }))
        self.assertFalse(configured.can_access_payment_test_product({
            "email": "first.owner@example.test", "emailVerified": False,
        }))

    def test_exact_live_razorpay_order_has_no_delivery_tax_discount_wallet_or_inventory(self) -> None:
        inventory_before = dict(self.service.store.state["inventory"])
        created = self.create()
        self.assertEqual((created["amount"], created["currency"]), (1000, "INR"))
        self.assertEqual(created["trustedTotals"], {
            "subtotal": 10, "discount": 0, "deliveryFee": 0, "taxes": 0, "grandTotal": 10,
        })
        self.assertEqual(self.gateway.calls, [{
            "amount": 1000,
            "currency": "INR",
            "receipt": created["receipt"],
            "notes": {
                "styleDashOrderId": created["styleDashOrderId"],
                "purpose": "payment_validation",
                "fulfillmentRequired": "false",
            },
        }])
        order = self.service.store.state["orders"][created["styleDashOrderId"]]
        self.assertEqual(order["items"][0]["productName"], "StyleDash Payment Test Item")
        self.assertEqual(order["deliveryMethod"], "none")
        self.assertEqual(order["adminLabels"], ["TEST", "NO FULFILLMENT REQUIRED"])
        self.assertFalse(order["fulfillmentRequired"])
        self.assertFalse(order["inventoryCommitted"])
        self.assertEqual(self.service.store.state["inventory"], inventory_before)

    def test_idempotency_is_scoped_to_the_authenticated_allowed_account(self) -> None:
        second_user = {
            "id": "usr_second_payment_test_owner",
            "email": "second.payment.owner@example.test",
            "emailVerified": True,
        }
        self.service.payment_test_allowed_emails.add("second.payment.owner@example.test")
        first = self.create("payment-test-shared-idempotency")
        second = self.service.create_payment_test_order(
            second_user, {"paymentMethod": "upi"}, "payment-test-shared-idempotency"
        )
        self.assertNotEqual(first["styleDashOrderId"], second["styleDashOrderId"])
        self.assertEqual(len(self.gateway.calls), 2)
        self.assertEqual(
            self.service.store.state["orders"][second["styleDashOrderId"]]["userId"],
            second_user["id"],
        )

    def test_unauthorized_forged_email_cod_coupon_wallet_and_totals_fail_without_mutation(self) -> None:
        state_before = json.loads(json.dumps(self.service.store.state))
        attacker = {"id": "usr_attacker", "email": "attacker@example.test"}
        self.assert_api_error(
            "not_found",
            lambda: self.service.create_payment_test_order(
                attacker,
                {"paymentMethod": "upi", "email": self.allowed_user["email"]},
                "payment-test-forged-email",
            ),
        )
        for payload in (
            {"paymentMethod": "cod"},
            {"paymentMethod": "upi", "email": self.allowed_user["email"]},
            {"paymentMethod": "upi", "couponCode": "FORGED"},
            {"paymentMethod": "upi", "walletAmount": 10},
            {"paymentMethod": "upi", "amount": 1},
            {"paymentMethod": "upi", "deliveryFee": -100, "taxes": -100},
        ):
            expected = "invalid_payment_method" if payload == {"paymentMethod": "cod"} else "invalid_payment_test_request"
            self.assert_api_error(
                expected,
                lambda candidate=payload: self.service.create_payment_test_order(
                    self.allowed_user, candidate, "payment-test-rejected-input"
                ),
            )
        self.assertEqual(self.service.store.state, state_before)
        self.assertEqual(self.gateway.calls, [])

    def test_authorized_payment_remains_pending_until_capture_and_never_touches_inventory(self) -> None:
        created = self.create("payment-test-authorized")
        inventory_before = dict(self.service.store.state["inventory"])
        authorized = self.service.verify_payment(
            self.browser_verification(created, "pay_payment_test_authorized", "authorized")
        )
        self.assertTrue(authorized["pending"])
        pending = self.service.store.state["orders"][created["styleDashOrderId"]]
        self.assertEqual((pending["paymentStatus"], pending["status"]), ("pending", "payment_pending"))
        self.assertEqual(self.service.store.state["inventory"], inventory_before)

        captured = self.deliver(self.webhook_body(created, "pay_payment_test_authorized"))
        self.assertEqual(captured, {"success": True})
        paid = self.service.store.state["orders"][created["styleDashOrderId"]]
        self.assertEqual((paid["paymentStatus"], paid["status"]), ("paid", "payment_test_completed"))
        self.assertFalse(paid["inventoryCommitted"])
        self.assertIn("no fulfillment required", paid["statusHistory"][-1]["note"].lower())
        self.assertEqual(self.service.store.state["inventory"], inventory_before)

    def test_invalid_callback_and_webhook_fail_without_business_mutation(self) -> None:
        created = self.create("payment-test-invalid")
        inventory_before = dict(self.service.store.state["inventory"])
        invalid = self.browser_verification(created, "pay_payment_test_invalid")
        invalid["razorpay_signature"] = "invalid"
        self.assert_api_error("signature_mismatch", lambda: self.service.verify_payment(invalid))

        body = self.webhook_body(created, "pay_payment_test_invalid")
        self.assert_api_error(
            "webhook_signature_mismatch",
            lambda: self.service.process_webhook(body, "invalid"),
        )
        self.assert_api_error(
            "amount_mismatch",
            lambda: self.deliver(self.webhook_body(created, "pay_payment_test_invalid", amount=999)),
        )
        order = self.service.store.state["orders"][created["styleDashOrderId"]]
        self.assertEqual((order["paymentStatus"], order["status"]), ("pending", "payment_pending"))
        self.assertEqual(self.service.store.state["inventory"], inventory_before)

    def test_concurrent_duplicates_and_restart_finalize_exactly_once_without_inventory(self) -> None:
        with ThreadPoolExecutor(max_workers=8) as executor:
            created_results = list(executor.map(
                lambda _index: self.create("payment-test-concurrent-create"),
                range(8),
            ))
        self.assertEqual(len({item["styleDashOrderId"] for item in created_results}), 1)
        self.assertEqual(len(self.gateway.calls), 1)
        created = created_results[0]
        callback = self.browser_verification(created, "pay_payment_test_concurrent")
        body = self.webhook_body(created, "pay_payment_test_concurrent")
        inventory_before = dict(self.service.store.state["inventory"])

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(self.service.verify_payment, callback),
                executor.submit(self.deliver, body),
            ]
            for future in futures:
                future.result()

        order = self.service.store.state["orders"][created["styleDashOrderId"]]
        self.assertEqual((order["paymentStatus"], order["status"]), ("paid", "payment_test_completed"))
        self.assertEqual(len(self.service.store.state["processedPayments"]), 1)
        self.assertEqual(self.service.store.state["inventory"], inventory_before)

        restarted = SERVER.PaymentService(
            ROOT / "server" / "payment-data" / "catalog.json",
            ROOT / "server" / "payment-data" / "settings.json",
            self.data_directory,
            key_id="rzp_live_placeholder", key_secret="live_secret_placeholder",
            webhook_secret="live_webhook_placeholder", mode="live", gateway=self.gateway,
            payment_test_enabled=False,
            payment_test_allowed_emails={"owner.payment.test@example.test"},
        )
        self.assertTrue(self.deliver(body, restarted)["duplicate"])
        restarted_order = restarted.store.state["orders"][created["styleDashOrderId"]]
        self.assertEqual((restarted_order["paymentStatus"], restarted_order["status"]), ("paid", "payment_test_completed"))
        self.assertEqual(restarted.store.state["inventory"], inventory_before)
        self.assert_api_error(
            "not_found",
            lambda: restarted.create_payment_test_order(
                self.allowed_user, {"paymentMethod": "upi"}, "payment-test-disabled-new"
            ),
        )


class HttpApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        web_root = root / "web"
        web_root.mkdir()
        (web_root / "index.html").write_text("<!doctype html><title>StyleDash</title>", encoding="utf-8")
        self.reset_deliveries = []
        self.firebase_claims = {}
        security_store = SERVER.SecurityStore(
            root / "styledash.db", Fernet.generate_key().decode(),
            password_reset_sender=lambda email, token: self.reset_deliveries.append((email, token)),
            firebase_verifier=lambda token: self.firebase_claims[token],
        )
        self.gateway = FakeGateway()
        service = SERVER.PaymentService(
            ROOT / "server" / "payment-data" / "catalog.json",
            ROOT / "server" / "payment-data" / "settings.json",
            root / "data",
            key_id="rzp_test_placeholder",
            key_secret="test_secret_placeholder",
            webhook_secret="webhook_secret_placeholder",
            mode="test",
            gateway=self.gateway,
            security_store=security_store,
            payment_test_enabled=True,
            payment_test_allowed_emails={"http-payment-owner@example.test"},
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
            self.assertEqual(payload, {"status": "ok", "service": "StyleDash", "database": "ok"})
            self.assertNotIn("paymentMode", payload)
            self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
            self.assertEqual(response.headers["Referrer-Policy"], "strict-origin-when-cross-origin")
            self.assertIn("checkout.razorpay.com", response.headers["Content-Security-Policy"])

    def test_public_robots_and_sitemap_use_configured_origin(self) -> None:
        with urllib.request.urlopen(f"{self.base_url}/robots.txt") as response:
            body = response.read().decode("utf-8")
            self.assertEqual(response.headers.get_content_type(), "text/plain")
            self.assertIn("User-agent: *", body)
            self.assertIn("Sitemap: https://styledash.test/sitemap.xml", body)

        with urllib.request.urlopen(f"{self.base_url}/sitemap.xml") as response:
            body = response.read().decode("utf-8")
            self.assertEqual(response.headers.get_content_type(), "application/xml")
            self.assertIn("<loc>https://styledash.test/</loc>", body)
            self.assertIn("<loc>https://styledash.test/products</loc>", body)
            self.assertIn("https://styledash.test/product/", body)

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
        body = b'{"event":"subscription.charged","payload":{}}'
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

    def get_json(self, path: str, headers: dict | None = None):
        try:
            request = urllib.request.Request(f"{self.base_url}{path}", headers=headers or {})
            response = urllib.request.urlopen(request)
        except urllib.error.HTTPError as error:
            body = json.loads(error.read()); status = error.code; response_headers = error.headers; error.close()
            return status, body, response_headers
        with response:
            return response.status, json.load(response), response.headers

    def patch_json(self, path: str, payload: dict, headers: dict | None = None):
        request = urllib.request.Request(
            f"{self.base_url}{path}", data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json", **(headers or {})}, method="PATCH",
        )
        try:
            response = urllib.request.urlopen(request)
        except urllib.error.HTTPError as error:
            body = json.loads(error.read()); status = error.code; response_headers = error.headers; error.close()
            return status, body, response_headers
        with response:
            return response.status, json.load(response), response.headers

    def test_shop_draft_approval_publication_inventory_and_checkout_contract(self) -> None:
        status, registered, headers = self.post_json(
            "/api/auth/register",
            {
                "name": "Shop HTTP Owner",
                "email": "shop-http-owner@example.test",
                "password": "very secure shop http password 123",
                "phone": "9876543210",
            },
        )
        self.assertEqual(status, 201)
        session_headers = {
            "Cookie": headers["Set-Cookie"].split(";", 1)[0],
            "X-CSRF-Token": registered["csrfToken"],
            "Origin": "https://styledash.test",
        }
        status, anonymous, _headers = self.get_json("/api/vendor-applications/me")
        self.assertEqual((status, anonymous["code"]), (401, "authentication_required"))

        status, created, _headers = self.post_json(
            "/api/vendor-applications", {"shopName": "HTTP Draft Shop"}, session_headers
        )
        self.assertEqual(status, 201)
        self.assertEqual(created["application"]["status"], "DRAFT")
        application_id = created["application"]["id"]
        status, fetched, _headers = self.get_json(
            "/api/vendor-applications/me", {"Cookie": session_headers["Cookie"]}
        )
        self.assertEqual((status, fetched["application"]["id"]), (200, application_id))
        status, missing_csrf, _headers = self.patch_json(
            "/api/vendor-applications/me", {"ownerName": "Shop HTTP Owner"},
            {"Cookie": session_headers["Cookie"], "Origin": "https://styledash.test"},
        )
        self.assertEqual((status, missing_csrf["code"]), (403, "csrf_failed"))
        complete = {
            "shopName": "HTTP Draft Shop",
            "ownerName": "Shop HTTP Owner",
            "category": "Clothing & Fashion",
            "description": "A complete HTTP shop application for integration coverage.",
            "address": "12 Main Market Road",
            "city": "Neemuch",
            "state": "Madhya Pradesh",
            "pincode": "458441",
        }
        status, updated, _headers = self.patch_json(
            "/api/vendor-applications/me", complete, session_headers
        )
        self.assertEqual((status, updated["application"]["status"]), (200, "DRAFT"))
        status, submitted, _headers = self.post_json(
            "/api/vendor-applications/me/submit", {}, session_headers
        )
        self.assertEqual((status, submitted["application"]["status"]), (200, "SUBMITTED"))

        with self.service.security.connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS admin_users("
                "id TEXT PRIMARY KEY,is_active INTEGER NOT NULL DEFAULT 1)"
            )
            db.execute("INSERT INTO admin_users(id,is_active) VALUES('http-admin',1)")
        self.service.shops.admin_transition_application(
            "http-admin", application_id, "UNDER_REVIEW"
        )
        self.service.shops.admin_transition_application(
            "http-admin", application_id, "APPROVED"
        )
        self.service.shops.admin_transition_application(
            "http-admin", application_id, "ACTIVE"
        )
        product_payload = {
            "name": "HTTP Published Kurta",
            "description": "A reviewed local cotton kurta available through the HTTP catalogue.",
            "brand": "HTTP Local Loom",
            "department": "women",
            "category": "Clothing & Fashion",
            "pricePaise": 159900,
            "originalPricePaise": 179900,
            "inventory": 8,
            "imageUrls": ["https://images.example.test/http-kurta.jpg"],
            "attributes": {"material": "Cotton"},
            "size": "M",
            "colourName": "Blue",
            "colourHex": "#0000FF",
        }
        status, product_response, _headers = self.post_json(
            "/api/shop-products", product_payload, session_headers
        )
        self.assertEqual(status, 201)
        product_id = product_response["product"]["id"]
        status, product_submitted, _headers = self.post_json(
            f"/api/shop-products/{product_id}/submit", {}, session_headers
        )
        self.assertEqual((status, product_submitted["product"]["status"]), (200, "SUBMITTED"))
        status, public_before, _headers = self.get_json("/api/shop-products/published")
        self.assertEqual((status, public_before["products"]), (200, []))
        for target in ("UNDER_REVIEW", "APPROVED", "PUBLISHED"):
            self.service.shops.admin_transition_product("http-admin", product_id, target)

        status, public_after, _headers = self.get_json("/api/shop-products/published")
        self.assertEqual(status, 200)
        self.assertEqual([item["id"] for item in public_after["products"]], [product_id])
        public_product = public_after["products"][0]
        self.assertNotIn("submittedByUserId", public_product)
        self.assertNotIn("registeredEmail", public_product)
        status, stores_response, _headers = self.get_json("/api/stores/active")
        self.assertEqual(status, 200)
        self.assertEqual([store["id"] for store in stores_response["stores"]], [application_id])
        public_store = stores_response["stores"][0]
        self.assertEqual(public_store["slug"], public_product["storeSlug"])
        self.assertEqual(public_store["storeName"], complete["shopName"])
        self.assertEqual(public_store["bannerImage"], product_payload["imageUrls"][0])
        self.assertNotIn("registeredEmail", public_store)
        self.assertNotIn("registeredMobile", public_store)
        self.assertNotIn("businessInformation", public_store)
        variant_id = public_product["variants"][0]["id"]
        status, availability, _headers = self.get_json(
            f"/api/inventory/availability?variantId={variant_id}"
        )
        self.assertEqual(status, 200)
        self.assertTrue(availability["availability"][0]["available"])

        cod_headers = {
            **session_headers,
            "Idempotency-Key": "shop-http-cod-001",
        }
        status, placed, _headers = self.post_json(
            "/api/place-cod-order",
            {
                "items": [{"productId": product_id, "variantId": variant_id, "quantity": 1}],
                "address": {
                    "name": "Shop HTTP Owner",
                    "phone": "9876543210",
                    "street": "12 Main Market Road",
                    "city": "Neemuch",
                    "pincode": "458441",
                },
                "deliveryMethod": "express",
                "paymentMethod": "cod",
            },
            cod_headers,
        )
        self.assertEqual(status, 201)
        self.assertEqual(placed["order"]["items"][0]["productId"], product_id)
        self.service.shops.admin_transition_product("http-admin", product_id, "APPROVED")
        status, public_unpublished, _headers = self.get_json("/api/shop-products/published")
        self.assertEqual(public_unpublished["products"], [])
        inactive = next(
            item for item in self.service.shops.payment_catalog_products() if item["id"] == product_id
        )
        self.assertFalse(inactive["active"])
        status, unavailable, _headers = self.post_json(
            "/api/place-cod-order",
            {
                "items": [{"productId": product_id, "variantId": variant_id, "quantity": 1}],
                "address": {
                    "name": "Shop HTTP Owner",
                    "phone": "9876543210",
                    "street": "12 Main Market Road",
                    "city": "Neemuch",
                    "pincode": "458441",
                },
                "deliveryMethod": "express",
                "paymentMethod": "cod",
            },
            {**session_headers, "Idempotency-Key": "shop-http-cod-002"},
        )
        self.assertEqual((status, unavailable["code"]), (422, "invalid_product"))

    def test_federated_link_http_requires_csrf_and_rejects_linked_subject(self) -> None:
        status, registered, headers = self.post_json(
            "/api/auth/register",
            {
                "name": "Link HTTP Owner",
                "email": "link-http-owner@example.test",
                "password": "very secure link http password 123",
                "phone": "9876543212",
            },
        )
        self.assertEqual(status, 201)
        cookie = headers["Set-Cookie"].split(";", 1)[0]
        google_token = "google-link-http-token-0001"
        self.firebase_claims[google_token] = {
            "uid": "google-link-http-uid-1",
            "email": "link-http-owner@example.test",
            "email_verified": True,
            "firebase": {"sign_in_provider": "google.com"},
        }
        status, missing, _headers = self.post_json(
            "/api/auth/federated/google/link", {"idToken": google_token}, {"Cookie": cookie}
        )
        self.assertEqual((status, missing["code"]), (403, "csrf_failed"))
        status, invalid, _headers = self.post_json(
            "/api/auth/federated/google/link",
            {"idToken": google_token},
            {"Cookie": cookie, "X-CSRF-Token": "invalid", "Origin": "https://styledash.test"},
        )
        self.assertEqual((status, invalid["code"]), (403, "csrf_failed"))
        valid_headers = {
            "Cookie": cookie,
            "X-CSRF-Token": registered["csrfToken"],
            "Origin": "https://styledash.test",
        }
        status, linked, _headers = self.post_json(
            "/api/auth/federated/google/link", {"idToken": google_token}, valid_headers
        )
        self.assertEqual(status, 200)
        self.assertEqual(linked["profile"]["id"], registered["user"]["id"])

        status, second, second_headers = self.post_json(
            "/api/auth/register",
            {
                "name": "Link HTTP Other",
                "email": "link-http-other@example.test",
                "password": "very secure other link password 123",
                "phone": "9876543213",
            },
        )
        self.assertEqual(status, 201)
        status, conflict, _headers = self.post_json(
            "/api/auth/federated/link/google",
            {"idToken": google_token},
            {
                "Cookie": second_headers["Set-Cookie"].split(";", 1)[0],
                "X-CSRF-Token": second["csrfToken"],
                "Origin": "https://styledash.test",
            },
        )
        self.assertEqual((status, conflict["code"]), (409, "identity_already_linked"))

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

        status, batch, _headers = self.get_json(
            "/api/inventory/availability?productId=sd-prod-001&productId=missing-product"
        )
        self.assertEqual(status, 200)
        self.assertGreater(len(batch["availability"]), 1)
        self.assertTrue(all(item["productId"] == "sd-prod-001" for item in batch["availability"]))
        self.assertIn("sd-prod-001-var-2", {item["variantId"] for item in batch["availability"]})
        self.assertNotIn("stock", json.dumps(batch))

        too_many = "&".join(f"productId=p{index}" for index in range(33))
        status, invalid_products, _headers = self.get_json(f"/api/inventory/availability?{too_many}")
        self.assertEqual((status, invalid_products["code"]), (400, "invalid_product"))
        status, mixed, _headers = self.get_json(
            "/api/inventory/availability?variantId=sd-prod-001-var-2&productId=sd-prod-001"
        )
        self.assertEqual((status, mixed["code"]), (400, "invalid_inventory_filter"))

        status, invalid, _headers = self.get_json("/api/inventory/availability?variantId=&variantId=duplicate")
        self.assertEqual((status, invalid["code"]), (400, "invalid_variant"))
        status, _body, _headers = self.post_json("/api/inventory/availability", {})
        self.assertEqual(status, 404)

    def test_registration_sends_exactly_one_private_owner_notification(self) -> None:
        notification_env = {
            "STYLEDASH_NTFY_ENABLED": "true",
            "STYLEDASH_NTFY_BASE_URL": "https://ntfy.test",
            "STYLEDASH_NTFY_TOPIC": "styledash-test-private-topic-1234567890",
        }

        with patch.dict(os.environ, notification_env, clear=False):
            with patch("scripts.styledash_notify.urlopen") as mocked_urlopen:
                mocked_urlopen.return_value.__enter__.return_value.status = 200

                payload = {
                    "name": "Notification Customer",
                    "email": "notification-customer@example.test",
                    "password": "very secure notification password 123",
                    "phone": "9999999999",
                }

                status, registered, _headers = self.post_json(
                    "/api/auth/register",
                    payload,
                )

                self.assertEqual(status, 201)
                self.assertTrue(registered["success"])
                self.assertEqual(mocked_urlopen.call_count, 1)

                request = mocked_urlopen.call_args.args[0]
                ntfy_payload = json.loads(request.data.decode("utf-8"))

                self.assertEqual(
                    ntfy_payload["topic"],
                    notification_env["STYLEDASH_NTFY_TOPIC"],
                )
                self.assertEqual(ntfy_payload["priority"], 5)
                self.assertIn(
                    "Notification Customer",
                    ntfy_payload["message"],
                )
                self.assertIn(
                    "no*******************@example.test",
                    ntfy_payload["message"],
                )

                # Sensitive registration fields must not appear in the
                # human-visible notification title/message.
                visible = (
                    ntfy_payload["title"] + "\n" + ntfy_payload["message"]
                )
                self.assertNotIn(payload["password"], visible)
                self.assertNotIn(payload["phone"], visible)
                self.assertNotIn(payload["email"], visible)
                self.assertNotIn(
                    notification_env["STYLEDASH_NTFY_TOPIC"],
                    visible,
                )

                # A failed duplicate registration must not produce
                # a second owner notification.
                duplicate_status, duplicate, _headers = self.post_json(
                    "/api/auth/register",
                    payload,
                )

                self.assertEqual(duplicate_status, 409)
                self.assertEqual(duplicate["code"], "email_exists")
                self.assertEqual(mocked_urlopen.call_count, 1)

    def test_ntfy_network_failure_does_not_break_registration(self) -> None:
        notification_env = {
            "STYLEDASH_NTFY_ENABLED": "true",
            "STYLEDASH_NTFY_BASE_URL": "https://ntfy.test",
            "STYLEDASH_NTFY_TOPIC": "styledash-test-private-topic-1234567890",
        }

        with patch.dict(os.environ, notification_env, clear=False):
            with patch(
                "scripts.styledash_notify.urlopen",
                side_effect=TimeoutError("simulated ntfy timeout"),
            ):
                status, registered, headers = self.post_json(
                    "/api/auth/register",
                    {
                        "name": "Notification Failure Customer",
                        "email": "notification-failure@example.test",
                        "password": "very secure failure password 123",
                        "phone": "9999999999",
                    },
                )

        self.assertEqual(status, 201)
        self.assertTrue(registered["success"])
        self.assertIn("__Host-styledash_session=", headers["Set-Cookie"])

        # Registration really persisted despite notification failure.
        with self.service.security.connect() as db:
            row = db.execute(
                "SELECT id FROM users WHERE email=?",
                ("notification-failure@example.test",),
            ).fetchone()

        self.assertIsNotNone(row)


    def test_cod_order_sends_exactly_one_owner_notification(self) -> None:
        # Registration notification is intentionally disabled here so
        # this test counts only the COD notification.
        with patch.dict(
            os.environ,
            {"STYLEDASH_NTFY_ENABLED": "false"},
            clear=False,
        ):
            status, registered, headers = self.post_json(
                "/api/auth/register",
                {
                    "name": "COD Notification Customer",
                    "email": "cod-notification@example.test",
                    "password": "very secure cod password 123",
                    "phone": "9999999999",
                },
            )

        self.assertEqual(status, 201)

        cookie = headers["Set-Cookie"].split(";", 1)[0]

        cod_payload = {
            "items": [{
                "productId": "sd-prod-001",
                "variantId": "sd-prod-001-var-2",
                "quantity": 1,
            }],
            "address": {
                "name": "COD Notification Customer",
                "phone": "9999999999",
                "street": "123 Notification Street",
                "city": "Neemuch",
                "pincode": "458441",
            },
            "deliveryMethod": "express",
            "paymentMethod": "cod",
            "couponCode": None,
        }

        request_headers = {
            "Cookie": cookie,
            "X-CSRF-Token": registered["csrfToken"],
            "Origin": "https://styledash.test",
            "Idempotency-Key": "cod-notification-test-001",
        }

        notification_env = {
            "STYLEDASH_NTFY_ENABLED": "true",
            "STYLEDASH_NTFY_BASE_URL": "https://ntfy.test",
            "STYLEDASH_NTFY_TOPIC":
                "styledash-test-private-topic-1234567890",
        }

        with patch.dict(os.environ, notification_env, clear=False):
            with patch(
                "scripts.styledash_notify.urlopen"
            ) as mocked_urlopen:
                mocked_urlopen.return_value.__enter__.return_value.status = 200

                status, placed, _headers = self.post_json(
                    "/api/place-cod-order",
                    cod_payload,
                    request_headers,
                )

                self.assertEqual(status, 201)
                self.assertTrue(placed["success"])
                self.assertFalse(placed["idempotent"])
                self.assertEqual(mocked_urlopen.call_count, 1)

                request = mocked_urlopen.call_args.args[0]
                ntfy_payload = json.loads(
                    request.data.decode("utf-8")
                )

                order = placed["order"]
                grand_total = order["grandTotal"]

                self.assertEqual(ntfy_payload["priority"], 5)
                self.assertIn(
                    order["id"],
                    ntfy_payload["message"],
                )
                self.assertIn(
                    f"?{grand_total}",
                    ntfy_payload["message"],
                )
                self.assertIn(
                    "Payment: COD",
                    ntfy_payload["message"],
                )
                self.assertIn(
                    "Status: Placed",
                    ntfy_payload["message"],
                )

                visible = (
                    ntfy_payload["title"]
                    + "\n"
                    + ntfy_payload["message"]
                )

                # Private address/phone/topic must not be visible.
                self.assertNotIn(
                    cod_payload["address"]["street"],
                    visible,
                )
                self.assertNotIn(
                    cod_payload["address"]["phone"],
                    visible,
                )
                self.assertNotIn(
                    notification_env["STYLEDASH_NTFY_TOPIC"],
                    visible,
                )

                # Same logical COD order must not ring twice.
                duplicate_status, duplicate, _headers = self.post_json(
                    "/api/place-cod-order",
                    cod_payload,
                    request_headers,
                )

                self.assertEqual(duplicate_status, 201)
                self.assertTrue(duplicate["idempotent"])
                self.assertEqual(
                    duplicate["order"]["id"],
                    order["id"],
                )
                self.assertEqual(mocked_urlopen.call_count, 1)

    def test_ntfy_failure_does_not_break_cod_order(self) -> None:
        with patch.dict(
            os.environ,
            {"STYLEDASH_NTFY_ENABLED": "false"},
            clear=False,
        ):
            status, registered, headers = self.post_json(
                "/api/auth/register",
                {
                    "name": "COD Failure Customer",
                    "email": "cod-failure@example.test",
                    "password": "very secure cod failure password 123",
                    "phone": "9999999999",
                },
            )

        self.assertEqual(status, 201)

        cookie = headers["Set-Cookie"].split(";", 1)[0]

        cod_payload = {
            "items": [{
                "productId": "sd-prod-001",
                "variantId": "sd-prod-001-var-2",
                "quantity": 1,
            }],
            "address": {
                "name": "COD Failure Customer",
                "phone": "9999999999",
                "street": "123 Failure Street",
                "city": "Neemuch",
                "pincode": "458441",
            },
            "deliveryMethod": "express",
            "paymentMethod": "cod",
            "couponCode": None,
        }

        request_headers = {
            "Cookie": cookie,
            "X-CSRF-Token": registered["csrfToken"],
            "Origin": "https://styledash.test",
            "Idempotency-Key": "cod-notification-failure-001",
        }

        notification_env = {
            "STYLEDASH_NTFY_ENABLED": "true",
            "STYLEDASH_NTFY_BASE_URL": "https://ntfy.test",
            "STYLEDASH_NTFY_TOPIC":
                "styledash-test-private-topic-1234567890",
        }

        with patch.dict(os.environ, notification_env, clear=False):
            with patch(
                "scripts.styledash_notify.urlopen",
                side_effect=TimeoutError(
                    "simulated COD notification timeout"
                ),
            ):
                status, placed, _headers = self.post_json(
                    "/api/place-cod-order",
                    cod_payload,
                    request_headers,
                )

        self.assertEqual(status, 201)
        self.assertTrue(placed["success"])
        self.assertFalse(placed["idempotent"])

        order_id = placed["order"]["id"]
        persisted = self.service.store.state["orders"][order_id]

        self.assertEqual(persisted["status"], "placed")
        self.assertEqual(persisted["paymentMethod"], "cod")
        self.assertTrue(persisted["inventoryCommitted"])


    def test_vendor_application_sends_one_private_owner_notification(self) -> None:
        # Registration itself is not part of this notification test.
        with patch.dict(
            os.environ,
            {"STYLEDASH_NTFY_ENABLED": "false"},
            clear=False,
        ):
            status, registered, headers = self.post_json(
                "/api/auth/register",
                {
                    "name": "Vendor Notification Owner",
                    "email": "vendor-notify@example.test",
                    "password": "very secure vendor password 123",
                    "phone": "9999999999",
                },
            )

        self.assertEqual(status, 201)

        cookie = headers["Set-Cookie"].split(";", 1)[0]

        request_headers = {
            "Cookie": cookie,
            "X-CSRF-Token": registered["csrfToken"],
            "Origin": "https://styledash.test",
        }

        payload = {
            "storeName": "Notification Fashion Store",
            "ownerName": "Vendor Notification Owner",
            "email": "vendor-notify@example.test",
            "phone": "9999999999",
            "category": "Clothing & Fashion",
            "address": "123 Private Vendor Market",
            "pincode": "458441",
            "description":
                "A test vendor application for notification coverage.",
        }

        with patch.object(
            SERVER,
            "owner_notifier",
        ) as notifier_factory:
            notifier = notifier_factory.return_value

            status, response, _headers = self.post_json(
                "/api/vendor-applications",
                payload,
                request_headers,
            )

            self.assertEqual(status, 201)
            self.assertTrue(response["success"])
            self.assertTrue(
                response["application"]["id"].startswith("vendor_")
            )

            self.assertEqual(
                notifier.send.call_count,
                1,
            )

            notification = notifier.send.call_args.kwargs

            self.assertEqual(
                notification["event"],
                "vendor_application",
            )
            self.assertEqual(
                notification["priority"],
                5,
            )
            self.assertIn(
                response["application"]["id"],
                notification["message"],
            )
            self.assertIn(
                "Notification Fashion Store",
                notification["message"],
            )
            self.assertIn(
                "Clothing & Fashion",
                notification["message"],
            )

            visible = (
                notification["title"]
                + "\n"
                + notification["message"]
            )

            # Customer/vendor private contact and address information
            # must not be sent to the phone notification.
            self.assertNotIn(
                payload["email"],
                visible,
            )
            self.assertNotIn(
                payload["phone"],
                visible,
            )
            self.assertNotIn(
                payload["address"],
                visible,
            )

            # Failed validation must not generate a notification.
            invalid_payload = dict(
                payload,
                category="Unsupported Category",
            )

            invalid_status, invalid, _headers = self.post_json(
                "/api/vendor-applications",
                invalid_payload,
                request_headers,
            )

            self.assertEqual(invalid_status, 400)
            self.assertEqual(
                invalid["code"],
                "invalid_vendor_application",
            )
            self.assertEqual(
                notifier.send.call_count,
                1,
            )

    def test_ntfy_failure_does_not_break_vendor_application(self) -> None:
        with patch.dict(
            os.environ,
            {"STYLEDASH_NTFY_ENABLED": "false"},
            clear=False,
        ):
            status, registered, headers = self.post_json(
                "/api/auth/register",
                {
                    "name": "Vendor Failure Owner",
                    "email": "vendor-failure@example.test",
                    "password": "very secure vendor failure password 123",
                    "phone": "9999999999",
                },
            )

        self.assertEqual(status, 201)

        request_headers = {
            "Cookie": headers["Set-Cookie"].split(";", 1)[0],
            "X-CSRF-Token": registered["csrfToken"],
            "Origin": "https://styledash.test",
        }

        notification_env = {
            "STYLEDASH_NTFY_ENABLED": "true",
            "STYLEDASH_NTFY_BASE_URL": "https://ntfy.test",
            "STYLEDASH_NTFY_TOPIC":
                "styledash-test-private-topic-1234567890",
        }

        payload = {
            "storeName": "Failure Isolation Store",
            "ownerName": "Vendor Failure Owner",
            "email": "vendor-failure@example.test",
            "phone": "9999999999",
            "category": "Clothing & Fashion",
            "address": "456 Private Vendor Market",
            "pincode": "458441",
            "description":
                "Vendor notification failure isolation test.",
        }

        with patch.dict(
            os.environ,
            notification_env,
            clear=False,
        ):
            with patch(
                "scripts.styledash_notify.urlopen",
                side_effect=TimeoutError(
                    "simulated vendor ntfy timeout"
                ),
            ):
                status, response, _headers = self.post_json(
                    "/api/vendor-applications",
                    payload,
                    request_headers,
                )

        self.assertEqual(status, 201)
        self.assertTrue(response["success"])

        application_id = response["application"]["id"]

        # The database write must survive notification failure.
        with self.service.security.connect() as db:
            row = db.execute(
                """
                SELECT id, status
                FROM vendor_applications
                WHERE id=?
                """,
                (application_id,),
            ).fetchone()

        self.assertIsNotNone(row)
        self.assertEqual(row["status"], "SUBMITTED")


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

        anonymous_admin = urllib.request.Request(f"{self.base_url}/api/admin/orders")
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(anonymous_admin)
        self.assertEqual(caught.exception.code, 404); caught.exception.close()

        customer_admin = urllib.request.Request(f"{self.base_url}/api/admin/orders", headers={"Cookie": cookie})
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(customer_admin)
        self.assertEqual(caught.exception.code, 404); caught.exception.close()

        public_admin_ui = urllib.request.Request(f"{self.base_url}/admin")
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(public_admin_ui)
        self.assertEqual(caught.exception.code, 404); caught.exception.close()
        for concealed_path in ("/%61dmin", "/.%2e/admin", "/api/%61dmin/orders"):
            status, body, _headers = self.get_json(concealed_path)
            self.assertEqual((status, body["code"]), (404, "not_found"))

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

    def test_federated_phone_and_returning_google_http_contract(self) -> None:
        phone_token = "phone-http-token-" + ("x" * 24)
        self.firebase_claims[phone_token] = {
            "uid": "firebase-phone-http-uid",
            "email": None,
            "phone_number": "+91 99999 99999",
            "firebase": {"sign_in_provider": "phone"},
        }
        phone_status, phone_body, phone_headers = self.post_json(
            "/api/auth/federated/phone", {"idToken": phone_token}
        )
        self.assertEqual(phone_status, 201)
        self.assertTrue(phone_body["needsProfile"])
        self.assertTrue(phone_body["csrfToken"])
        phone_cookie = phone_headers["Set-Cookie"].split(";", 1)[0]
        me_status, me_body, _headers = self.get_json(
            "/api/auth/me", {"Cookie": phone_cookie}
        )
        self.assertEqual(me_status, 200)
        self.assertEqual(me_body["user"]["phone"], "+919999999999")

        replacement_phone_token = "phone-http-replacement-token-" + ("r" * 24)
        self.firebase_claims[replacement_phone_token] = {
            "uid": "firebase-phone-http-replacement-uid",
            "email": None,
            "phone_number": "+919999999999",
            "firebase": {"sign_in_provider": "phone"},
        }
        replacement_status, replacement_body, replacement_headers = self.post_json(
            "/api/auth/federated/phone", {"idToken": replacement_phone_token}
        )
        self.assertEqual(replacement_status, 200)
        self.assertEqual(replacement_body["user"]["id"], phone_body["user"]["id"])
        self.assertTrue(replacement_body["csrfToken"])
        self.assertNotEqual(
            replacement_headers["Set-Cookie"].split(";", 1)[0], phone_cookie
        )
        with self.service.security.connect() as db:
            self.assertEqual(
                db.execute(
                    "SELECT COUNT(*) FROM customer_auth_identities "
                    "WHERE provider='phone'"
                ).fetchone()[0],
                1,
            )
            self.assertEqual(
                db.execute(
                    "SELECT provider_subject FROM customer_auth_identities "
                    "WHERE provider='phone'"
                ).fetchone()[0],
                "firebase-phone-http-replacement-uid",
            )

        google_token = "google-http-token-" + ("y" * 24)
        self.firebase_claims[google_token] = {
            "uid": "firebase-google-http-uid",
            "email": "existing-google@example.test",
            "email_verified": True,
            "name": "Existing Google",
            "firebase": {"sign_in_provider": "google.com"},
        }
        first_status, first_body, first_headers = self.post_json(
            "/api/auth/federated/google", {"idToken": google_token}
        )
        self.assertEqual(first_status, 201)
        with self.service.security.connect() as db:
            google_user_id = first_body["user"]["id"]
            db.execute("UPDATE users SET last_login_at='stale' WHERE id=?", (google_user_id,))
            db.execute("UPDATE customer_auth_identities SET last_used_at='stale' WHERE user_id=?", (google_user_id,))
            users_before = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            identities_before = db.execute("SELECT COUNT(*) FROM customer_auth_identities").fetchone()[0]
        second_status, second_body, second_headers = self.post_json(
            "/api/auth/federated/google", {"idToken": google_token}
        )
        self.assertEqual(second_status, 200)
        self.assertEqual(second_body["user"]["id"], google_user_id)
        self.assertTrue(second_body["csrfToken"])
        self.assertNotEqual(first_body["csrfToken"], second_body["csrfToken"])
        self.assertNotEqual(
            first_headers["Set-Cookie"].split(";", 1)[0],
            second_headers["Set-Cookie"].split(";", 1)[0],
        )
        with self.service.security.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM users").fetchone()[0], users_before)
            self.assertEqual(
                db.execute("SELECT COUNT(*) FROM customer_auth_identities").fetchone()[0],
                identities_before,
            )
            login_at = db.execute("SELECT last_login_at FROM users WHERE id=?", (google_user_id,)).fetchone()[0]
            last_used_at = db.execute(
                "SELECT last_used_at FROM customer_auth_identities WHERE user_id=?", (google_user_id,)
            ).fetchone()[0]
        self.assertNotEqual(login_at, "stale")
        self.assertNotEqual(last_used_at, "stale")

    def test_standard_http_errors_remain_available_with_redacted_logging(self) -> None:
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(f"{self.base_url}/missing.js")
        self.assertEqual(caught.exception.code, 404)
        caught.exception.close()

        admin_options = urllib.request.Request(
            f"{self.base_url}/api/admin/orders", method="OPTIONS"
        )
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(admin_options)
        self.assertEqual(caught.exception.code, 404)
        caught.exception.close()

    def test_payment_test_http_authorizes_session_only_and_preserves_paid_history_when_disabled(self) -> None:
        endpoint = "/api/payment-test-product/styledash-payment-test-item"
        controlled_route = "/payment-test/styledash-payment-test-item"
        route_status, route_hidden, _headers = self.get_json(controlled_route)
        self.assertEqual((route_status, route_hidden["code"]), (404, "not_found"))
        status, anonymous, _headers = self.get_json(
            f"{endpoint}?email=http-payment-owner%40example.test"
        )
        self.assertEqual((status, anonymous["code"]), (404, "not_found"))

        status, attacker, attacker_headers = self.post_json("/api/auth/register", {
            "name": "HTTP Attacker", "email": "http-attacker@example.test",
            "password": "long attacker password 123", "phone": "9999999999",
        })
        self.assertEqual(status, 201)
        attacker_cookie = attacker_headers["Set-Cookie"].split(";", 1)[0]
        attacker_auth = {
            "Cookie": attacker_cookie,
            "X-CSRF-Token": attacker["csrfToken"],
            "Origin": "https://styledash.test",
            "Idempotency-Key": "payment-test-http-forged",
        }
        status, hidden, _headers = self.get_json(
            f"{endpoint}?email=http-payment-owner%40example.test",
            {"Cookie": attacker_cookie},
        )
        self.assertEqual((status, hidden["code"]), (404, "not_found"))
        route_status, route_hidden, _headers = self.get_json(
            controlled_route, {"Cookie": attacker_cookie}
        )
        self.assertEqual((route_status, route_hidden["code"]), (404, "not_found"))
        status, forged, _headers = self.post_json(
            f"{endpoint}/create-order",
            {"paymentMethod": "upi", "email": "http-payment-owner@example.test"},
            attacker_auth,
        )
        self.assertEqual((status, forged["code"]), (404, "not_found"))

        status, forged_registration, _headers = self.post_json("/api/auth/register", {
            "name": "HTTP Payment Owner", "email": "HTTP-PAYMENT-OWNER@EXAMPLE.TEST",
            "password": "long payment owner password 123", "phone": "9999999999",
            "emailVerified": True,
        })
        self.assertEqual((status, forged_registration["code"]), (400, "invalid_registration"))
        status, owner, owner_headers = self.post_json("/api/auth/register", {
            "name": "HTTP Payment Owner", "email": "HTTP-PAYMENT-OWNER@EXAMPLE.TEST",
            "password": "long payment owner password 123", "phone": "9888888888",
        })
        self.assertEqual(status, 201)
        self.assertFalse(owner["user"]["emailVerified"])
        owner_cookie = owner_headers["Set-Cookie"].split(";", 1)[0]
        owner_headers_base = {
            "Cookie": owner_cookie,
            "Origin": "https://styledash.test",
            "Idempotency-Key": "payment-test-http-owner",
        }
        status, unverified, _headers = self.get_json(endpoint, {"Cookie": owner_cookie})
        self.assertEqual((status, unverified["code"]), (404, "not_found"))
        route_status, route_hidden, _headers = self.get_json(
            controlled_route, {"Cookie": owner_cookie}
        )
        self.assertEqual((route_status, route_hidden["code"]), (404, "not_found"))
        status, forged_verified, _headers = self.post_json(
            f"{endpoint}/create-order",
            {"paymentMethod": "upi", "emailVerified": True, "email": "http-payment-owner@example.test"},
            {**owner_headers_base, "X-CSRF-Token": owner["csrfToken"]},
        )
        self.assertEqual((status, forged_verified["code"]), (404, "not_found"))
        self.assertEqual(self.gateway.calls, [])

        status, reset_response, _headers = self.post_json(
            "/api/auth/password-reset/request", {"email": "http-payment-owner@example.test"}
        )
        self.assertEqual(status, 200)
        self.assertEqual(reset_response, {
            "success": True,
            "message": "If an account exists, reset instructions will be sent shortly.",
        })
        self.assertEqual(len(self.reset_deliveries), 1)
        reset_token = self.reset_deliveries[0][1]
        self.assertNotIn(reset_token, json.dumps(reset_response))
        status, confirmed, _headers = self.post_json(
            "/api/auth/password-reset/confirm",
            {"token": reset_token, "newPassword": "verified payment owner password 456"},
        )
        self.assertEqual(status, 200)
        self.assertNotIn(reset_token, json.dumps(confirmed))

        status, stale_session, _headers = self.get_json(
            "/api/auth/me", {"Cookie": owner_cookie}
        )
        self.assertEqual((status, stale_session["code"]), (401, "authentication_required"))
        status, stale_hidden, _headers = self.get_json(endpoint, {"Cookie": owner_cookie})
        self.assertEqual((status, stale_hidden["code"]), (404, "not_found"))

        status, refreshed, refreshed_headers = self.post_json("/api/auth/login", {
            "email": "HTTP-PAYMENT-OWNER@EXAMPLE.TEST",
            "password": "verified payment owner password 456",
            "emailVerified": False,
        })
        self.assertEqual(status, 200)
        self.assertTrue(refreshed["user"]["emailVerified"])
        owner_cookie = refreshed_headers["Set-Cookie"].split(";", 1)[0]
        owner_headers_base = {
            "Cookie": owner_cookie,
            "Origin": "https://styledash.test",
            "Idempotency-Key": "payment-test-http-owner",
        }

        with self.service.security.connect() as db:
            proof = db.execute(
                "SELECT email_verified,email_verified_at FROM users WHERE id=?",
                (refreshed["user"]["id"],),
            ).fetchone()
            self.assertEqual(proof["email_verified"], 1)
            self.assertIsNotNone(proof["email_verified_at"])
            db.execute("UPDATE users SET is_active=0 WHERE id=?", (refreshed["user"]["id"],))
        status, disabled_account, _headers = self.get_json(endpoint, {"Cookie": owner_cookie})
        self.assertEqual((status, disabled_account["code"]), (404, "not_found"))
        status, disabled_login, _headers = self.post_json("/api/auth/login", {
            "email": "http-payment-owner@example.test",
            "password": "verified payment owner password 456",
        })
        self.assertEqual((status, disabled_login["code"]), (401, "invalid_credentials"))
        with self.service.security.connect() as db:
            db.execute("UPDATE users SET is_active=1 WHERE id=?", (refreshed["user"]["id"],))
        status, refreshed, refreshed_headers = self.post_json("/api/auth/login", {
            "email": "http-payment-owner@example.test",
            "password": "verified payment owner password 456",
        })
        self.assertEqual(status, 200)
        owner_cookie = refreshed_headers["Set-Cookie"].split(";", 1)[0]
        owner_headers_base = {
            "Cookie": owner_cookie,
            "Origin": "https://styledash.test",
            "Idempotency-Key": "payment-test-http-owner",
        }

        status, metadata, _headers = self.get_json(endpoint, {"Cookie": owner_cookie})
        self.assertEqual(status, 200)
        self.assertEqual((metadata["product"]["amount"], metadata["product"]["currency"]), (1000, "INR"))
        self.assertNotIn("allowed", json.dumps(metadata).lower())
        status, cross_account, _headers = self.get_json(
            endpoint, {"Cookie": attacker_cookie}
        )
        self.assertEqual((status, cross_account["code"]), (404, "not_found"))
        route_request = urllib.request.Request(
            f"{self.base_url}{controlled_route}", headers={"Cookie": owner_cookie}
        )
        with urllib.request.urlopen(route_request) as route_response:
            self.assertEqual(route_response.status, 200)
            self.assertIn("StyleDash", route_response.read().decode())
        route_status, route_hidden, _headers = self.get_json(
            f"{controlled_route}/", {"Cookie": owner_cookie}
        )
        self.assertEqual((route_status, route_hidden["code"]), (404, "not_found"))

        status, csrf_failure, _headers = self.post_json(
            f"{endpoint}/create-order", {"paymentMethod": "upi"}, owner_headers_base
        )
        self.assertEqual((status, csrf_failure["code"]), (403, "csrf_failed"))
        owner_auth = {**owner_headers_base, "X-CSRF-Token": refreshed["csrfToken"]}
        status, created, _headers = self.post_json(
            f"{endpoint}/create-order", {"paymentMethod": "upi"}, owner_auth
        )
        self.assertEqual(status, 201)
        self.assertEqual((created["amount"], created["currency"]), (1000, "INR"))

        ordinary_payload = {
            "items": [{
                "productId": "styledash-payment-test-item",
                "variantId": "styledash-payment-test-item-validation",
                "quantity": 1,
            }],
            "address": {
                "name": "HTTP Payment Owner", "phone": "9999999999",
                "street": "123 Test Street", "city": "Neemuch", "pincode": "458441",
            },
            "deliveryMethod": "express", "paymentMethod": "cod", "couponCode": None,
        }
        status, ordinary_cod, _headers = self.post_json(
            "/api/place-cod-order", ordinary_payload,
            {**owner_auth, "Idempotency-Key": "payment-test-http-cod"},
        )
        self.assertEqual((status, ordinary_cod["code"]), (422, "invalid_product"))

        payment_id = "pay_payment_test_http_captured"
        self.gateway.payments[payment_id] = {
            "id": payment_id,
            "order_id": created["razorpayOrderId"],
            "amount": 1000,
            "currency": "INR",
            "status": "captured",
        }
        signature = hmac.new(
            b"test_secret_placeholder",
            f"{created['razorpayOrderId']}|{payment_id}".encode(),
            hashlib.sha256,
        ).hexdigest()
        status, verified, _headers = self.post_json("/api/verify-payment", {
            "styleDashOrderId": created["styleDashOrderId"],
            "razorpay_order_id": created["razorpayOrderId"],
            "razorpay_payment_id": payment_id,
            "razorpay_signature": signature,
        }, owner_auth)
        self.assertEqual(status, 200)
        self.assertEqual((verified["order"]["paymentStatus"], verified["order"]["status"]), ("paid", "payment_test_completed"))
        self.assertFalse(verified["order"]["inventoryCommitted"])

        self.service.payment_test_enabled = False
        status, disabled, _headers = self.get_json(endpoint, {"Cookie": owner_cookie})
        self.assertEqual((status, disabled["code"]), (404, "not_found"))
        route_status, route_hidden, _headers = self.get_json(
            controlled_route, {"Cookie": owner_cookie}
        )
        self.assertEqual((route_status, route_hidden["code"]), (404, "not_found"))
        status, disabled_create, _headers = self.post_json(
            f"{endpoint}/create-order", {"paymentMethod": "upi"},
            {**owner_auth, "Idempotency-Key": "payment-test-http-disabled"},
        )
        self.assertEqual((status, disabled_create["code"]), (404, "not_found"))
        status, historical, _headers = self.get_json(
            f"/api/orders/{created['styleDashOrderId']}", {"Cookie": owner_cookie}
        )
        self.assertEqual(status, 200)
        self.assertEqual(historical["order"]["adminLabels"], ["TEST", "NO FULFILLMENT REQUIRED"])
        self.assertEqual(historical["order"]["paymentStatus"], "paid")

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

    def test_password_reset_tokens_do_not_reach_or_leak_through_access_logs(self) -> None:
        marker = "TESTER_RESET_TOKEN_MUST_NOT_BE_LOGGED_1234567890"
        captured = io.StringIO()
        with redirect_stderr(captured):
            with urllib.request.urlopen(f"{self.base_url}/reset-password#{marker}") as response:
                self.assertEqual(response.status, 200)
            with urllib.request.urlopen(f"{self.base_url}/reset-password?token={marker}") as response:
                self.assertEqual(response.status, 200)
        logs = captured.getvalue()
        self.assertIn('GET /reset-password HTTP/1.1', logs)
        self.assertNotIn(marker, logs)
        self.assertIn('token=[redacted]', logs)

    def test_password_reset_response_is_not_delayed_by_smtp_delivery(self) -> None:
        def delayed_sender(_email, _token) -> None:
            time.sleep(0.3)

        delivery_queue = SERVER.PasswordResetDeliveryQueue(delayed_sender, max_pending=8)
        self.service.security.password_reset_sender = None
        self.service.security.password_reset_dispatcher = delivery_queue.dispatch
        try:
            registered = {
                "name": "Timing Customer", "email": "timing@example.test",
                "password": "long timing password 123", "phone": "9999999999",
            }
            self.assertEqual(self.post_json("/api/auth/register", registered)[0], 201)
            started = time.perf_counter()
            known_status, known, _headers = self.post_json("/api/auth/password-reset/request", {"email": "timing@example.test"})
            known_elapsed = time.perf_counter() - started
            started = time.perf_counter()
            unknown_status, unknown, _headers = self.post_json("/api/auth/password-reset/request", {"email": "timing-unknown@example.test"})
            unknown_elapsed = time.perf_counter() - started
            self.assertEqual((known_status, known), (unknown_status, unknown))
            self.assertLess(known_elapsed, 0.2)
            self.assertLess(abs(known_elapsed - unknown_elapsed), 0.15)
        finally:
            delivery_queue.close()


if __name__ == "__main__":
    unittest.main()
