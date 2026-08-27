from __future__ import annotations

import importlib.util
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
from unittest.mock import patch
from pathlib import Path

import pyotp
from cryptography.fernet import Fernet


ROOT = Path(__file__).resolve().parents[2]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SECURITY = load("styledash_security_test", ROOT / "scripts" / "styledash_security.py")
ADMIN = load("styledash_admin_test", ROOT / "scripts" / "styledash_admin.py")
ADMIN_SERVER = load("styledash_admin_server_test", ROOT / "scripts" / "termux-admin-server.py")


class AdminStoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.database = self.root / "styledash.db"
        self.key = Fernet.generate_key().decode()
        self.customers = SECURITY.SecurityStore(self.database, self.key)
        self.store = ADMIN.AdminStore(self.database, self.key)
        self.secret = pyotp.random_base32()
        self.recovery = ["ABCDEF123456", "123456ABCDEF"]
        self.admin = self.store.create_admin("owner@example.test", "long administrator password 123", self.secret, self.recovery)

    def tearDown(self):
        self.temporary.cleanup()

    def assert_error(self, code, callback):
        with self.assertRaises(ADMIN.SecurityError) as caught:
            callback()
        self.assertEqual(caught.exception.code, code)

    def login(self):
        challenge = self.store.begin_login({"username": "owner@example.test", "password": "long administrator password 123"}, "127.0.0.1")
        return challenge, self.store.verify_totp(challenge, pyotp.TOTP(self.secret).now(), "127.0.0.1")

    def test_separate_password_totp_session_cookie_and_csrf(self):
        self.assert_error("invalid_admin_credentials", lambda: self.store.begin_login({"username": "owner@example.test", "password": "wrong administrator password"}, "client-a"))
        challenge = self.store.begin_login({"username": "owner@example.test", "password": "long administrator password 123"}, "client-b")
        self.assert_error("admin_authentication_required", lambda: self.store.authenticate(challenge))
        self.assert_error("invalid_admin_totp", lambda: self.store.verify_totp(challenge, "000000", "client-b"))
        admin, raw, csrf = self.store.verify_totp(challenge, pyotp.TOTP(self.secret).now(), "client-b")
        self.assertEqual(admin["id"], self.admin["id"])
        self.store.authenticate(raw)
        self.store.verify_csrf(raw, csrf)
        self.assert_error("admin_csrf_failed", lambda: self.store.verify_csrf(raw, "wrong"))
        cookie = self.store.session_cookie(raw)
        for flag in ("styledash_admin_session=", "HttpOnly", "SameSite=Strict", "Path=/"):
            self.assertIn(flag, cookie)
        self.assertNotIn("Secure", cookie)
        with self.store.connect() as db:
            self.assertIsNotNone(db.execute("SELECT 1 FROM admin_sessions WHERE token_hash=?", (ADMIN.token_hash(raw),)).fetchone())
            self.assertIsNone(db.execute("SELECT 1 FROM admin_sessions WHERE token_hash=?", (raw,)).fetchone())
            encrypted = db.execute("SELECT encrypted_totp_secret FROM admin_users WHERE id=?", (admin["id"],)).fetchone()[0]
            self.assertNotIn(self.secret, bytes(encrypted).decode("ascii"))

    def test_recovery_code_single_use_session_expiry_and_identity_separation(self):
        challenge = self.store.begin_login({"username": "owner@example.test", "password": "long administrator password 123"}, "recovery-a")
        _admin, raw, _csrf = self.store.verify_totp(challenge, self.recovery[0], "recovery-a")
        with self.assertRaises(SECURITY.SecurityError) as caught:
            self.customers.authenticate(raw)
        self.assertEqual(caught.exception.code, "authentication_required")
        with self.store.connect() as db:
            db.execute("UPDATE admin_sessions SET idle_expires_at='2000-01-01T00:00:00+00:00' WHERE token_hash=?", (ADMIN.token_hash(raw),))
        self.assert_error("admin_session_expired", lambda: self.store.authenticate(raw))
        repeat = self.store.begin_login({"username": "owner@example.test", "password": "long administrator password 123"}, "recovery-b")
        self.assert_error("invalid_admin_totp", lambda: self.store.verify_totp(repeat, self.recovery[0], "recovery-b"))

    def test_admin_operations_are_audited_and_state_machine_enforced(self):
        user, _raw, _csrf = self.customers.register({"name": "Customer A", "email": "customer-a@example.test", "password": "long customer password 123", "phone": "9999999999"})
        vendor = self.customers.create_vendor_application(user["id"], {"storeName": "Test Store", "ownerName": "Customer A", "email": user["email"], "phone": "9999999999", "category": "Clothing & Fashion", "address": "123 Test Market", "pincode": "458441", "description": "Test vendor application"})
        app = ADMIN_SERVER.AdminApplication(self.database, self.key, ROOT / "server/payment-data/catalog.json", ROOT / "server/payment-data/settings.json", self.root / "data")
        with app.payments.store.lock:
            app.payments.store.state["orders"]["ORDER-ADMIN"] = {"id": "ORDER-ADMIN", "userId": user["id"], "status": "placed", "paymentStatus": "paid", "createdAt": "2026-08-13T00:00:00+00:00"}
            app.payments.store.state["operationalAlerts"]["refund.failed:rfnd_admin_test"] = {
                "id": "refund.failed:rfnd_admin_test", "type": "refund.failed",
                "entityId": "rfnd_admin_test", "razorpayPaymentId": "pay_admin_test",
                "styleDashOrderId": "ORDER-ADMIN", "status": "open",
                "recordedAt": "2026-08-13T00:00:00+00:00",
            }
            app.payments.store.save()
        alerts = app.payment_alerts()
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["styleDashOrderId"], "ORDER-ADMIN")
        order = app.update_order_status(self.admin["id"], "ORDER-ADMIN", "confirmed")
        self.assertEqual(order["status"], "confirmed")
        self.assert_error("invalid_transition", lambda: app.update_order_status(self.admin["id"], "ORDER-ADMIN", "delivered"))
        inventory = app.adjust_inventory(self.admin["id"], "sd-prod-001-var-2", 3)
        self.assertEqual(inventory["after"], inventory["before"] + 3)
        reviewed = self.store.review_vendor(self.admin["id"], vendor["id"], "approved")
        self.assertEqual(reviewed["status"], "approved")
        disabled = self.store.set_customer_active(self.admin["id"], user["id"], False)
        self.assertFalse(disabled["active"])
        actions = {row["action"] for row in self.store.audit()}
        self.assertTrue({"order_status", "inventory_adjustment", "vendor_approved", "customer_disabled"}.issubset(actions))

    def test_order_cancellation_sends_owner_notification(self):
        app = ADMIN_SERVER.AdminApplication(
            self.database,
            self.key,
            ROOT / "server/payment-data/catalog.json",
            ROOT / "server/payment-data/settings.json",
            self.root / "data-cancel-notify",
        )

        with app.payments.store.lock:
            app.payments.store.state["orders"]["ORDER-CANCEL-NOTIFY"] = {
                "id": "ORDER-CANCEL-NOTIFY",
                "userId": "customer-cancel-notify",
                "status": "placed",
                "paymentStatus": "pending",
                "paymentMethod": "cod",
                "grandTotal": 1072,
                "inventoryCommitted": False,
                "createdAt": "2026-08-15T00:00:00+00:00",
            }
            app.payments.store.save()

        with patch.object(
            ADMIN_SERVER,
            "owner_notifier",
        ) as notifier_factory:
            notifier = notifier_factory.return_value

            result = app.update_order_status(
                self.admin["id"],
                "ORDER-CANCEL-NOTIFY",
                "cancelled",
            )

            self.assertEqual(result["status"], "cancelled")
            self.assertEqual(notifier.send.call_count, 1)

            notification = notifier.send.call_args.kwargs

            self.assertEqual(
                notification["event"],
                "order_cancelled",
            )
            self.assertEqual(
                notification["priority"],
                5,
            )
            self.assertIn(
                "ORDER-CANCEL-NOTIFY",
                notification["message"],
            )
            self.assertIn(
                "?1072",
                notification["message"],
            )
            self.assertIn(
                "Payment: COD",
                notification["message"],
            )
            self.assertIn(
                "Status: Cancelled",
                notification["message"],
            )

            # A second cancellation is an invalid state transition,
            # therefore it must not produce another notification.
            self.assert_error(
                "invalid_transition",
                lambda: app.update_order_status(
                    self.admin["id"],
                    "ORDER-CANCEL-NOTIFY",
                    "cancelled",
                ),
            )

            self.assertEqual(notifier.send.call_count, 1)

    def test_cancellation_notification_failure_does_not_break_cancellation(self):
        app = ADMIN_SERVER.AdminApplication(
            self.database,
            self.key,
            ROOT / "server/payment-data/catalog.json",
            ROOT / "server/payment-data/settings.json",
            self.root / "data-cancel-failure",
        )

        with app.payments.store.lock:
            app.payments.store.state["orders"]["ORDER-CANCEL-FAILURE"] = {
                "id": "ORDER-CANCEL-FAILURE",
                "userId": "customer-cancel-failure",
                "status": "placed",
                "paymentStatus": "pending",
                "paymentMethod": "cod",
                "grandTotal": 999,
                "inventoryCommitted": False,
                "createdAt": "2026-08-15T00:00:00+00:00",
            }
            app.payments.store.save()

        with patch.object(
            ADMIN_SERVER,
            "owner_notifier",
            side_effect=RuntimeError(
                "simulated notification configuration failure"
            ),
        ):
            result = app.update_order_status(
                self.admin["id"],
                "ORDER-CANCEL-FAILURE",
                "cancelled",
            )

        self.assertEqual(result["status"], "cancelled")

        persisted = app.get_order("ORDER-CANCEL-FAILURE")

        self.assertEqual(
            persisted["status"],
            "cancelled",
        )

        actions = [
            entry
            for entry in self.store.audit()
            if entry["target_id"] == "ORDER-CANCEL-FAILURE"
        ]

        self.assertTrue(
            any(
                entry["action"] == "order_status"
                and entry["result"] == "success"
                for entry in actions
            )
        )


    def test_admin_inventory_threshold_notifications(self):
        app = ADMIN_SERVER.AdminApplication(
            self.database,
            self.key,
            ROOT / "server/payment-data/catalog.json",
            ROOT / "server/payment-data/settings.json",
            self.root / "data-inventory-notify",
        )

        variant_id = "sd-prod-001-var-2"

        with app.payments.store.lock:
            app.payments.store.state["inventory"][variant_id] = 6
            app.payments.store.save()

        with patch.object(
            ADMIN_SERVER,
            "owner_notifier",
        ) as notifier_factory:
            notifier = notifier_factory.return_value

            # 6 -> 5: one low-stock alert.
            first = app.adjust_inventory(
                self.admin["id"],
                variant_id,
                -1,
            )

            self.assertEqual(first["before"], 6)
            self.assertEqual(first["after"], 5)

            self.assertEqual(
                notifier.send.call_count,
                1,
            )

            self.assertEqual(
                notifier.send.call_args.kwargs["event"],
                "inventory_low_stock",
            )

            # 5 -> 4: no repeated low-stock alert.
            second = app.adjust_inventory(
                self.admin["id"],
                variant_id,
                -1,
            )

            self.assertEqual(second["after"], 4)

            self.assertEqual(
                notifier.send.call_count,
                1,
            )

            # Prepare an independent 1 -> 0 crossing.
            with app.payments.store.lock:
                app.payments.store.state["inventory"][
                    variant_id
                ] = 1
                app.payments.store.save()

            third = app.adjust_inventory(
                self.admin["id"],
                variant_id,
                -1,
            )

            self.assertEqual(third["after"], 0)

            self.assertEqual(
                notifier.send.call_count,
                2,
            )

            events = [
                call.kwargs["event"]
                for call in notifier.send.call_args_list
            ]

            self.assertEqual(
                events,
                [
                    "inventory_low_stock",
                    "inventory_out_of_stock",
                ],
            )

            out_notification = (
                notifier.send.call_args_list[-1].kwargs
            )

            self.assertIn(
                "Remaining: 0",
                out_notification["message"],
            )

    def test_paid_order_reconciliation_can_trigger_low_stock_notification(self):
        app = ADMIN_SERVER.AdminApplication(
            self.database,
            self.key,
            ROOT / "server/payment-data/catalog.json",
            ROOT / "server/payment-data/settings.json",
            self.root / "data-reconcile-notify",
        )

        variant_id = "sd-prod-001-var-2"

        with app.payments.store.lock:
            app.payments.store.state["inventory"][variant_id] = 6

            app.payments.store.state["orders"][
                "ORDER-RECONCILE-LOW-STOCK"
            ] = {
                "id": "ORDER-RECONCILE-LOW-STOCK",
                "userId": "customer-reconcile",
                "status": "payment_review_required",
                "paymentStatus": "paid",
                "paymentMethod": "card",
                "grandTotal": 1072,
                "inventoryCommitted": False,
                "requiresAdminAttention": True,
                "inventoryShortfall": True,
                "items": [{
                    "productId": "sd-prod-001",
                    "variantId": variant_id,
                    "quantity": 1,
                }],
                "statusHistory": [],
                "createdAt": "2026-08-15T00:00:00+00:00",
                "updatedAt": "2026-08-15T00:00:00+00:00",
            }

            app.payments.store.save()

        with patch.object(
            ADMIN_SERVER,
            "owner_notifier",
        ) as notifier_factory:
            notifier = notifier_factory.return_value

            result = app.update_order_status(
                self.admin["id"],
                "ORDER-RECONCILE-LOW-STOCK",
                "placed",
            )

            self.assertEqual(
                result["status"],
                "placed",
            )

            self.assertTrue(
                result["inventoryCommitted"]
            )

            self.assertEqual(
                app.payments.store.state["inventory"][
                    variant_id
                ],
                5,
            )

            self.assertEqual(
                notifier.send.call_count,
                1,
            )

            notification = notifier.send.call_args.kwargs

            self.assertEqual(
                notification["event"],
                "inventory_low_stock",
            )

            self.assertIn(
                "Remaining: 5",
                notification["message"],
            )


    def test_payment_test_order_is_prominently_labelled_and_cannot_enter_fulfillment(self):
        app = ADMIN_SERVER.AdminApplication(
            self.database, self.key,
            ROOT / "server/payment-data/catalog.json", ROOT / "server/payment-data/settings.json",
            self.root / "data",
        )
        with app.payments.store.lock:
            app.payments.store.state["orders"]["ORDER-PAYMENT-TEST"] = {
                "id": "ORDER-PAYMENT-TEST",
                "userId": "usr_payment_test_owner",
                "status": "payment_test_completed",
                "paymentStatus": "paid",
                "isPaymentTestOrder": True,
                "fulfillmentRequired": False,
                "adminLabels": ["TEST", "NO FULFILLMENT REQUIRED"],
                "createdAt": "2026-08-14T00:00:00+00:00",
            }
            app.payments.store.save()

        listed = app.list_orders("ORDER-PAYMENT-TEST")
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["adminLabels"], ["TEST", "NO FULFILLMENT REQUIRED"])
        self.assertFalse(listed[0]["fulfillmentRequired"])
        self.assert_error(
            "no_fulfillment_order",
            lambda: app.update_order_status(self.admin["id"], "ORDER-PAYMENT-TEST", "confirmed"),
        )
        unchanged = app.get_order("ORDER-PAYMENT-TEST")
        self.assertEqual(unchanged["status"], "payment_test_completed")

        admin_ui = (ROOT / "server/admin/admin.js").read_text(encoding="utf-8")
        self.assertIn("NO FULFILLMENT REQUIRED", admin_ui)
        self.assertIn("Do not pack, dispatch, deliver, or adjust fashion inventory.", admin_ui)
        self.assertIn("paymentTest?", admin_ui)


class AdminHttpTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.database = self.root / "styledash.db"
        self.key = Fernet.generate_key().decode()
        SECURITY.SecurityStore(self.database, self.key)
        store = ADMIN.AdminStore(self.database, self.key)
        self.secret = pyotp.random_base32()
        store.create_admin("local-owner", "long administrator password 123", self.secret, ["ABCDEF123456"])
        self.server = ADMIN_SERVER.create_admin_server(
            "127.0.0.1", 0, self.database, self.key,
            ROOT / "server/payment-data/catalog.json", ROOT / "server/payment-data/settings.json",
            self.root / "data", ROOT / "server/admin", self.root / "backups",
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.jar = CookieJar()
        self.client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(timeout=2)
        self.temporary.cleanup()

    def request(self, path, payload=None, headers=None, method=None):
        data = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(self.base + path, data=data, method=method, headers={"Host": "127.0.0.1:8081", "Origin": "http://127.0.0.1:8081", **(headers or {})})
        if data is not None: request.add_header("Content-Type", "application/json")
        try: response = self.client.open(request)
        except urllib.error.HTTPError as error:
            body = json.loads(error.read()); status = error.code; response_headers = error.headers; error.close(); return status, body, response_headers
        with response:
            content = response.read()
            return response.status, json.loads(content) if response.headers.get_content_type() == "application/json" else content.decode(), response.headers

    def test_loopback_host_password_totp_and_separate_cookie(self):
        status, html, _headers = self.request("/", headers={"Origin": ""})
        self.assertEqual(status, 200); self.assertIn("StyleDash Local Administration", html)
        bad = urllib.request.Request(self.base + "/", headers={"Host": "evil.example"})
        with self.assertRaises(urllib.error.HTTPError) as caught: urllib.request.urlopen(bad)
        self.assertEqual(caught.exception.code, 421); caught.exception.close()
        status, body, _headers = self.request("/api/admin/orders")
        self.assertEqual((status, body["code"]), (401, "admin_authentication_required"))
        customer_cookie = urllib.request.Request(
            self.base + "/api/admin/orders",
            headers={
                "Host": "127.0.0.1:8081",
                "Origin": "http://127.0.0.1:8081",
                "Cookie": "__Host-styledash_session=customer-cookie-is-not-an-admin-session",
            },
        )
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(customer_cookie)
        self.assertEqual(caught.exception.code, 401); caught.exception.close()
        status, body, _headers = self.request("/api/admin/login", {"username": "local-owner", "password": "wrong administrator password"}, method="POST")
        self.assertEqual((status, body["code"]), (401, "invalid_admin_credentials"))
        status, body, _headers = self.request("/api/admin/login", {"username": "local-owner", "password": "long administrator password 123"}, method="POST")
        self.assertEqual(status, 200); self.assertTrue(body["requiresTotp"])
        status, body, _headers = self.request("/api/admin/me")
        self.assertEqual((status, body["code"]), (401, "admin_authentication_required"))
        status, body, _headers = self.request("/api/admin/totp", {"code": pyotp.TOTP(self.secret).now()}, method="POST")
        self.assertEqual(status, 200); csrf = body["csrfToken"]
        status, body, _headers = self.request("/api/admin/me")
        self.assertEqual(status, 200)
        status, body, _headers = self.request("/api/admin/orders")
        self.assertEqual(status, 200); self.assertEqual(body["orders"], [])
        status, body, _headers = self.request("/api/admin/payment-alerts")
        self.assertEqual(status, 200); self.assertEqual(body["alerts"], [])
        status, body, _headers = self.request("/api/admin/logout", {}, method="POST")
        self.assertEqual((status, body["code"]), (403, "admin_csrf_failed"))
        status, body, _headers = self.request("/api/admin/logout", {}, headers={"X-CSRF-Token": csrf}, method="POST")
        self.assertEqual(status, 200)

    def test_shop_transition_success_does_not_depend_on_admin_catalog_refresh(self):
        customers = SECURITY.SecurityStore(self.database, self.key)
        user, _raw, _csrf = customers.register({
            "name": "Seller Test", "email": "seller-transition@example.test",
            "password": "long seller password 123", "phone": "9999999998",
        })
        shops = ADMIN_SERVER.ShopWorkflow(self.database)
        application = shops.create_draft(user["id"], {
            "shopName": "Transition Shop", "ownerName": "Seller Test",
            "category": "Clothing & Fashion", "description": "A complete local shop description.",
            "address": "123 Main Market", "city": "Neemuch",
            "state": "Madhya Pradesh", "pincode": "458441",
        })
        shops.submit_application(user["id"])

        self.request("/api/admin/login", {"username": "local-owner", "password": "long administrator password 123"}, method="POST")
        status, body, _headers = self.request("/api/admin/totp", {"code": pyotp.TOTP(self.secret).now()}, method="POST")
        self.assertEqual(status, 200)
        csrf = body["csrfToken"]
        app = self.server.RequestHandlerClass.application
        with patch.object(app.payments, "refresh_shop_products", side_effect=RuntimeError("refresh must not run")) as refresh:
            status, body, _headers = self.request(
                f"/api/admin/vendors/{application['id']}", {"status": "UNDER_REVIEW", "reason": None},
                headers={"X-CSRF-Token": csrf}, method="PATCH",
            )
        self.assertEqual((status, body["application"]["status"]), (200, "UNDER_REVIEW"))
        refresh.assert_not_called()

        for target in ("APPROVED", "ACTIVE"):
            status, body, _headers = self.request(
                f"/api/admin/vendors/{application['id']}", {"status": target, "reason": None},
                headers={"X-CSRF-Token": csrf}, method="PATCH",
            )
            self.assertEqual((status, body["application"]["status"]), (200, target))

        product = shops.create_product_draft(user["id"], {
            "name": "Transition Tee", "description": "A reviewed transition product for handler coverage.",
            "brand": "Local", "department": "men", "category": "Clothing & Fashion",
            "pricePaise": 50000, "originalPricePaise": 60000, "inventory": 3,
            "size": "M", "colourName": "Black", "colourHex": "#000000",
            "imageUrls": ["https://example.test/transition.jpg"], "attributes": {},
        })
        shops.submit_product(user["id"], product["id"])
        with patch.object(app.payments, "refresh_shop_products", side_effect=RuntimeError("refresh must not run")) as refresh:
            status, body, _headers = self.request(
                f"/api/admin/shop-products/{product['id']}", {"status": "UNDER_REVIEW", "reason": None},
                headers={"X-CSRF-Token": csrf}, method="PATCH",
            )
        self.assertEqual((status, body["product"]["status"]), (200, "UNDER_REVIEW"))
        refresh.assert_not_called()

    def test_shop_fulfillment_override_requires_admin_csrf_and_is_audited(self):
        customers = SECURITY.SecurityStore(self.database, self.key)
        user, _raw, _csrf = customers.register({
            "name": "Seller Override", "email": "seller-override@example.test",
            "password": "long seller override password 123", "phone": "9999999997",
        })
        shops = ADMIN_SERVER.ShopWorkflow(self.database)
        application = shops.create_draft(user["id"], {
            "shopName": "Override Shop", "ownerName": "Seller Override",
            "category": "Clothing & Fashion", "description": "A complete override test shop description.",
            "address": "44 Main Market", "city": "Neemuch",
            "state": "Madhya Pradesh", "pincode": "458441",
        })
        shops.submit_application(user["id"])
        with shops.connect() as db:
            admin_id = db.execute("SELECT id FROM admin_users LIMIT 1").fetchone()[0]
        for status in ("UNDER_REVIEW", "APPROVED", "ACTIVE"):
            shops.admin_transition_application(admin_id, application["id"], status)
        product = shops.create_product_draft(user["id"], {
            "name": "Override Tee", "description": "A tracked seller product for private admin override testing.",
            "brand": "Local", "department": "men", "category": "Clothing & Fashion",
            "pricePaise": 45000, "originalPricePaise": 50000, "inventory": 4,
            "size": "M", "colourName": "Black", "colourHex": "#000000",
            "imageUrls": ["https://example.test/override.jpg"], "attributes": {},
        })
        app = self.server.RequestHandlerClass.application
        with app.payments.store.lock:
            app.payments.store.state["orders"]["ORDER-SHOP-OVERRIDE"] = {
                "id": "ORDER-SHOP-OVERRIDE", "userId": user["id"],
                "status": "placed", "paymentStatus": "paid", "paymentMethod": "upi",
                "fulfillmentRequired": True, "createdAt": "2026-08-27T10:00:00+00:00",
                "items": [{"productId": product["id"], "quantity": 1}],
                "address": {"name": "Buyer", "phone": "9999999996"},
            }
            app.payments.store.save()

        status, body, _headers = self.request("/api/admin/orders?q=ORDER-SHOP-OVERRIDE")
        self.assertEqual((status, body["code"]), (401, "admin_authentication_required"))
        self.request("/api/admin/login", {"username": "local-owner", "password": "long administrator password 123"}, method="POST")
        status, body, _headers = self.request(
            "/api/admin/totp", {"code": pyotp.TOTP(self.secret).now()}, method="POST"
        )
        self.assertEqual(status, 200)
        csrf = body["csrfToken"]
        status, body, _headers = self.request("/api/admin/orders?q=ORDER-SHOP-OVERRIDE")
        self.assertEqual(status, 200)
        order = body["orders"][0]
        self.assertEqual(order["shopFulfillments"][0]["shopName"], "Override Shop")
        self.assertEqual(order["shopFulfillments"][0]["status"], "NEW")
        segment = order["shopFulfillments"][0]["applicationId"]

        path = f"/api/admin/orders/ORDER-SHOP-OVERRIDE/fulfillment/{segment}"
        payload = {
            "status": "SHIPPED", "carrier": "Delhivery",
            "trackingNumber": "DLV-ADMIN-HTTP", "reason": "Correct seller shipping state",
        }
        status, body, _headers = self.request(path, payload, method="PATCH")
        self.assertEqual((status, body["code"]), (403, "admin_csrf_failed"))
        status, body, _headers = self.request(
            path, payload, headers={"X-CSRF-Token": csrf}, method="PATCH"
        )
        self.assertEqual((status, body["fulfillment"]["status"]), (200, "SHIPPED"))
        self.assertEqual(body["fulfillment"]["shipping"]["trackingNumber"], "DLV-ADMIN-HTTP")
        status, body, _headers = self.request(
            "/api/admin/orders?q=ORDER-SHOP-OVERRIDE"
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["orders"][0]["shopFulfillments"][0]["status"], "SHIPPED")
        self.assertEqual(
            body["orders"][0]["shopFulfillments"][0]["shipping"]["trackingNumber"],
            "DLV-ADMIN-HTTP",
        )
        status, body, _headers = self.request(
            "/api/admin/orders/ORDER-SHOP-OVERRIDE/fulfillment/not-this-shop",
            {"status": "READY", "reason": "Must not cross shop boundary"},
            headers={"X-CSRF-Token": csrf}, method="PATCH",
        )
        self.assertEqual((status, body["code"]), (404, "order_shop_segment_not_found"))
        with app.payments.store.lock:
            app.payments.store.state["orders"]["ORDER-SHOP-OVERRIDE"]["status"] = "cancelled"
            app.payments.store.save()
        status, body, _headers = self.request(
            path, {"status": "READY", "reason": "Cancelled order must remain stopped"},
            headers={"X-CSRF-Token": csrf}, method="PATCH",
        )
        self.assertEqual((status, body["code"]), (409, "order_not_fulfillable"))
        status, body, _headers = self.request("/api/admin/audit")
        self.assertEqual(status, 200)
        self.assertIn("shop_fulfillment_override", {row["action"] for row in body["audit"]})
        admin_ui = (ROOT / "server/admin/admin.js").read_text(encoding="utf-8")
        self.assertIn("Override shop fulfillment", admin_ui)
        self.assertIn("administrator override", admin_ui)

    def test_return_review_requires_admin_csrf_and_is_audited(self):
        customers = SECURITY.SecurityStore(self.database, self.key)
        seller, _raw, _csrf = customers.register({
            "name": "Return Seller", "email": "return-seller@example.test",
            "password": "long return seller password 123", "phone": "9999999961",
        })
        buyer, _raw, _csrf = customers.register({
            "name": "Return Buyer", "email": "return-buyer@example.test",
            "password": "long return buyer password 123", "phone": "9999999962",
        })
        shops = ADMIN_SERVER.ShopWorkflow(self.database)
        application = shops.create_draft(seller["id"], {
            "shopName": "Return Review Shop", "ownerName": "Return Seller",
            "category": "Clothing & Fashion", "description": "A return review test shop.",
            "address": "77 Main Market", "city": "Neemuch",
            "state": "Madhya Pradesh", "pincode": "458441",
        })
        shops.submit_application(seller["id"])
        with shops.connect() as db:
            admin_id = db.execute("SELECT id FROM admin_users LIMIT 1").fetchone()[0]
        for status in ("UNDER_REVIEW", "APPROVED", "ACTIVE"):
            shops.admin_transition_application(admin_id, application["id"], status)
        product = shops.create_product_draft(seller["id"], {
            "name": "Return Review Tee", "description": "A return-review product fixture.",
            "brand": "Local", "department": "men", "category": "Clothing & Fashion",
            "pricePaise": 50000, "originalPricePaise": 55000, "inventory": 3,
            "size": "M", "colourName": "Black", "colourHex": "#000000",
            "imageUrls": ["https://example.test/return-review.jpg"], "attributes": {},
        })
        return_request = shops.create_return_request(
            buyer["id"], "ORDER-RETURN-REVIEW",
            {"productId": product["id"], "productName": product["name"],
             "variantId": f"{product['id']}-var-1", "quantity": 1, "unitPrice": 500},
            {"applicationId": application["id"], "shopName": "Return Review Shop"},
            {"requestType": "ISSUE_RETURN", "reason": "DAMAGED", "details": "Damaged seam", "quantity": 1},
        )
        app = self.server.RequestHandlerClass.application
        with app.payments.store.lock:
            app.payments.store.state["orders"]["ORDER-CANCEL-REVIEW"] = {
                "id": "ORDER-CANCEL-REVIEW", "userId": buyer["id"],
                "status": "placed", "paymentStatus": "pending", "paymentMethod": "cod",
                "inventoryCommitted": False, "items": [],
                "address": {"name": "Return Buyer", "phone": "9999999962"},
                "cancellationRequest": {
                    "status": "REQUESTED", "reason": "CUSTOMER_REQUEST",
                    "details": "Please cancel", "createdAt": "2026-08-27T12:00:00+00:00",
                    "updatedAt": "2026-08-27T12:00:00+00:00",
                },
                "createdAt": "2026-08-27T12:00:00+00:00", "updatedAt": "2026-08-27T12:00:00+00:00",
            }
            app.payments.store.save()
        status, body, _headers = self.request("/api/admin/returns")
        self.assertEqual((status, body["code"]), (401, "admin_authentication_required"))
        self.request("/api/admin/login", {
            "username": "local-owner", "password": "long administrator password 123"
        }, method="POST")
        status, body, _headers = self.request(
            "/api/admin/totp", {"code": pyotp.TOTP(self.secret).now()}, method="POST"
        )
        self.assertEqual(status, 200)
        csrf = body["csrfToken"]
        status, body, _headers = self.request("/api/admin/returns")
        self.assertEqual(status, 200)
        self.assertEqual(body["items"][0]["id"], return_request["id"])
        self.assertEqual(body["cancellations"][0]["orderId"], "ORDER-CANCEL-REVIEW")

        item_path = f"/api/admin/returns/items/{return_request['id']}"
        status, body, _headers = self.request(item_path, {"status": "UNDER_REVIEW"}, method="PATCH")
        self.assertEqual((status, body["code"]), (403, "admin_csrf_failed"))
        status, body, _headers = self.request(
            item_path, {"status": "UNDER_REVIEW"}, headers={"X-CSRF-Token": csrf}, method="PATCH"
        )
        self.assertEqual((status, body["request"]["status"]), (200, "UNDER_REVIEW"))
        status, body, _headers = self.request(
            item_path, {"status": "REFUNDED"}, headers={"X-CSRF-Token": csrf}, method="PATCH"
        )
        self.assertEqual((status, body["code"]), (400, "invalid_return_status"))
        cancel_path = "/api/admin/returns/cancellations/ORDER-CANCEL-REVIEW"
        status, body, _headers = self.request(
            cancel_path, {"status": "UNDER_REVIEW"}, headers={"X-CSRF-Token": csrf}, method="PATCH"
        )
        self.assertEqual((status, body["request"]["status"]), (200, "UNDER_REVIEW"))
        status, body, _headers = self.request(
            cancel_path, {"status": "APPROVED"}, headers={"X-CSRF-Token": csrf}, method="PATCH"
        )
        self.assertEqual((status, body["request"]["status"]), (200, "APPROVED"))
        with app.payments.store.lock:
            self.assertEqual(app.payments.store.state["orders"]["ORDER-CANCEL-REVIEW"]["status"], "placed")
        status, body, _headers = self.request(
            cancel_path, {"status": "REJECTED", "note": "Too late"},
            headers={"X-CSRF-Token": csrf}, method="PATCH",
        )
        self.assertEqual((status, body["code"]), (409, "invalid_cancellation_request_transition"))

        status, body, _headers = self.request(
            "/api/admin/orders/ORDER-CANCEL-REVIEW/status", {"status": "cancelled"},
            headers={"X-CSRF-Token": csrf}, method="PATCH",
        )
        self.assertEqual((status, body["order"]["status"]), (200, "cancelled"))
        self.assertEqual(body["order"]["cancellationRequest"]["status"], "CANCELLED")
        status, body, _headers = self.request("/api/admin/audit")
        self.assertEqual(status, 200)
        actions = {row["action"] for row in body["audit"]}
        self.assertIn("return_request_status", actions)
        self.assertIn("cancellation_request_status", actions)
        self.assertIn("order_status", actions)
        admin_ui = (ROOT / "server/admin/admin.js").read_text(encoding="utf-8")
        admin_html = (ROOT / "server/admin/index.html").read_text(encoding="utf-8")
        self.assertIn("renderReturns", admin_ui)
        self.assertIn("Approving a request never performs a Razorpay refund", admin_ui)
        self.assertIn('data-tab="returns"', admin_html)
    def test_non_loopback_bind_refused(self):
        with self.assertRaises(RuntimeError):
            ADMIN_SERVER.create_admin_server("0.0.0.0", 0, self.database, self.key, ROOT / "server/payment-data/catalog.json", ROOT / "server/payment-data/settings.json", self.root / "data2", ROOT / "server/admin", self.root / "backups")


if __name__ == "__main__":
    unittest.main()
