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

    def test_private_admin_owner_mobile_required_email_optional_and_otp_binds(self):
        owner = self.store.create_customer_account(self.admin["id"], {
            "name": "Phone First Owner", "phone": "9876501234", "password": "TempPass8!",
        })
        self.assertIsNone(owner["email"])
        self.assertEqual(owner["phone"], "+919876501234")
        self.assert_error(
            "invalid_phone",
            lambda: self.store.create_customer_account(self.admin["id"], {
                "name": "Missing Phone", "email": "missing-phone@example.test", "password": "TempPass8!",
            }),
        )
        self.customers.firebase_verifier = lambda _token: {
            "uid": "firebase-phone-first-owner",
            "phone_number": "+919876501234",
            "firebase": {"sign_in_provider": "phone"},
        }
        logged_in, _raw, _csrf, created = self.customers.federated_session(
            "phone", {"idToken": "x" * 24}
        )
        self.assertEqual(logged_in["id"], owner["id"])
        self.assertFalse(created)
        with self.store.connect() as db:
            identity = db.execute(
                "SELECT provider_subject,verified_phone FROM customer_auth_identities WHERE user_id=? AND provider='phone'",
                (owner["id"],),
            ).fetchone()
        self.assertEqual(identity["provider_subject"], "firebase-phone-first-owner")
        self.assertEqual(identity["verified_phone"], "+919876501234")
        self.assertEqual(self.store.customers("501234")[0]["id"], owner["id"])
        app = ADMIN_SERVER.AdminApplication(
            self.database, self.key, ROOT / "server/payment-data/catalog.json",
            ROOT / "server/payment-data/settings.json", self.root / "data-phone-owner",
        )
        shop = app.shops.admin_create_application(self.admin["id"], owner["id"], {
            "shopName": "Phone First Store", "ownerName": "Phone First Owner",
            "category": "Clothing & Fashion",
            "description": "A local store whose owner signs in primarily with mobile OTP.",
            "address": "12 Neemuch Main Market", "city": "Neemuch",
            "state": "Madhya Pradesh", "pincode": "458441",
            "businessInformation": "Admin-assisted phone-first onboarding.",
        })
        self.assertEqual(shop["status"], "ACTIVE")
        self.assertIsNone(shop["registeredEmail"])
        self.assertEqual(shop["registeredMobile"], "+919876501234")

    def test_private_admin_can_create_owner_store_and_multisize_product(self):
        app = ADMIN_SERVER.AdminApplication(self.database, self.key, ROOT / "server/payment-data/catalog.json", ROOT / "server/payment-data/settings.json", self.root / "data")
        owner = app.identity.create_customer_account(self.admin["id"], {
            "name": "Managed Owner", "email": "managed-owner@example.test", "phone": "9876543210", "password": "TempPass8!",
        })
        logged_in, _raw, _csrf = self.customers.login({"email": owner["email"], "password": "TempPass8!"}, "managed-owner")
        self.assertEqual(logged_in["id"], owner["id"])
        shop = app.shops.admin_create_application(self.admin["id"], owner["id"], {
            "shopName": "Managed Local Store", "ownerName": "Managed Owner", "category": "Clothing & Fashion",
            "description": "A local store managed initially by the private administrator.", "address": "10 Main Market Road",
            "city": "Neemuch", "state": "Madhya Pradesh", "pincode": "458441", "businessInformation": "Admin-assisted onboarding.",
        })
        self.assertEqual(shop["status"], "ACTIVE")
        product = app.shops.admin_create_product(self.admin["id"], shop["id"], {
            "name": "Managed Cotton Tee", "description": "Admin-listed local cotton tee with size stock.", "brand": "Local",
            "department": "unisex", "category": "Clothing & Fashion", "pricePaise": 79900, "originalPricePaise": 99900,
            "variants": [{"size":"S","inventory":3},{"size":"M","inventory":5},{"size":"L","inventory":2}],
            "colourName": "Black", "colourHex": "#000000", "imageUrls": ["https://images.example.test/tee.jpg"], "attributes": {},
        })
        self.assertEqual(product["status"], "PUBLISHED")
        self.assertEqual([(v["size"], v["inventory"]) for v in product["variants"]], [("S",3),("M",5),("L",2)])
        public = next(item for item in app.shops.list_published_products() if item["id"] == product["id"])
        self.assertEqual([v["size"] for v in public["variants"]], ["S","M","L"])
        updated = app.shops.admin_update_product(self.admin["id"], product["id"], {"name": "Managed Cotton T-Shirt"})
        self.assertEqual(updated["name"], "Managed Cotton T-Shirt")
        app.identity.set_customer_password(self.admin["id"], owner["id"], "NewTemp8!")
        actions = {row["action"] for row in app.identity.audit()}
        self.assertTrue({"customer_created","shop_admin_created","shop_product_admin_created","shop_product_admin_updated","customer_password_reset"}.issubset(actions))

    def test_private_admin_size_replacement_does_not_inherit_retired_stock(self):
        app = ADMIN_SERVER.AdminApplication(
            self.database, self.key, ROOT / "server/payment-data/catalog.json",
            ROOT / "server/payment-data/settings.json", self.root / "data-admin-size-replacement",
        )
        owner = app.identity.create_customer_account(self.admin["id"], {
            "name": "Admin Size Owner", "email": "admin-size-owner@example.test",
            "phone": "9876543212", "password": "TempPass8!",
        })
        shop = app.shops.admin_create_application(self.admin["id"], owner["id"], {
            "shopName": "Admin Size Replacement", "ownerName": "Admin Size Owner",
            "category": "Clothing & Fashion", "description": "A store testing immutable private admin variant identities.",
            "address": "12 Main Market Road", "city": "Neemuch",
            "state": "Madhya Pradesh", "pincode": "458441",
        })
        product = app.shops.admin_create_product(self.admin["id"], shop["id"], {
            "name": "Admin Replacement Tee", "description": "Published tee used to verify private admin size replacement safety.",
            "brand": "Local", "department": "unisex", "category": "Clothing & Fashion",
            "pricePaise": 79900, "originalPricePaise": 99900,
            "variants": [{"size": "M", "inventory": 2}], "colourName": "Black",
            "colourHex": "#000000", "imageUrls": ["https://images.example.test/admin-size-tee.jpg"], "attributes": {},
        })
        app.payments.refresh_shop_products()
        old_id = product["variants"][0]["id"]
        app.payments.set_shop_inventory(product["id"], 7, old_id)

        app.shops.admin_transition_product(self.admin["id"], product["id"], "APPROVED")
        replaced = app.shops.admin_update_product(
            self.admin["id"], product["id"],
            {"variants": [{"size": "XL", "inventory": 4}]},
        )
        active = replaced["variants"][0]
        replacement_catalog = next(
            item
            for item in app.shops.payment_catalog_products()
            if item["id"] == product["id"]
        )["variants"]
        retired = next(item for item in replacement_catalog if item["id"] == old_id)
        self.assertFalse(retired["active"])
        self.assertNotEqual(active["id"], old_id)

        app.shops.admin_transition_product(self.admin["id"], product["id"], "PUBLISHED")
        app.payments.refresh_shop_products()
        variants = app.payments.product_snapshot()[product["id"]]["variants"]
        live_active = next(item for item in variants if item.get("active") is not False)
        live_retired = next(item for item in variants if item["id"] == old_id)
        self.assertEqual((live_active["id"], live_active["size"]), (active["id"], "XL"))
        self.assertFalse(live_retired["active"])
        with app.payments.store.lock:
            self.assertEqual(
                app.payments._inventory(app.payments.store.state, live_active), 4
            )
            self.assertEqual(app.payments.store.state["inventory"].get(old_id), 7)

    def test_approved_size_change_syncs_new_and_retired_inventory(self):
        app = ADMIN_SERVER.AdminApplication(
            self.database, self.key, ROOT / "server/payment-data/catalog.json",
            ROOT / "server/payment-data/settings.json", self.root / "data-size-change",
        )
        owner = app.identity.create_customer_account(self.admin["id"], {
            "name": "Size Owner", "email": "size-owner@example.test",
            "phone": "9876543211", "password": "TempPass8!",
        })
        shop = app.shops.admin_create_application(self.admin["id"], owner["id"], {
            "shopName": "Size Change Store", "ownerName": "Size Owner",
            "category": "Clothing & Fashion", "description": "A store testing safe published size changes.",
            "address": "11 Main Market Road", "city": "Neemuch",
            "state": "Madhya Pradesh", "pincode": "458441",
        })
        product = app.shops.admin_create_product(self.admin["id"], shop["id"], {
            "name": "Size Change Tee", "description": "Published tee used to verify size replacement inventory safety.",
            "brand": "Local", "department": "unisex", "category": "Clothing & Fashion",
            "pricePaise": 79900, "originalPricePaise": 99900,
            "variants": [{"size": "M", "inventory": 2}], "colourName": "Black",
            "colourHex": "#000000", "imageUrls": ["https://images.example.test/size-tee.jpg"], "attributes": {},
        })
        app.payments.refresh_shop_products()
        old_id = product["variants"][0]["id"]
        app.payments.set_shop_inventory(product["id"], 0, old_id)
        live = app.payments.shop_inventory_snapshot([product["id"]])
        request = app.shops.create_product_edit_request(
            owner["id"], product["id"], {"variants": [{"size": "XL", "inventory": 4}]}, live,
        )
        app.transition_shop_product_request(self.admin["id"], request["id"], "UNDER_REVIEW")
        app.adjust_inventory(self.admin["id"], old_id, 5)
        with self.assertRaises(ADMIN_SERVER.SecurityError) as caught:
            app.transition_shop_product_request(
                self.admin["id"], request["id"], "APPROVED"
            )
        self.assertEqual(caught.exception.code, "published_variant_has_stock")
        pending = next(
            item
            for item in app.shops.admin_list_product_change_requests(self.admin["id"])
            if item["id"] == request["id"]
        )
        self.assertEqual(pending["status"], "UNDER_REVIEW")
        with app.payments.store.lock:
            self.assertEqual(app.payments.store.state["inventory"].get(old_id), 5)
        app.adjust_inventory(self.admin["id"], old_id, -5)

        with app.payments.store.lock:
            app.payments.store.state["orders"]["ORDER-SIZE-RELEASE-RACE"] = {
                "id": "ORDER-SIZE-RELEASE-RACE",
                "paymentMethod": "cod",
                "inventoryCommitted": True,
                "items": [{
                    "productId": product["id"],
                    "variantId": old_id,
                    "quantity": 1,
                }],
            }
            app.payments.store.save()

        approval_entered = threading.Event()
        release_attempted = threading.Event()
        release_results = []
        release_errors = []
        original_transition = app.shops.admin_transition_product_change_request

        def synchronized_transition(*args, **kwargs):
            approval_entered.set()
            self.assertTrue(release_attempted.wait(2))
            return original_transition(*args, **kwargs)

        def release_order():
            try:
                self.assertTrue(approval_entered.wait(2))
                release_attempted.set()
                with app.payments.store.lock:
                    order = app.payments.store.state["orders"]["ORDER-SIZE-RELEASE-RACE"]
                    release_results.append(
                        app.payments._release_inventory(
                            app.payments.store.state, order
                        )
                    )
                    app.payments.store.save()
            except BaseException as error:
                release_errors.append(error)

        release_thread = threading.Thread(target=release_order)
        with patch.object(
            app.shops,
            "admin_transition_product_change_request",
            side_effect=synchronized_transition,
        ):
            release_thread.start()
            approved = app.transition_shop_product_request(
                self.admin["id"], request["id"], "APPROVED"
            )
        release_thread.join(3)
        self.assertFalse(release_thread.is_alive())
        self.assertEqual(release_errors, [])
        self.assertEqual(release_results, [True])
        self.assertEqual(approved["status"], "APPROVED")
        app.payments.refresh_shop_products()
        variants = app.payments.product_snapshot()[product["id"]]["variants"]
        retired = next(item for item in variants if item["id"] == old_id)
        added = next(item for item in variants if item["size"] == "XL")
        self.assertFalse(retired["active"])
        self.assertTrue(added["active"])
        with app.payments.store.lock:
            self.assertEqual(app.payments.store.state["inventory"].get(old_id), 1)
            self.assertEqual(app.payments.store.state["inventory"].get(added["id"]), 4)

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
                "Customer requested cancellation before dispatch",
            )

            self.assertEqual(result["status"], "cancelled")
            self.assertEqual(result["cancellationReason"], "Customer requested cancellation before dispatch")
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
                "Item unavailable after order review",
            )

        self.assertEqual(result["status"], "cancelled")
        self.assertEqual(result["cancellationReason"], "Item unavailable after order review")

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
        self.assertIn("Mobile number (required; used for OTP login)", admin_ui)
        self.assertIn("Store owner email (optional)", admin_ui)
        self.assertIn("async function editStore(button)", admin_ui)
        self.assertIn('data-action="edit-store"', admin_ui)
        self.assertIn("Replace store cover (optional)", admin_ui)
        self.assertIn("Replace store logo (optional)", admin_ui)
        self.assertIn("/details`,{method:'PATCH'", admin_ui)
        self.assertIn('data-order-filter="status"', admin_ui)
        self.assertIn('data-order-filter="payment"', admin_ui)
        self.assertIn('data-order-filter="fulfillment"', admin_ui)
        self.assertIn('data-shop-product-filter', admin_ui)
        self.assertIn('All Shops', admin_ui)
        self.assertIn('No products for the selected shop.', admin_ui)
        self.assertIn("Promise.all([api('/api/admin/shop-products'),api('/api/admin/vendors')])", admin_ui)
        self.assertIn("payment_pending:'amber'", admin_ui)
        self.assertIn("delivered:'green'", admin_ui)
        self.assertIn("cancelled:'red'", admin_ui)
        self.assertIn("async function cancellationReasonFor()", admin_ui)
        self.assertIn("Customer requested cancellation", admin_ui)
        self.assertIn("Other", admin_ui)
        self.assertIn("Cancellation reason", admin_ui)
        self.assertIn("orderItemMarkup", admin_ui)
        self.assertNotIn("prompt(", admin_ui)
        self.assertNotIn("alert(", admin_ui)
        self.assertNotIn("confirm(", admin_ui)
        admin_index = (ROOT / "server/admin/index.html").read_text(encoding="utf-8")
        admin_css = (ROOT / "server/admin/admin.css").read_text(encoding="utf-8")
        self.assertIn('id="admin-dialog"', admin_index)
        self.assertIn('role="status"', admin_index)
        self.assertNotIn("th:nth-child(n+4)", admin_css)
        self.assertIn("table{min-width:680px}", admin_css)
        self.assertIn(".order-filters{", admin_css)
        self.assertIn(".status-badge{", admin_css)
        self.assertIn(".tone-green{", admin_css)
        self.assertIn(".tone-red{", admin_css)


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
        self.assertEqual(status, 200); self.assertIn("Vibe4You Local Administration", html)
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

        for target in ("APPROVED", "PUBLISHED"):
            status, body, _headers = self.request(
                f"/api/admin/shop-products/{product['id']}", {"status": target, "reason": None},
                headers={"X-CSRF-Token": csrf}, method="PATCH",
            )
            self.assertEqual((status, body["product"]["status"]), (200, target))

        change = shops.create_product_edit_request(
            user["id"], product["id"], {"name": "Transition Tee Updated"}
        )
        status, body, _headers = self.request("/api/admin/shop-product-requests")
        self.assertEqual(status, 200)
        self.assertEqual([item["id"] for item in body["requests"]], [change["id"]])
        self.assertEqual(body["requests"][0]["shopName"], "Transition Shop")
        for target in ("UNDER_REVIEW", "APPROVED"):
            status, body, _headers = self.request(
                f"/api/admin/shop-product-requests/{change['id']}",
                {"status": target, "reason": None},
                headers={"X-CSRF-Token": csrf}, method="PATCH",
            )
            self.assertEqual((status, body["request"]["status"]), (200, target))
        updated = next(item for item in shops.admin_list_products(body["request"]["reviewedBy"]) if item["id"] == product["id"] )
        self.assertEqual(updated["name"], "Transition Tee Updated")

    def test_admin_can_edit_store_details_without_changing_identity_or_status(self):
        import base64
        customers = SECURITY.SecurityStore(self.database, self.key)
        user, _raw, _csrf = customers.register({
            "name": "Editable Seller", "email": "editable-seller@example.test",
            "password": "long seller password 123", "phone": "9999999977",
        })
        self.request("/api/admin/login", {"username": "local-owner", "password": "long administrator password 123"}, method="POST")
        status, body, _headers = self.request("/api/admin/totp", {"code": pyotp.TOTP(self.secret).now()}, method="POST")
        self.assertEqual(status, 200); csrf = body["csrfToken"]; admin_id = body["admin"]["id"]
        shops = ADMIN_SERVER.ShopWorkflow(self.database)
        application = shops.admin_create_application(admin_id, user["id"], {
            "shopName": "Editable Shop", "ownerName": "Editable Seller", "category": "Clothing & Fashion",
            "description": "A local shop that can be edited safely by the administrator.",
            "address": "1 Main Market", "city": "Neemuch", "state": "Madhya Pradesh", "pincode": "458441",
        })
        png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")
        status, uploaded, _headers = self.request("/api/admin/product-images", {
            "fileName": "cover.png", "contentType": "image/png", "dataBase64": base64.b64encode(png).decode("ascii"),
        }, headers={"X-CSRF-Token": csrf}, method="POST")
        self.assertEqual(status, 201); cover = uploaded["image"]["url"]
        status, body, _headers = self.request(f"/api/admin/vendors/{application['id']}/details", {
            "shopName": "Edited Local Shop", "description": "Updated local shop description for the public storefront.",
            "address": "22 Veer Park Road", "businessInformation": "Updated by private admin.", "bannerImage": cover,
        }, headers={"X-CSRF-Token": csrf}, method="PATCH")
        self.assertEqual(status, 200); edited = body["application"]
        self.assertEqual((edited["shopName"], edited["status"]), ("Edited Local Shop", "ACTIVE"))
        self.assertEqual((edited["registeredEmail"], edited["registeredMobile"]), (user["email"], user["phone"]))
        self.assertEqual((edited["submittedByUserId"], edited["bannerImage"]), (user["id"], cover))
        status, bad, _headers = self.request(f"/api/admin/vendors/{application['id']}/details", {"registeredMobile": "+919999999999"}, headers={"X-CSRF-Token": csrf}, method="PATCH")
        self.assertEqual((status, bad["code"]), (400, "invalid_vendor_application"))
        status, bad, _headers = self.request(f"/api/admin/vendors/{application['id']}/details", {"bannerImage": "/media/product-images/" + "a" * 32 + ".png"}, headers={"X-CSRF-Token": csrf}, method="PATCH")
        self.assertEqual((status, bad["code"]), (400, "invalid_store_branding"))
        status, audit, _headers = self.request("/api/admin/audit")
        self.assertEqual(status, 200); self.assertTrue(any(row["action"] == "shop_admin_updated" and row["target_id"] == application["id"] for row in audit["audit"]))

    def test_admin_bulk_product_endpoint_publishes_valid_rows_atomically(self):
        customers = SECURITY.SecurityStore(self.database, self.key)
        user, _raw, _csrf = customers.register({
            "name": "Bulk Seller", "email": "bulk-seller@example.test",
            "password": "long seller password 123", "phone": "9999999988",
        })
        shops = ADMIN_SERVER.ShopWorkflow(self.database)
        self.request("/api/admin/login", {"username": "local-owner", "password": "long administrator password 123"}, method="POST")
        status, body, _headers = self.request("/api/admin/totp", {"code": pyotp.TOTP(self.secret).now()}, method="POST")
        self.assertEqual(status, 200); csrf = body["csrfToken"]; admin_id = body["admin"]["id"]
        application = shops.admin_create_application(admin_id, user["id"], {
            "shopName": "Bulk HTTP Shop", "ownerName": "Bulk Seller",
            "category": "Clothing & Fashion", "description": "Bulk import endpoint shop.",
            "address": "10 Main Market", "city": "Neemuch", "state": "Madhya Pradesh",
            "pincode": "458441",
        })
        product = {
            "name": "Bulk HTTP Tee", "description": "Imported through the admin bulk endpoint.",
            "brand": "Local", "department": "men", "category": "Clothing & Fashion",
            "pricePaise": 79900, "originalPricePaise": 99900,
            "variants": [{"size": "M", "inventory": 5}], "colourName": "Black",
            "colourHex": "#000000", "imageUrls": ["https://example.test/bulk-http.jpg"], "attributes": {},
        }
        status, body, _headers = self.request(
            "/api/admin/shop-products/bulk", {"applicationId": application["id"], "products": [product]},
            headers={"X-CSRF-Token": csrf}, method="POST",
        )
        self.assertEqual((status, body["created"], body["products"][0]["status"]), (201, 1, "PUBLISHED"))
        self.assertEqual(shops.list_published_products()[0]["name"], "Bulk HTTP Tee")

    def test_admin_product_image_upload_is_content_addressed(self):
        import base64
        self.request("/api/admin/login", {"username": "local-owner", "password": "long administrator password 123"}, method="POST")
        status, body, _headers = self.request("/api/admin/totp", {"code": pyotp.TOTP(self.secret).now()}, method="POST")
        self.assertEqual(status, 200)
        png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")
        status, body, _headers = self.request(
            "/api/admin/product-images",
            {"fileName": "admin-upload.png", "contentType": "image/png", "dataBase64": base64.b64encode(png).decode("ascii")},
            headers={"X-CSRF-Token": body["csrfToken"]}, method="POST",
        )
        self.assertEqual(status, 201)
        self.assertRegex(body["image"]["url"], r"^/media/product-images/[0-9a-f]{32}\.png$")
        stored = self.database.parent / "product-images" / Path(body["image"]["url"]).name
        self.assertEqual(stored.read_bytes(), png)

    def test_non_loopback_bind_refused(self):
        with self.assertRaises(RuntimeError):
            ADMIN_SERVER.create_admin_server("0.0.0.0", 0, self.database, self.key, ROOT / "server/payment-data/catalog.json", ROOT / "server/payment-data/settings.json", self.root / "data2", ROOT / "server/admin", self.root / "backups")


if __name__ == "__main__":
    unittest.main()
