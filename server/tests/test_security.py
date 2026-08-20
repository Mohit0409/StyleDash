from __future__ import annotations

import importlib.util
import json
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from cryptography.fernet import Fernet


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("styledash_security", ROOT / "scripts" / "styledash_security.py")
assert SPEC and SPEC.loader
SECURITY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SECURITY)


class DummyPaymentStore:
    def __init__(self):
        import threading
        self.lock = threading.RLock()
        self.state = {"orders": {
            "ORDER-A": {"id": "ORDER-A", "userId": "user-a", "paymentStatus": "paid", "status": "placed"},
            "ORDER-B": {"id": "ORDER-B", "userId": "user-b", "paymentStatus": "pending"},
        }}

    def save(self):
        pass


class SecurityStoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / "styledash.db"
        self.store = SECURITY.SecurityStore(self.path, Fernet.generate_key().decode())

    def tearDown(self):
        self.temporary.cleanup()

    def registration(self, email="customer-a@example.test", password="long test password 123"):
        return self.store.register({"name": "Customer A", "email": email, "password": password, "phone": "9999999999"})

    def assert_security_error(self, code, callback):
        with self.assertRaises(SECURITY.SecurityError) as caught:
            callback()
        self.assertEqual(caught.exception.code, code)

    def test_registration_argon2_unique_email_and_no_role_escalation(self):
        user, raw, csrf = self.registration()
        self.assertEqual(user["role"], "customer")
        self.assertFalse(user["emailVerified"])
        self.assertTrue(raw and csrf)
        with self.store.connect() as db:
            row = db.execute(
                "SELECT password_hash,email_verified,email_verified_at FROM users WHERE id=?",
                (user["id"],),
            ).fetchone()
            self.assertTrue(row["password_hash"].startswith("$argon2id$"))
            self.assertNotIn("long test password", row["password_hash"])
            self.assertEqual(row["email_verified"], 0)
            self.assertIsNone(row["email_verified_at"])
        self.assert_security_error("email_exists", self.registration)
        self.assert_security_error("invalid_registration", lambda: self.store.register({
            "name": "Attacker", "email": "attacker@example.test", "password": "long test password 123", "role": "admin"
        }))
        self.assert_security_error("invalid_registration", lambda: self.store.register({
            "name": "Attacker", "email": "verified-attacker@example.test",
            "password": "long test password 123", "emailVerified": True,
        }))

    def test_password_policy_and_sql_injection_input(self):
        self.assert_security_error("weak_password", lambda: self.store.register({
            "name": "Short", "email": "short@example.test", "password": "short"
        }))
        self.assert_security_error("invalid_email", lambda: self.registration("x' OR 1=1--@example.test"))

    def test_login_logout_cookie_and_hashed_session(self):
        user, first_raw, _csrf = self.registration()
        self.store.revoke(first_raw)
        logged_in, raw, csrf = self.store.login({
            "email": user["email"], "password": "long test password 123",
            "emailVerified": True, "email_verified_at": "2099-01-01T00:00:00+00:00",
        }, "client-a")
        self.assertFalse(logged_in["emailVerified"])
        cookie = self.store.cookie(raw)
        for flag in ("__Host-styledash_session=", "HttpOnly", "Secure", "SameSite=Lax", "Path=/"):
            self.assertIn(flag, cookie)
        with self.store.connect() as db:
            stored = db.execute("SELECT token_hash FROM sessions WHERE token_hash=?", (SECURITY.token_hash(raw),)).fetchone()
            self.assertIsNotNone(stored)
            self.assertIsNone(db.execute("SELECT 1 FROM sessions WHERE token_hash=?", (raw,)).fetchone())
        self.store.verify_csrf(raw, csrf)
        self.assert_security_error("csrf_failed", lambda: self.store.verify_csrf(raw, "wrong"))
        self.store.revoke(raw)
        self.assert_security_error("authentication_required", lambda: self.store.authenticate(raw))
        self.assertEqual(logged_in["id"], user["id"])

    def test_wrong_unknown_disabled_and_rate_limited_login(self):
        user, raw, _csrf = self.registration()
        self.store.revoke(raw)
        self.assert_security_error("invalid_credentials", lambda: self.store.login({"email": user["email"], "password": "wrong password value"}, "client-b"))
        self.assert_security_error("invalid_credentials", lambda: self.store.login({"email": "unknown@example.test", "password": "wrong password value"}, "client-b"))
        with self.store.connect() as db:
            db.execute("UPDATE users SET is_active=0 WHERE id=?", (user["id"],))
        self.assert_security_error("invalid_credentials", lambda: self.store.login({"email": user["email"], "password": "long test password 123"}, "client-c"))
        with self.store.connect() as db:
            db.execute("UPDATE users SET is_active=1 WHERE id=?", (user["id"],))
        for index in range(8):
            try: self.store.login({"email": user["email"], "password": "wrong password value"}, f"client-{index}")
            except SECURITY.SecurityError: pass
        self.assert_security_error("login_rate_limited", lambda: self.store.login({"email": user["email"], "password": "long test password 123"}, "new-client"))

    def test_password_change_revokes_other_sessions(self):
        user, first, csrf = self.registration()
        _user, second, _csrf = self.store.login({"email": user["email"], "password": "long test password 123"}, "client-change")
        self.store.verify_csrf(first, csrf)
        refreshed, refreshed_csrf = self.store.change_password(first, {"currentPassword": "long test password 123", "newPassword": "new long password 456"})
        self.assert_security_error("authentication_required", lambda: self.store.authenticate(second))
        refreshed_user, _session = self.store.authenticate(refreshed)
        self.assertFalse(refreshed_user["emailVerified"])
        self.store.verify_csrf(refreshed, refreshed_csrf)

    def test_password_reset_hash_expiry_single_use_and_session_revocation(self):
        deliveries = []
        reset_store = SECURITY.SecurityStore(
            Path(self.temporary.name) / "reset.db", Fernet.generate_key().decode(),
            password_reset_sender=lambda email, token: deliveries.append((email, token)),
        )
        user, first, _csrf = reset_store.register({
            "name": "Reset Customer", "email": "reset@example.test",
            "password": "long test password 123", "phone": "9999999999",
        })
        _user, second, _csrf = reset_store.login({"email": user["email"], "password": "long test password 123"}, "reset-client")
        self.assertFalse(user["emailVerified"])
        reset_store.request_password_reset({"email": user["email"]})
        self.assertEqual(len(deliveries), 1)
        token = deliveries[0][1]
        self.assert_security_error("weak_password", lambda: reset_store.confirm_password_reset({"token": token, "newPassword": "short"}))
        reset_store.request_password_reset({"email": user["email"]})
        replacement = deliveries[-1][1]
        self.assert_security_error("invalid_reset_token", lambda: reset_store.confirm_password_reset({"token": token, "newPassword": "new long password 456"}))
        with reset_store.connect() as db:
            row = db.execute("SELECT token_hash,expires_at,used_at FROM password_reset_tokens WHERE token_hash=?", (SECURITY.token_hash(replacement),)).fetchone()
            self.assertEqual(row["token_hash"], SECURITY.token_hash(replacement))
            self.assertNotEqual(row["token_hash"], replacement)
            self.assertIsNone(row["used_at"])

        reset_store.confirm_password_reset({"token": replacement, "newPassword": "new long password 456"})
        with reset_store.connect() as db:
            verification = db.execute(
                "SELECT email_verified,email_verified_at FROM users WHERE id=?", (user["id"],)
            ).fetchone()
            self.assertEqual(verification["email_verified"], 1)
            self.assertIsNotNone(verification["email_verified_at"])
        self.assert_security_error("authentication_required", lambda: reset_store.authenticate(first))
        self.assert_security_error("authentication_required", lambda: reset_store.authenticate(second))
        self.assert_security_error("invalid_credentials", lambda: reset_store.login({"email": user["email"], "password": "long test password 123"}, "old-password"))
        self.assert_security_error("invalid_reset_token", lambda: reset_store.confirm_password_reset({"token": replacement, "newPassword": "another long password 789"}))
        fresh_user, fresh, _csrf = reset_store.login({
            "email": user["email"], "password": "new long password 456",
            "emailVerified": False,
        }, "fresh-client")
        self.assertTrue(fresh_user["emailVerified"])
        authenticated, _session = reset_store.authenticate(fresh)
        self.assertTrue(authenticated["emailVerified"])

        reset_store.request_password_reset({"email": user["email"]})
        expired = deliveries[-1][1]
        with reset_store.connect() as db:
            db.execute("UPDATE password_reset_tokens SET expires_at='2000-01-01T00:00:00+00:00' WHERE token_hash=?", (SECURITY.token_hash(expired),))
        self.assert_security_error("invalid_reset_token", lambda: reset_store.confirm_password_reset({"token": expired, "newPassword": "another long password 789"}))

    def test_password_reset_concurrent_reuse_allows_only_one_confirmation(self):
        deliveries = []
        reset_store = SECURITY.SecurityStore(
            Path(self.temporary.name) / "concurrent-reset.db", Fernet.generate_key().decode(),
            password_reset_sender=lambda email, token: deliveries.append((email, token)),
        )
        user, _raw, _csrf = reset_store.register({
            "name": "Reset Customer", "email": "concurrent-reset@example.test",
            "password": "long test password 123", "phone": "9999999999",
        })
        reset_store.request_password_reset({"email": user["email"]})
        token = deliveries[0][1]

        def confirm_once() -> str:
            try:
                reset_store.confirm_password_reset({"token": token, "newPassword": "new long password 456"})
                return "success"
            except SECURITY.SecurityError as error:
                return error.code

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _value: confirm_once(), range(2)))
        self.assertEqual(results.count("success"), 1)
        self.assertEqual(results.count("invalid_reset_token"), 1)

    def test_disabled_customer_cannot_receive_or_use_reset_token(self):
        deliveries = []
        reset_store = SECURITY.SecurityStore(
            Path(self.temporary.name) / "disabled-reset.db", Fernet.generate_key().decode(),
            password_reset_sender=lambda email, token: deliveries.append((email, token)),
        )
        user, _raw, _csrf = reset_store.register({
            "name": "Reset Customer", "email": "disabled-reset@example.test",
            "password": "long test password 123", "phone": "9999999999",
        })
        with reset_store.connect() as db:
            db.execute("UPDATE users SET is_active=0 WHERE id=?", (user["id"],))
        reset_store.request_password_reset({"email": user["email"]})
        self.assertEqual(deliveries, [])
        with reset_store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM password_reset_tokens").fetchone()[0], 0)

        with reset_store.connect() as db:
            db.execute("UPDATE users SET is_active=1 WHERE id=?", (user["id"],))
        reset_store.request_password_reset({"email": user["email"]})
        token = deliveries[0][1]
        with reset_store.connect() as db:
            db.execute("UPDATE users SET is_active=0 WHERE id=?", (user["id"],))
        self.assert_security_error("invalid_reset_token", lambda: reset_store.confirm_password_reset({"token": token, "newPassword": "new long password 456"}))
        with reset_store.connect() as db:
            self.assertIsNotNone(db.execute("SELECT used_at FROM password_reset_tokens WHERE token_hash=?", (SECURITY.token_hash(token),)).fetchone()["used_at"])
            self.assertIsNone(db.execute(
                "SELECT email_verified_at FROM users WHERE id=?", (user["id"],)
            ).fetchone()["email_verified_at"])

    def test_password_reset_is_enumeration_safe_without_delivery(self):
        self.registration()
        self.store.request_password_reset({"email": "customer-a@example.test"})
        self.store.request_password_reset({"email": "unknown@example.test"})
        self.store.request_password_reset({"email": "not an email"})
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM password_reset_tokens").fetchone()[0], 0)

    def test_password_reset_delivery_failure_consumes_new_token(self):
        def failed_delivery(_email, _token):
            raise RuntimeError("test-only delivery failure")

        reset_store = SECURITY.SecurityStore(
            Path(self.temporary.name) / "failed-delivery.db", Fernet.generate_key().decode(),
            password_reset_sender=failed_delivery,
        )
        user, _raw, _csrf = reset_store.register({
            "name": "Reset Customer", "email": "failed-delivery@example.test",
            "password": "long test password 123", "phone": "9999999999",
        })
        reset_store.request_password_reset({"email": user["email"]})
        with reset_store.connect() as db:
            stored = db.execute("SELECT token_hash,used_at FROM password_reset_tokens").fetchone()
            self.assertIsNotNone(stored["token_hash"])
            self.assertIsNotNone(stored["used_at"])
            self.assertIsNone(db.execute(
                "SELECT email_verified_at FROM users WHERE id=?", (user["id"],)
            ).fetchone()["email_verified_at"])

    def test_expired_session_is_rejected_and_revoked(self):
        _user, raw, _csrf = self.registration()
        with self.store.connect() as db:
            db.execute("UPDATE sessions SET expires_at='2000-01-01T00:00:00+00:00' WHERE token_hash=?", (SECURITY.token_hash(raw),))
        self.assert_security_error("session_expired", lambda: self.store.authenticate(raw))
        with self.store.connect() as db:
            self.assertIsNotNone(db.execute("SELECT revoked_at FROM sessions WHERE token_hash=?", (SECURITY.token_hash(raw),)).fetchone()[0])

    def test_customer_order_ownership_enforcement(self):
        self.registration()
        payment = DummyPaymentStore()
        orders = self.store.list_orders(payment, "user-a")
        self.assertEqual([item["id"] for item in orders], ["ORDER-A"])
        self.assert_security_error("order_not_found", lambda: self.store.get_order(payment, "ORDER-B", "user-a"))

    def test_vendor_application_is_always_pending(self):
        user, _raw, _csrf = self.registration()
        application = self.store.create_vendor_application(user["id"], {
            "storeName": "Test Shop", "ownerName": "Customer A", "email": user["email"],
            "phone": "9999999999", "category": "Clothing & Fashion", "address": "123 Test Market",
            "pincode": "458441", "description": "A test-only vendor application",
            "status": "approved",
        })
        self.assertEqual(application["status"], "pending")
        with self.store.connect() as db:
            stored = db.execute("SELECT status FROM vendor_applications WHERE id=?", (application["id"],)).fetchone()
            self.assertEqual(stored[0], "pending")

    def test_profile_role_is_immutable_and_address_is_server_stored(self):
        user, _raw, _csrf = self.registration()
        profile = self.store.update_profile(user["id"], {
            "name": "Updated Customer", "phone": "9888888888",
            "addresses": [{"name": "Updated Customer", "phone": "9888888888", "street": "123 Test Street", "city": "Neemuch", "state": "Madhya Pradesh", "pincode": "458441", "type": "home", "isDefault": True}],
        })
        self.assertEqual(profile["name"], "Updated Customer")
        self.assertEqual(profile["addresses"][0]["street"], "123 Test Street")
        self.assert_security_error("invalid_profile", lambda: self.store.update_profile(user["id"], {"role": "admin"}))
        self.assert_security_error("invalid_profile", lambda: self.store.update_profile(
            user["id"], {"emailVerified": True, "email_verified_at": "2099-01-01T00:00:00+00:00"}
        ))

    def test_customer_web_login_rejects_non_customer_role(self):
        user, raw, _csrf = self.registration()
        self.store.revoke(raw)
        with self.store.connect() as db:
            db.execute("UPDATE users SET role='admin' WHERE id=?", (user["id"],))
        self.assert_security_error("invalid_credentials", lambda: self.store.login({"email": user["email"], "password": "long test password 123"}, "public-client"))

    def test_foreign_keys_migrations_integrity_and_backup(self):
        with self.store.connect() as db:
            self.assertEqual(db.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            self.assertEqual(db.execute("PRAGMA journal_mode").fetchone()[0], "wal")
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(db.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0], 6)
            backup_path = Path(self.temporary.name) / "backup.db"
            backup = sqlite3.connect(backup_path)
            db.backup(backup)
            backup.close()
        restored = sqlite3.connect(backup_path)
        self.assertEqual(restored.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        restored.close()

    def test_email_verification_timestamp_migration_is_forward_safe_and_idempotent(self):
        legacy_path = Path(self.temporary.name) / "legacy-email-verification.db"
        legacy = sqlite3.connect(legacy_path)
        legacy.executescript(
            """
            CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
            CREATE TABLE users(
              id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL,
              name TEXT NOT NULL, phone TEXT, role TEXT NOT NULL DEFAULT 'customer',
              is_active INTEGER NOT NULL DEFAULT 1, email_verified INTEGER NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL, updated_at TEXT NOT NULL, password_changed_at TEXT NOT NULL
            );
            INSERT INTO schema_migrations(version,applied_at) VALUES(1,'2026-01-01T00:00:00+00:00');
            INSERT INTO schema_migrations(version,applied_at) VALUES(2,'2026-01-01T00:00:00+00:00');
            INSERT INTO users(
              id,email,password_hash,name,phone,role,is_active,email_verified,
              created_at,updated_at,password_changed_at
            ) VALUES(
              'usr_legacy','legacy-owner@example.test','legacy-hash','Legacy Owner',NULL,
              'customer',1,1,'2026-01-01T00:00:00+00:00',
              '2026-01-01T00:00:00+00:00','2026-01-01T00:00:00+00:00'
            );
            """
        )
        legacy.commit()
        legacy.close()

        key = Fernet.generate_key().decode()
        migrated = SECURITY.SecurityStore(legacy_path, key)
        with migrated.connect() as db:
            columns = {row["name"] for row in db.execute("PRAGMA table_info(users)")}
            self.assertIn("email_verified_at", columns)
            self.assertIn("last_login_at", columns)
            self.assertIn("normalized_email", columns)
            self.assertIn("normalized_phone", columns)
            row = db.execute(
                "SELECT email,email_verified,email_verified_at FROM users WHERE id='usr_legacy'"
            ).fetchone()
            self.assertEqual((row["email"], row["email_verified"]), ("legacy-owner@example.test", 1))
            self.assertIsNone(row["email_verified_at"])
            self.assertEqual(db.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0], 6)
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        self.assertFalse(migrated.profile("usr_legacy")["emailVerified"])

        reopened = SECURITY.SecurityStore(legacy_path, key)
        with reopened.connect() as db:
            self.assertEqual(
                db.execute("SELECT COUNT(*) FROM schema_migrations WHERE version=4").fetchone()[0],
                1,
            )
            self.assertEqual(
                db.execute("SELECT COUNT(*) FROM schema_migrations WHERE version=5").fetchone()[0],
                1,
            )
            self.assertEqual(
                db.execute("SELECT COUNT(*) FROM schema_migrations WHERE version=6").fetchone()[0],
                1,
            )
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")


if __name__ == "__main__":
    unittest.main()
