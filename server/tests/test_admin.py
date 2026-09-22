from __future__ import annotations

import importlib.util
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from datetime import datetime
from http.cookiejar import CookieJar
from types import SimpleNamespace
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
        inventory_row = next(item for item in app.inventory() if item["variantId"] == "sd-prod-001-var-2")
        self.assertEqual(inventory_row["imageUrl"], app.payments.products["sd-prod-001"]["thumbnail"])
        self.assertTrue(str(inventory_row["imageUrl"]).startswith("https://"))
        inventory = app.adjust_inventory(self.admin["id"], "sd-prod-001-var-2", 3)
        self.assertEqual(inventory["after"], inventory["before"] + 3)
        reviewed = self.store.review_vendor(self.admin["id"], vendor["id"], "approved")
        self.assertEqual(reviewed["status"], "approved")
        disabled = self.store.set_customer_active(self.admin["id"], user["id"], False)
        self.assertFalse(disabled["active"])
        actions = {row["action"] for row in self.store.audit()}
        self.assertTrue({"order_status", "inventory_adjustment", "vendor_approved", "customer_disabled"}.issubset(actions))

    def test_cod_payment_collection_is_separate_audited_and_never_spoofs_razorpay(self):
        app = ADMIN_SERVER.AdminApplication(
            self.database, self.key, ROOT / "server/payment-data/catalog.json",
            ROOT / "server/payment-data/settings.json", self.root / "data-cod-payment",
        )
        with app.payments.store.lock:
            app.payments.store.state["orders"]["COD-PENDING"] = {
                "id": "COD-PENDING", "paymentMethod": "cod", "paymentStatus": "pending",
                "status": "placed", "fulfillmentRequired": True, "createdAt": "2026-09-04T10:00:00+00:00",
            }
            app.payments.store.state["orders"]["COD-CONFIRM-FIRST"] = {
                "id": "COD-CONFIRM-FIRST", "paymentMethod": "cod", "paymentStatus": "pending",
                "status": "placed", "fulfillmentRequired": True, "createdAt": "2026-09-04T10:01:00+00:00",
            }
            app.payments.store.state["orders"]["RAZORPAY-PENDING"] = {
                "id": "RAZORPAY-PENDING", "paymentMethod": "upi", "paymentStatus": "pending",
                "status": "payment_pending", "fulfillmentRequired": True, "razorpayOrderId": "order_secure",
                "createdAt": "2026-09-04T10:02:00+00:00",
            }
            app.payments.store.save()
        paid = app.mark_cod_paid(self.admin["id"], "COD-PENDING", "cash")
        self.assertEqual((paid["paymentMethod"], paid["paymentStatus"], paid["status"]), ("cod", "paid", "placed"))
        self.assertEqual(paid["paymentCollectionMethod"], "cash")
        self.assertTrue(paid["paymentCollectedAt"].endswith("+00:00"))
        public = app.payments._public_order(paid)
        self.assertEqual(public["paymentCollectionMethod"], "cash")
        self.assertEqual(public["paymentCollectedAt"], paid["paymentCollectedAt"])
        confirmed = app.update_order_status(self.admin["id"], "COD-CONFIRM-FIRST", "confirmed")
        self.assertEqual((confirmed["status"], confirmed["paymentStatus"]), ("confirmed", "pending"))
        self.assert_error("manual_payment_forbidden", lambda: app.mark_cod_paid(self.admin["id"], "RAZORPAY-PENDING", "cash"))
        self.assert_error("payment_not_pending", lambda: app.mark_cod_paid(self.admin["id"], "COD-PENDING", "upi_at_delivery"))
        audit = next(row for row in self.store.audit() if row["action"] == "cod_payment_marked_paid")
        metadata = json.loads(audit["metadata_json"])
        self.assertEqual(metadata["collectionMethod"], "cash")
        self.assertEqual(metadata["paymentCollectedAt"], paid["paymentCollectedAt"])

    def test_try_at_home_delivery_timer_and_late_fee_collection_are_admin_controlled(self):
        app = ADMIN_SERVER.AdminApplication(
            self.database, self.key, ROOT / "server/payment-data/catalog.json",
            ROOT / "server/payment-data/settings.json", self.root / "data-try-home",
        )
        with app.payments.store.lock:
            app.payments.store.state["orders"]["TRY-HOME-ADMIN"] = {
                "id": "TRY-HOME-ADMIN", "userId": "customer-try-home", "paymentMethod": "cod",
                "paymentStatus": "paid", "status": "out_for_delivery", "fulfillmentRequired": True,
                "createdAt": "2026-09-13T09:00:00+00:00", "updatedAt": "2026-09-13T09:00:00+00:00",
                "statusHistory": [], "items": [{"productId": "sd-prod-001", "variantId": "sd-prod-001-var-1",
                "quantity": 1, "tryAtHome": {"status": "reserved", "tryMinutes": 15}}],
            }
            app.payments.store.save()
        delivered = app.update_order_status(self.admin["id"], "TRY-HOME-ADMIN", "delivered")
        trial = delivered["items"][0]["tryAtHome"]
        self.assertEqual(trial["status"], "active")
        self.assertTrue(trial["startedAt"].endswith("+00:00"))
        start = datetime.fromisoformat(trial["startedAt"])
        deadline = datetime.fromisoformat(trial["deadlineAt"])
        self.assertEqual(int((deadline - start).total_seconds()), 15 * 60)
        with app.payments.store.lock:
            order = app.payments.store.state["orders"]["TRY-HOME-ADMIN"]
            order["tryAtHomeLateFeeDue"] = 50
            order["tryAtHomeLateFeePaid"] = False
            app.payments.store.save()
        paid = app.mark_try_at_home_late_fee_paid(self.admin["id"], "TRY-HOME-ADMIN", "upi_at_delivery")
        self.assertTrue(paid["tryAtHomeLateFeePaid"])
        self.assertEqual(paid["tryAtHomeLateFeeCollectionMethod"], "upi_at_delivery")
        self.assert_error("late_fee_already_paid", lambda: app.mark_try_at_home_late_fee_paid(self.admin["id"], "TRY-HOME-ADMIN", "cash"))
        audit = next(row for row in self.store.audit() if row["action"] == "try_at_home_late_fee_paid")
        metadata = json.loads(audit["metadata_json"])
        self.assertEqual(metadata["amount"], 50)
        self.assertEqual(metadata["collectionMethod"], "upi_at_delivery")

    def test_cancellation_and_exchange_fees_are_collected_and_inventory_moves_exactly_once(self):
        app = ADMIN_SERVER.AdminApplication(
            self.database, self.key, ROOT / "server/payment-data/catalog.json",
            ROOT / "server/payment-data/settings.json", self.root / "data-service-fees",
        )
        product = app.payments.product_snapshot()["sd-prod-001"]
        source, target = product["variants"][0], product["variants"][1]
        exchange_id = "exch_admin_test"
        with app.payments.store.lock:
            state = app.payments.store.state
            state["inventory"][source["id"]] = 9
            state["inventory"][target["id"]] = 4
            state["orders"]["EXCHANGE-ADMIN"] = {
                "id": "EXCHANGE-ADMIN", "userId": "customer-a", "paymentMethod": "cod",
                "paymentStatus": "paid", "status": "delivered", "fulfillmentRequired": True,
                "createdAt": "2026-09-13T09:00:00+00:00", "updatedAt": "2026-09-13T10:00:00+00:00",
                "statusHistory": [], "items": [{"productId": product["id"], "variantId": source["id"], "quantity": 1}],
                "exchangeRequests": [{"id": exchange_id, "productId": product["id"], "itemIndex": 0,
                    "sourceVariantId": source["id"], "sourceSize": source["size"], "targetVariantId": target["id"],
                    "targetSize": target["size"], "quantity": 1, "status": "requested", "feeDue": 50,
                    "feePaid": False, "inventoryAdjusted": False}],
            }
            state["orders"]["CANCEL-ADMIN"] = {
                "id": "CANCEL-ADMIN", "paymentMethod": "cod", "paymentStatus": "pending",
                "status": "out_for_delivery", "fulfillmentRequired": True, "inventoryCommitted": False,
                "createdAt": "2026-09-13T09:00:00+00:00", "updatedAt": "2026-09-13T10:00:00+00:00",
                "statusHistory": [], "items": [],
                "cancellationRequest": {"status": "requested", "feeDue": 50, "feePaid": False},
            }
            state["orders"]["EXCHANGE-REJECT-ADMIN"] = {
                "id": "EXCHANGE-REJECT-ADMIN", "status": "delivered", "items": [],
                "exchangeRequests": [{"id": "exch_reject", "productId": "retired-product",
                    "status": "requested", "quantity": "invalid", "sourceSize": "S", "targetSize": "M"}],
            }
            app.payments.store.save()

        self.assert_error("exchange_fee_not_ready", lambda: app.mark_exchange_fee_paid(self.admin["id"], "EXCHANGE-ADMIN", exchange_id, "cash"))
        approved = app.update_exchange_status(self.admin["id"], "EXCHANGE-ADMIN", exchange_id, "approved")
        self.assertEqual(approved["exchangeRequests"][0]["status"], "approved")
        self.assertEqual(app.payments.store.state["inventory"][target["id"]], 3)
        paid = app.mark_exchange_fee_paid(self.admin["id"], "EXCHANGE-ADMIN", exchange_id, "cash")
        self.assertTrue(paid["exchangeRequests"][0]["feePaid"])
        completed = app.update_exchange_status(self.admin["id"], "EXCHANGE-ADMIN", exchange_id, "completed")
        self.assertEqual(completed["exchangeRequests"][0]["status"], "completed")
        self.assertEqual(app.payments.store.state["inventory"][source["id"]], 10)
        self.assertEqual(app.payments.store.state["inventory"][target["id"]], 3)
        self.assert_error("invalid_exchange_transition", lambda: app.update_exchange_status(self.admin["id"], "EXCHANGE-ADMIN", exchange_id, "completed"))
        self.assertEqual((app.payments.store.state["inventory"][source["id"]], app.payments.store.state["inventory"][target["id"]]), (10, 3))
        rejected = app.update_exchange_status(self.admin["id"], "EXCHANGE-REJECT-ADMIN", "exch_reject", "rejected")
        self.assertEqual(rejected["exchangeRequests"][0]["status"], "rejected")

        self.assert_error("cancellation_fee_required", lambda: app.update_order_status(self.admin["id"], "CANCEL-ADMIN", "cancelled", "Customer requested cancellation"))
        fee_paid = app.mark_cancellation_fee_paid(self.admin["id"], "CANCEL-ADMIN", "upi_at_delivery")
        self.assertTrue(fee_paid["cancellationRequest"]["feePaid"])
        cancelled = app.update_order_status(self.admin["id"], "CANCEL-ADMIN", "cancelled", "Customer requested cancellation")
        self.assertEqual(cancelled["cancellationRequest"]["status"], "completed")
        actions = {row["action"] for row in self.store.audit()}
        self.assertTrue({"exchange_approved", "exchange_fee_paid", "exchange_completed", "cancellation_fee_paid"}.issubset(actions))

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
            "bannerImage": "/media/product-images/" + "a" * 32 + ".webp",
            "logoImage": "/media/product-images/" + "b" * 32 + ".png",
        })
        self.assertEqual(shop["status"], "ACTIVE")
        self.assertEqual(shop["bannerImage"], "/media/product-images/" + "a" * 32 + ".webp")
        self.assertEqual(shop["logoImage"], "/media/product-images/" + "b" * 32 + ".png")
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

    def test_bulk_product_request_approval_advances_submitted_in_one_call(self):
        app = ADMIN_SERVER.AdminApplication(
            self.database, self.key, ROOT / "server/payment-data/catalog.json",
            ROOT / "server/payment-data/settings.json", self.root / "data-bulk-request-approval",
        )
        submitted = {"id": "shopchg-one", "status": "SUBMITTED", "action": "EDIT", "productName": "Watch One", "productId": "product-one", "changeSummary": [{"field": "Images"}]}
        under_review = {**submitted, "status": "UNDER_REVIEW"}
        approved = {**submitted, "status": "APPROVED"}
        with patch.object(app.shops, "admin_list_product_change_requests", return_value=[submitted]), patch.object(
            app.shops, "admin_transition_product_change_request", side_effect=[under_review, approved]
        ) as transition, patch.object(app.payments, "refresh_shop_products") as refresh:
            result = app.bulk_transition_shop_product_requests(
                self.admin["id"], [submitted["id"], "shopchg-missing"], "APPROVED"
            )
        self.assertEqual(result["requested"], 2)
        self.assertEqual(result["updated"], [approved])
        self.assertEqual(result["failures"][0]["code"], "product_change_not_found")
        self.assertEqual(transition.call_args_list[0].args[2], "UNDER_REVIEW")
        self.assertEqual(transition.call_args_list[1].args[2], "APPROVED")
        refresh.assert_called_once_with()

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

    def test_inventory_snapshot_lists_new_shops_before_they_have_products(self):
        app = ADMIN_SERVER.AdminApplication(
            self.database, self.key, ROOT / "server/payment-data/catalog.json",
            ROOT / "server/payment-data/settings.json", self.root / "data-inventory-shops",
        )
        owner = app.identity.create_customer_account(self.admin["id"], {
            "name": "Inventory Shop Owner", "email": "inventory-shop@example.test",
            "phone": "9876543299", "password": "TempPass8!",
        })
        shop = app.shops.admin_create_application(self.admin["id"], owner["id"], {
            "shopName": "New Empty Inventory Shop", "ownerName": "Inventory Shop Owner",
            "category": "Clothing & Fashion", "description": "A newly created shop with no submitted product.",
            "address": "12 Main Market Road", "city": "Neemuch", "state": "Madhya Pradesh", "pincode": "458441",
        })
        snapshot = app.inventory_snapshot(self.admin["id"])
        listed = next(item for item in snapshot["shops"] if item["id"] == shop["id"])
        self.assertEqual((listed["name"], listed["status"]), ("New Empty Inventory Shop", "ACTIVE"))
        self.assertFalse(any(row.get("storeId") == shop["id"] for row in snapshot["inventory"]))

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
        self.assertIn('data-admin-filter', admin_ui)
        self.assertIn("Shop application filters", admin_ui)
        self.assertIn("Product change request filters", admin_ui)
        self.assertIn("Inventory filters", admin_ui)
        self.assertIn("New verified-purchase reviews stay private until approved", admin_ui)
        self.assertIn("/api/admin/store-reviews", admin_ui)
        self.assertIn('width="48" height="48"', admin_ui)
        self.assertNotIn('referrerpolicy="no-referrer" style=', admin_ui)
        self.assertNotIn('fallback.style.cssText', admin_ui)
        self.assertIn("item.productName || item.name || 'Product'", admin_ui)
        self.assertIn('class="inventory-product-heading">${inventoryThumbnail(item)}<div><h3>${escapeText(item.name)}</h3>', admin_ui)
        self.assertIn('class="inventory-product-cell">${inventoryThumbnail(item)}<span>', admin_ui)
        self.assertNotIn("width:44px;height:44px;flex:0 0 44px", admin_ui)
        self.assertIn("Customer filters", admin_ui)
        self.assertIn("Payment alert filters", admin_ui)
        self.assertIn("Audit filters", admin_ui)
        self.assertIn("Changed field", admin_ui)
        self.assertNotIn("JSON.stringify(item.proposedProduct", admin_ui)
        self.assertIn("bulkTransition", admin_ui)
        self.assertIn("/api/admin/shop-product-requests/bulk", admin_ui)
        self.assertIn("cancellationRequest?.status==='requested'", admin_ui)
        self.assertIn("mark-cancellation-fee-paid", admin_ui)
        self.assertIn("mark-exchange-fee-paid", admin_ui)
        self.assertIn("matchesAdminSearch", admin_ui)
        self.assertIn('All Shops', admin_ui)
        self.assertIn('No products match the current search and filters.', admin_ui)
        self.assertIn("Promise.all([api('/api/admin/shop-products'),api('/api/admin/vendors')])", admin_ui)
        self.assertIn("Store cover image (optional)", admin_ui)
        self.assertIn("Store logo (optional)", admin_ui)
        self.assertIn("payload.bannerImage", admin_ui)
        self.assertIn("payload.logoImage", admin_ui)
        self.assertIn("Choose product images from this PC", admin_ui)
        self.assertIn("HTTPS image URLs (optional fallback)", admin_ui)
        self.assertIn("imageFile", admin_ui)
        self.assertIn("Select the local product images referenced by the CSV", admin_ui)
        self.assertIn("previewImages:true", admin_ui)
        self.assertIn("new DataTransfer()", admin_ui)
        self.assertIn("csvText,images", admin_ui)
        self.assertIn("progressOffset=0,progressTotal=null", admin_ui)
        self.assertIn("uploadAdminProductImages([file],uploaded,requiredFiles.size)", admin_ui)
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
        self.assertIn('data-tab="store-reviews"', admin_index)
        map_ui = (ROOT / "server/admin/delivery-zone-map.js").read_text(encoding="utf-8")
        admin_css = (ROOT / "server/admin/admin.css").read_text(encoding="utf-8")
        self.assertIn('/admin.js?v=reviews-20260922-1', admin_index)
        self.assertIn('/admin.css?v=thumbnail-20260916-4', admin_index)
        self.assertIn('id="admin-dialog"', admin_index)
        self.assertIn('role="status"', admin_index)
        self.assertNotIn("th:nth-child(n+4)", admin_css)
        self.assertIn("table{min-width:680px}", admin_css)
        self.assertIn(".order-filters{", admin_css)
        self.assertIn(".status-badge{", admin_css)
        self.assertIn(".tone-green{", admin_css)
        self.assertIn(".tone-red{", admin_css)
        self.assertIn(".inventory-product-cell,.inventory-product-heading{display:flex;align-items:center;gap:8px}", admin_css)
        self.assertIn("width:48px!important;height:48px!important", admin_css)
        self.assertIn("img.inventory-thumbnail{display:block;object-fit:contain!important", admin_css)
        self.assertIn("STORE_CATEGORIES", admin_ui)
        self.assertIn("{name:'category',label:'Category',type:'select',required:true,value:STORE_CATEGORIES[0]", admin_ui)
        self.assertIn("field-required", admin_ui)
        self.assertIn(".dialog-field-wide{", admin_css)
        self.assertIn("#admin-dialog-form>.actions{", admin_css)


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

    def test_cloudflare_access_admin_origin_is_allowed_but_other_origins_are_rejected(self):
        status, body, headers = self.request(
            "/api/admin/login",
            {"username": "local-owner", "password": "long administrator password 123"},
            headers={"Origin": "https://admin.vibe4you.in"},
            method="POST",
        )
        self.assertEqual(status, 200)
        self.assertTrue(body["requiresTotp"])
        self.assertIn("styledash_admin_challenge=", headers.get("Set-Cookie", ""))

        status, body, _headers = self.request(
            "/api/admin/login",
            {"username": "local-owner", "password": "long administrator password 123"},
            headers={"Origin": "https://evil.example"},
            method="POST",
        )
        self.assertEqual((status, body["code"]), (403, "admin_request_rejected"))

    def test_versioned_admin_assets_force_fresh_thumbnail_ui(self):
        status, index, headers = self.request("/")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("Cache-Control"), "no-store")
        self.assertIn("/admin.js?v=reviews-20260922-1", index)
        status, script, headers = self.request("/admin.js?v=reviews-20260922-1")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("Cache-Control"), "no-store")
        self.assertIn('width="48" height="48"', script)
        self.assertNotIn('referrerpolicy="no-referrer" style=', script)
        self.assertIn("item.productName || item.name || 'Product'", script)
        self.assertIn('class="inventory-product-heading">${inventoryThumbnail(item)}<div><h3>${escapeText(item.name)}</h3>', script)
        status, css, headers = self.request("/admin.css?v=thumbnail-20260916-4")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("Cache-Control"), "no-store")
        self.assertIn("width:48px!important;height:48px!important", css)
        self.assertIn("img.inventory-thumbnail{display:block;object-fit:contain!important", css)

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

    def test_store_review_queue_is_private_csrf_protected_and_audited(self):
        customers = SECURITY.SecurityStore(self.database, self.key)
        reviewer, _raw, _csrf = customers.register({
            "name": "Reviewing Customer", "email": "reviewing@example.test",
            "password": "long customer password 123", "phone": "9999999901",
        })
        owner, _raw, _csrf = customers.register({
            "name": "Store Owner", "email": "store-owner@example.test",
            "password": "long customer password 123", "phone": "9999999902",
        })
        shops = ADMIN_SERVER.ShopWorkflow(self.database)
        store = shops.create_draft(owner["id"], {
            "shopName": "Moderation Store", "ownerName": "Store Owner",
            "category": "Clothing & Fashion", "description": "A complete local store for review moderation tests.",
            "address": "12 Test Market", "city": "Neemuch", "state": "Madhya Pradesh", "pincode": "458441",
        })
        app = self.server.RequestHandlerClass.application
        review_order_store = SimpleNamespace(
            lock=threading.RLock(), state={"orders": {"review-http-order": {
                "id": "review-http-order", "userId": reviewer["id"], "status": "delivered",
                "fulfillmentRequired": True, "createdAt": "2026-09-22T10:00:00+00:00",
                "updatedAt": "2026-09-22T10:01:00+00:00",
                "items": [{"productId": "review-product", "storeId": store["id"]}],
            }}},
        )
        created = app.reviews.create_store(review_order_store, reviewer["id"], {
            "storeId": store["id"], "rating": 5, "comment": "Helpful service after a delivered local order.",
        })
        self.assertEqual(created["status"], "pending")
        status, body, _ = self.request("/api/admin/store-reviews")
        self.assertEqual((status, body["code"]), (401, "admin_authentication_required"))
        self.request("/api/admin/login", {"username": "local-owner", "password": "long administrator password 123"}, method="POST")
        status, auth, _ = self.request("/api/admin/totp", {"code": pyotp.TOTP(self.secret).now()}, method="POST")
        self.assertEqual(status, 200)
        csrf = auth["csrfToken"]
        status, queue, _ = self.request("/api/admin/store-reviews")
        self.assertEqual((status, len(queue["reviews"]), queue["reviews"][0]["status"]), (200, 1, "pending"))
        self.assertEqual(queue["reviews"][0]["customerEmail"], "reviewing@example.test")
        status, missing, _ = self.request(
            f"/api/admin/store-reviews/{created['id']}", {"status": "approved"}, method="PATCH",
        )
        self.assertEqual((status, missing["code"]), (403, "admin_csrf_failed"))
        status, approved, _ = self.request(
            f"/api/admin/store-reviews/{created['id']}", {"status": "approved"},
            headers={"X-CSRF-Token": csrf}, method="PATCH",
        )
        self.assertEqual((status, approved["review"]["status"]), (200, "approved"))
        self.assertEqual(app.reviews.list_store(store["id"])["reviewCount"], 1)
        status, audit, _ = self.request("/api/admin/audit")
        self.assertEqual(status, 200)
        self.assertTrue(any(row["action"] == "store_review_approved" for row in audit["audit"]))

    def test_delivery_zone_admin_is_private_csrf_protected_and_fail_closed(self):
        status, body, _ = self.request("/api/admin/delivery-zone")
        self.assertEqual((status, body["code"]), (401, "admin_authentication_required"))
        self.request("/api/admin/login", {"username":"local-owner","password":'long administrator password 123'}, method="POST")
        status, auth, _ = self.request("/api/admin/totp", {"code":pyotp.TOTP(self.secret).now()}, method="POST")
        self.assertEqual(status, 200); csrf = auth["csrfToken"]
        status, body, _ = self.request("/api/admin/delivery-zone")
        self.assertEqual(status, 200)
        self.assertEqual(body["configuration"]["enforcementMode"], "pincode")
        self.assertEqual(body["activeZoneCount"], 0)
        zone = {"type":"FeatureCollection","enforcementMode":"pincode","features":[{"type":"Feature","properties":{"id":"neemuch-core","name":"Neemuch Core","active":True},"geometry":{"type":"Polygon","coordinates":[[[74.84,24.45],[74.89,24.45],[74.89,24.50],[74.84,24.50],[74.84,24.45]]]}}]}
        status, body, _ = self.request("/api/admin/delivery-zone", zone, method="PATCH")
        self.assertEqual((status, body["code"]), (403, "admin_csrf_failed"))
        status, body, _ = self.request("/api/admin/delivery-zone", zone, headers={"X-CSRF-Token":csrf}, method="PATCH")
        self.assertEqual(status, 200)
        self.assertEqual(body["configuration"]["enforcementMode"], "pincode")
        self.assertEqual(body["activeZoneCount"], 1)
        invalid = {"type":"FeatureCollection","enforcementMode":"polygon","features":[]}
        status, body, _ = self.request("/api/admin/delivery-zone", invalid, headers={"X-CSRF-Token":csrf}, method="PATCH")
        self.assertEqual((status, body["code"]), (400, "invalid_delivery_zone"))
        status, body, _ = self.request("/api/admin/delivery-zone")
        self.assertEqual(body["configuration"]["enforcementMode"], "pincode")
        zone["enforcementMode"] = "polygon"
        status, body, _ = self.request("/api/admin/delivery-zone", zone, headers={"X-CSRF-Token":csrf}, method="PATCH")
        self.assertEqual(status, 200)
        self.assertEqual(body["configuration"]["enforcementMode"], "polygon")
        status, audit, _ = self.request("/api/admin/audit")
        self.assertEqual(status, 200)
        self.assertTrue(any(item.get("action") == "delivery_zone_updated" for item in audit["audit"]))

    def test_admin_map_headers_allow_osm_referer_without_leaking_full_path(self):
        status, _body, headers = self.request("/leaflet.js")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Referrer-Policy"], "strict-origin-when-cross-origin")
        self.assertIn("img-src 'self' data: https:", headers["Content-Security-Policy"])
        self.assertEqual(headers["Permissions-Policy"], "camera=(), microphone=(), geolocation=()")

    def test_delivery_zone_admin_ui_uses_explicit_safe_actions_and_coordinate_conversion(self):
        admin_ui = (ROOT / "server/admin/admin.js").read_text(encoding="utf-8")
        admin_index = (ROOT / "server/admin/index.html").read_text(encoding="utf-8")
        map_ui = (ROOT / "server/admin/delivery-zone-map.js").read_text(encoding="utf-8")
        self.assertIn('data-tab="delivery-zone"', admin_index)
        self.assertIn("Delivery Zones", admin_index)
        self.assertIn("Save Boundary Draft", admin_ui)
        self.assertIn("Activate Polygon Delivery", admin_ui)
        self.assertIn("Use Pincode Only", admin_ui)
        self.assertIn("Type ACTIVATE", admin_ui)
        self.assertIn("Type PINCODE", admin_ui)
        self.assertIn("function parseDeliveryZoneBoundary", admin_ui)
        self.assertIn("return [longitude,latitude]", admin_ui)
        self.assertIn("return [...points,[...points[0]]]", admin_ui)
        self.assertIn('/leaflet.css', admin_index)
        self.assertIn('/leaflet.js', admin_index)
        self.assertIn('/delivery-zone-map.js', admin_index)
        self.assertIn("tile.openstreetmap.org", map_ui)
        self.assertIn("draggable: true", map_ui)
        self.assertIn("delivery-zone-map-undo", map_ui)
        self.assertIn("delivery-zone-map-clear", map_ui)
        self.assertNotIn("prompt(", admin_ui)
        self.assertNotIn("alert(", admin_ui)
        self.assertNotIn("confirm(", admin_ui)

    def test_cod_mark_paid_http_is_private_csrf_protected_and_cod_only(self):
        app = self.server.RequestHandlerClass.application
        with app.payments.store.lock:
            app.payments.store.state["orders"]["HTTP-COD"] = {
                "id": "HTTP-COD", "paymentMethod": "cod", "paymentStatus": "pending",
                "status": "placed", "fulfillmentRequired": True, "createdAt": "2026-09-04T10:00:00+00:00",
            }
            app.payments.store.state["orders"]["HTTP-RAZORPAY"] = {
                "id": "HTTP-RAZORPAY", "paymentMethod": "card", "paymentStatus": "pending",
                "status": "payment_pending", "fulfillmentRequired": True, "razorpayOrderId": "order_http_secure",
                "createdAt": "2026-09-04T10:01:00+00:00",
            }
            app.payments.store.save()
        status, body, _ = self.request('/api/admin/orders/HTTP-COD/payment', {'collectionMethod':'cash'}, method='PATCH')
        self.assertEqual((status, body['code']), (401, 'admin_authentication_required'))
        self.request('/api/admin/login', {'username':'local-owner','password':'long administrator password 123'}, method='POST')
        status, auth, _ = self.request('/api/admin/totp', {'code':pyotp.TOTP(self.secret).now()}, method='POST')
        self.assertEqual(status, 200)
        csrf = auth["csrfToken"]
        status, missing, _ = self.request('/api/admin/orders/HTTP-COD/payment', {'collectionMethod':'cash'}, method='PATCH')
        self.assertEqual((status, missing['code']), (403, 'admin_csrf_failed'))
        status, paid, _ = self.request('/api/admin/orders/HTTP-COD/payment', {'collectionMethod':'upi_at_delivery'}, headers={'X-CSRF-Token':csrf}, method='PATCH')
        self.assertEqual(status, 200)
        self.assertEqual((paid['order']['paymentStatus'], paid['order']['paymentCollectionMethod'], paid['order']['status']), ('paid','upi_at_delivery','placed'))
        status, blocked, _ = self.request('/api/admin/orders/HTTP-RAZORPAY/payment', {'collectionMethod':'cash'}, headers={'X-CSRF-Token':csrf}, method='PATCH')
        self.assertEqual((status, blocked['code']), (409, 'manual_payment_forbidden'))
        status, audit, _ = self.request('/api/admin/audit')
        self.assertEqual(status, 200)
        self.assertTrue(any(row['action']=='cod_payment_marked_paid' for row in audit['audit']))

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
        image_request = urllib.request.Request(
            self.base + body["image"]["url"],
            headers={"Host": "127.0.0.1:8081", "Origin": "http://127.0.0.1:8081"},
        )
        with self.client.open(image_request) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(response.headers.get_content_type(), "image/png")
            self.assertIn("no-store", ", ".join(response.headers.get_all("Cache-Control") or []))
            self.assertEqual(response.read(), png)

    def test_admin_product_image_upload_security_and_supported_formats(self):
        import base64
        png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")
        jpeg = base64.b64decode("/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAMCAgMCAgMDAwMEAwMEBQgFBQQEBQoHBwYIDAoMDAsKCwsNDhIQDQ4RDgsLEBYQERMUFRUVDA8XGBYUGBIUFRT/2wBDAQMEBAUEBQkFBQkUDQsNFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBT/wAARCAACAAIDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD4kooor70+KP/Z")
        webp = base64.b64decode("UklGRhYCAABXRUJQVlA4WAoAAAAgAAAAAQAAAQAASUNDUMgBAAAAAAHIAAAAAAQwAABtbnRyUkdCIFhZWiAH4AABAAEAAAAAAABhY3NwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAA9tYAAQAAAADTLQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAlkZXNjAAAA8AAAACRyWFlaAAABFAAAABRnWFlaAAABKAAAABRiWFlaAAABPAAAABR3dHB0AAABUAAAABRyVFJDAAABZAAAAChnVFJDAAABZAAAAChiVFJDAAABZAAAAChjcHJ0AAABjAAAADxtbHVjAAAAAAAAAAEAAAAMZW5VUwAAAAgAAAAcAHMAUgBHAEJYWVogAAAAAAAAb6IAADj1AAADkFhZWiAAAAAAAABimQAAt4UAABjaWFlaIAAAAAAAACSgAAAPhAAAts9YWVogAAAAAAAA9tYAAQAAAADTLXBhcmEAAAAAAAQAAAACZmYAAPKnAAANWQAAE9AAAApbAAAAAAAAAABtbHVjAAAAAAAAAAEAAAAMZW5VUwAAACAAAAAcAEcAbwBvAGcAbABlACAASQBuAGMALgAgADIAMAAxADZWUDggKAAAAJABAJ0BKgIAAgABQCYliAJ0ugADmAD++ajv7U2Kqed36FGyiXzAAAA=")
        def payload(name, mime, raw):
            return {"fileName": name, "contentType": mime, "dataBase64": base64.b64encode(raw).decode("ascii")}

        status, body, _ = self.request("/api/admin/product-images", payload("anonymous.png", "image/png", png), method="POST")
        self.assertEqual((status, body["code"]), (401, "admin_authentication_required"))
        non_admin = urllib.request.Request(
            self.base + "/api/admin/product-images",
            data=json.dumps(payload("customer.png", "image/png", png)).encode(),
            method="POST",
            headers={
                "Host": "127.0.0.1:8081", "Origin": "http://127.0.0.1:8081",
                "Content-Type": "application/json",
                "Cookie": "__Host-styledash_session=customer-cookie-is-not-an-admin-session",
            },
        )
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(non_admin)
        self.assertEqual(caught.exception.code, 401); caught.exception.close()
        self.request("/api/admin/login", {"username": "local-owner", "password": "long administrator password 123"}, method="POST")
        status, auth, _ = self.request("/api/admin/totp", {"code": pyotp.TOTP(self.secret).now()}, method="POST")
        self.assertEqual(status, 200); csrf = auth["csrfToken"]
        status, body, _ = self.request("/api/admin/product-images", payload("missing.png", "image/png", png), method="POST")
        self.assertEqual((status, body["code"]), (403, "admin_csrf_failed"))
        status, body, _ = self.request("/api/admin/product-images", payload("wrong.png", "image/png", png), headers={"X-CSRF-Token": "wrong"}, method="POST")
        self.assertEqual((status, body["code"]), (403, "admin_csrf_failed"))

        generated = []
        for filename, mime, raw, suffix in (("client-name.jpg", "image/jpeg", jpeg, ".jpg"), ("client-name.png", "image/png", png, ".png"), ("client-name.webp", "image/webp", webp, ".webp")):
            status, body, _ = self.request("/api/admin/product-images", payload(filename, mime, raw), headers={"X-CSRF-Token": csrf}, method="POST")
            self.assertEqual(status, 201)
            url = body["image"]["url"]; generated.append(url)
            self.assertRegex(url, rf"^/media/product-images/[0-9a-f]{{32}}{suffix}$")
            self.assertNotIn("client-name", url)
            self.assertEqual((self.database.parent / "product-images" / Path(url).name).read_bytes(), raw)

        for bad_payload, expected_status in (
            ({"fileName": "../outside.png", "contentType": "image/png", "dataBase64": base64.b64encode(png).decode()}, 400),
            ({"fileName": "bad.gif", "contentType": "image/gif", "dataBase64": base64.b64encode(b"GIF89a" * 8).decode()}, 400),
            ({"fileName": "bad.png", "contentType": "image/png", "dataBase64": "not-base64!!!"}, 400),
            ({"fileName": "html.jpg", "contentType": "image/jpeg", "dataBase64": base64.b64encode(b"<html>not an image</html>" * 3).decode()}, 400),
            ({"fileName": "large.png", "contentType": "image/png", "dataBase64": base64.b64encode(b"x" * (500 * 1024 + 1)).decode()}, 413),
        ):
            status, body, _ = self.request("/api/admin/product-images", bad_payload, headers={"X-CSRF-Token": csrf}, method="POST")
            self.assertEqual(status, expected_status)
        self.assertEqual(len(list((self.database.parent / "product-images").glob("*"))), 3)

        request = urllib.request.Request(self.base + "/api/admin/product-images", data=b"{bad-json", method="POST", headers={"Host":"127.0.0.1:8081","Origin":"http://127.0.0.1:8081","Content-Type":"application/json","X-CSRF-Token":csrf})
        try:
            self.client.open(request)
        except urllib.error.HTTPError as caught:
            malformed = json.loads(caught.read()); self.assertEqual((caught.code, malformed["code"]), (400, "malformed_request")); caught.close()
        else:
            self.fail("Malformed JSON upload unexpectedly succeeded")

    def test_admin_uploaded_image_supports_create_and_filename_mapped_bulk_import(self):
        import base64
        png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")
        customers = SECURITY.SecurityStore(self.database, self.key)
        user, _raw, _csrf = customers.register({"name":"Image Bulk Seller","email":"image-bulk@example.test","password":"long seller password 123","phone":"9999999966"})
        shops = ADMIN_SERVER.ShopWorkflow(self.database)
        self.request("/api/admin/login", {"username":"local-owner","password":"long administrator password 123"}, method="POST")
        status, auth, _ = self.request("/api/admin/totp", {"code":pyotp.TOTP(self.secret).now()}, method="POST")
        self.assertEqual(status, 200); csrf=auth["csrfToken"]; admin_id=auth["admin"]["id"]
        application = shops.admin_create_application(admin_id, user["id"], {"shopName":"Existing Image Shop","ownerName":"Image Bulk Seller","category":"Footwear","description":"Existing shop for safe image import.","address":"7 Main Market","city":"Neemuch","state":"Madhya Pradesh","pincode":"458441"})
        status, uploaded, _ = self.request("/api/admin/product-images", {"fileName":"product1.png","contentType":"image/png","dataBase64":base64.b64encode(png).decode()}, headers={"X-CSRF-Token":csrf}, method="POST")
        self.assertEqual(status,201); image_path=uploaded["image"]["url"]

        direct_product={"applicationId":application["id"],"name":"Uploaded Image Shoe","description":"Product created with private admin uploaded image.","brand":"Local","department":"unisex","category":"Footwear","pricePaise":90000,"originalPricePaise":90000,"variants":[{"size":"8","inventory":5}],"colourName":"Blue","imageUrls":[image_path],"attributes":{}}
        status, created, _ = self.request("/api/admin/shop-products", direct_product, headers={"X-CSRF-Token":csrf}, method="POST")
        self.assertEqual(status,201); self.assertEqual(created["product"]["imageUrls"],[image_path])
        https_product={**direct_product,"name":"HTTPS Compatibility Shoe","imageUrls":["https://example.test/shoe.jpg"]}
        status, https_created, _ = self.request("/api/admin/shop-products", https_product, headers={"X-CSRF-Token":csrf}, method="POST")
        self.assertEqual(status,201); self.assertEqual(https_created["product"]["imageUrls"],["https://example.test/shoe.jpg"])

        before={product["id"]:product for product in shops.admin_list_products(admin_id)}
        csv_text='name,description,brand,department,category,price,originalPrice,variants,colourName,colourHex,imageFile,imageUrls\nMapped Campus,Campus sports shoe,Campus,unisex,Footwear,1720,1720,"6:5, 7:5",Multi,,product1.png,\nDirect URL Shoe,Direct URL compatibility,JQR,unisex,Footwear,1350,1350,"8:5, 9:5",Olive,,,https://example.test/direct.jpg\n'
        status, bulk, _ = self.request("/api/admin/shop-products/bulk", {"applicationId":application["id"],"csvText":csv_text,"images":{"product1.png":image_path}}, headers={"X-CSRF-Token":csrf}, method="POST")
        self.assertEqual((status,bulk["created"]),(201,2))
        by_name={product["name"]:product for product in bulk["products"]}
        self.assertEqual(by_name["Mapped Campus"]["imageUrls"][0],image_path)
        self.assertEqual(by_name["Direct URL Shoe"]["imageUrls"],["https://example.test/direct.jpg"])

        fifteen_header = "name,description,brand,department,category,price,originalPrice,variants,colourName,colourHex,imageFile,imageUrls"
        fifteen_rows = [
            f'Bulk Shoe {index},Bulk shoe {index},Brand,unisex,Footwear,1099,1099,"6:5, 7:5",Color {index},,product{index}.png,'
            for index in range(1, 16)
        ]
        fifteen_csv = "\n".join([fifteen_header, *fifteen_rows]) + "\n"
        fifteen_images = {f"product{index}.png": image_path for index in range(1, 16)}
        status, fifteen_bulk, _ = self.request(
            "/api/admin/shop-products/bulk",
            {"applicationId": application["id"], "csvText": fifteen_csv, "images": fifteen_images},
            headers={"X-CSRF-Token": csrf}, method="POST",
        )
        self.assertEqual((status, fifteen_bulk["created"]), (201, 15))
        for product_id, original in before.items():
            after=next(product for product in shops.admin_list_products(admin_id) if product["id"]==product_id)
            self.assertEqual((after["name"],after["imageUrls"]),(original["name"],original["imageUrls"]))

        count_before=len(shops.admin_list_products(admin_id))
        missing_csv='name,description,department,category,price,variants,colourName,imageFile\nMissing Image,Should fail,unisex,Footwear,999,"8:5",Black,missing.jpg\n'
        status, missing, _ = self.request("/api/admin/shop-products/bulk", {"applicationId":application["id"],"csvText":missing_csv,"images":{}}, headers={"X-CSRF-Token":csrf}, method="POST")
        self.assertEqual((status,missing["code"]),(400,"invalid_product_import"))
        self.assertEqual(missing["error"],'Row 1: Image file "missing.jpg" was not selected.')
        self.assertEqual(len(shops.admin_list_products(admin_id)),count_before)
        nan_csv='name,description,department,category,price,variants,colourName,imageUrls\nBad Price,Must fail,unisex,Footwear,nan,"8:5",Black,https://example.test/a.jpg\n'
        status, invalid_price, _ = self.request("/api/admin/shop-products/bulk", {"applicationId":application["id"],"csvText":nan_csv,"images":{}}, headers={"X-CSRF-Token":csrf}, method="POST")
        self.assertEqual((status, invalid_price["code"]), (400, "invalid_product_import"))
        self.assertIn("Row 1: Invalid price.", invalid_price["error"])
        self.assertEqual(len(shops.admin_list_products(admin_id)),count_before)

    def test_non_loopback_bind_refused(self):
        with self.assertRaises(RuntimeError):
            ADMIN_SERVER.create_admin_server("0.0.0.0", 0, self.database, self.key, ROOT / "server/payment-data/catalog.json", ROOT / "server/payment-data/settings.json", self.root / "data2", ROOT / "server/admin", self.root / "backups")


if __name__ == "__main__":
    unittest.main()
