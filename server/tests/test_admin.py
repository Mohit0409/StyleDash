from __future__ import annotations

import importlib.util
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
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
            app.payments.store.save()
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
        status, body, _headers = self.request("/api/admin/logout", {}, method="POST")
        self.assertEqual((status, body["code"]), (403, "admin_csrf_failed"))
        status, body, _headers = self.request("/api/admin/logout", {}, headers={"X-CSRF-Token": csrf}, method="POST")
        self.assertEqual(status, 200)

    def test_non_loopback_bind_refused(self):
        with self.assertRaises(RuntimeError):
            ADMIN_SERVER.create_admin_server("0.0.0.0", 0, self.database, self.key, ROOT / "server/payment-data/catalog.json", ROOT / "server/payment-data/settings.json", self.root / "data2", ROOT / "server/admin", self.root / "backups")


if __name__ == "__main__":
    unittest.main()
