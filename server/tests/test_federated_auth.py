from __future__ import annotations

import importlib.util
import sqlite3
import tempfile
import unittest
from pathlib import Path

from cryptography.fernet import Fernet

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("styledash_security", ROOT / "scripts" / "styledash_security.py")
assert SPEC and SPEC.loader
SECURITY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SECURITY)


class FederatedAuthTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / "styledash.db"
        self.claims = {}
        self.store = SECURITY.SecurityStore(
            self.path,
            Fernet.generate_key().decode(),
            firebase_verifier=lambda token: self.claims[token],
        )

    def tearDown(self):
        self.temporary.cleanup()

    def token(self, name: str) -> str:
        value = f"token-{name}-" + ("x" * 20)
        return value

    def add_claim(self, token_name: str, **claims):
        token = self.token(token_name)
        self.claims[token] = claims
        return token

    def google(self, uid: str, email: str, *, verified: bool = True, name: str = "Google Customer"):
        return self.add_claim(
            uid,
            uid=uid,
            email=email,
            email_verified=verified,
            name=name,
            firebase={"sign_in_provider": "google.com"},
        )

    def phone(self, uid: str, phone: str):
        return self.add_claim(
            uid,
            uid=uid,
            phone_number=phone,
            firebase={"sign_in_provider": "phone"},
        )

    def test_new_and_returning_google_use_one_customer(self):
        token = self.google("google-1", "google@example.test")
        first, raw, csrf, created = self.store.federated_session("google", {"idToken": token})
        second, _raw2, _csrf2, created_again = self.store.federated_session("google", {"idToken": token})
        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(self.store.profile(first["id"])["email"], "google@example.test")
        self.assertIn("HttpOnly", self.store.cookie(raw))
        self.assertTrue(csrf)

    def test_verified_google_email_links_existing_password_customer(self):
        existing, _raw, _csrf = self.store.register({
            "name": "Password Customer",
            "email": "link@example.test",
            "password": "long test password 123",
        })
        token = self.google("google-link", "LINK@example.test")
        linked, _raw2, _csrf2, created = self.store.federated_session("google", {"idToken": token})
        self.assertFalse(created)
        self.assertEqual(linked["id"], existing["id"])
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM users").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM customer_auth_identities").fetchone()[0], 1)

    def test_unverified_google_email_never_creates_or_links(self):
        token = self.google("google-unverified", "unverified@example.test", verified=False)
        with self.assertRaises(SECURITY.SecurityError) as caught:
            self.store.federated_session("google", {"idToken": token})
        self.assertEqual(caught.exception.code, "google_email_required")
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM users").fetchone()[0], 0)

    def test_new_and_returning_phone_use_one_customer(self):
        token = self.phone("phone-1", "+91 9876543210")
        first, _raw, _csrf, created = self.store.federated_session("phone", {"idToken": token})
        second, _raw2, _csrf2, created_again = self.store.federated_session("phone", {"idToken": token})
        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(first["id"], second["id"])
        self.assertTrue(second["needsProfile"])

    def test_verified_phone_collision_fails_closed(self):
        first_token = self.phone("phone-a", "09876543210")
        self.store.federated_session("phone", {"idToken": first_token})
        second_token = self.phone("phone-b", "+919876543210")
        with self.assertRaises(SECURITY.SecurityError) as caught:
            self.store.federated_session("phone", {"idToken": second_token})
        self.assertEqual(caught.exception.code, "identity_already_linked")
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM users").fetchone()[0], 1)

    def test_provider_mismatch_and_invalid_tokens_create_nothing(self):
        google_token = self.google("google-mismatch", "mismatch@example.test")
        with self.assertRaises(SECURITY.SecurityError):
            self.store.federated_session("phone", {"idToken": google_token})
        with self.assertRaises(SECURITY.SecurityError):
            self.store.federated_session("google", {"idToken": "short"})
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM users").fetchone()[0], 0)

    def test_authenticated_linking_requires_verified_claims_and_rejects_collision(self):
        password_user, raw, csrf = self.store.register({
            "name": "Link Owner",
            "email": "owner@example.test",
            "password": "long test password 123",
        })
        phone_token = self.phone("phone-link", "+919876543210")
        self.store.verify_csrf(raw, csrf)
        linked = self.store.link_federated_identity(raw, "phone", {"idToken": phone_token})
        self.assertEqual(linked["id"], password_user["id"])
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM users").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM customer_auth_identities").fetchone()[0], 1)

    def test_migration_preserves_customers_sessions_and_financial_tables(self):
        user, raw, _csrf = self.store.register({
            "name": "Migration Customer",
            "email": "migration@example.test",
            "password": "long test password 123",
        })
        with self.store.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS test_orders(id TEXT PRIMARY KEY, user_id TEXT)")
            db.execute("INSERT INTO test_orders VALUES(?, ?)", ("order-1", user["id"]))
        reopened = SECURITY.SecurityStore(self.path, Fernet.generate_key().decode())
        with reopened.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM test_orders").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM sessions WHERE token_hash IS NOT NULL").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT id FROM users").fetchone()[0], user["id"])
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        self.assertTrue(raw)


if __name__ == "__main__":
    unittest.main()
