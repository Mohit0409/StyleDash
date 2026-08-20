from __future__ import annotations

import importlib.util
import sqlite3
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from cryptography.fernet import Fernet

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("styledash_security", ROOT / "scripts" / "styledash_security.py")
assert SPEC and SPEC.loader
SECURITY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SECURITY)
AUDIT_SPEC = importlib.util.spec_from_file_location(
    "audit_identity_duplicates", ROOT / "scripts" / "audit_identity_duplicates.py"
)
assert AUDIT_SPEC and AUDIT_SPEC.loader
AUDIT = importlib.util.module_from_spec(AUDIT_SPEC)
AUDIT_SPEC.loader.exec_module(AUDIT)


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
            email=None,
            phone_number=phone,
            firebase={"sign_in_provider": "phone"},
        )

    def test_new_and_returning_google_use_one_customer(self):
        token = self.google("google-1", "google@example.test")
        first, raw, csrf, created = self.store.federated_session("google", {"idToken": token})
        with self.store.connect() as db:
            db.execute("UPDATE users SET last_login_at='stale' WHERE id=?", (first["id"],))
            db.execute("UPDATE customer_auth_identities SET last_used_at='stale' WHERE user_id=?", (first["id"],))
        second, raw2, csrf2, created_again = self.store.federated_session("google", {"idToken": token})
        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(self.store.profile(first["id"])["email"], "google@example.test")
        self.assertIn("HttpOnly", self.store.cookie(raw))
        self.assertTrue(csrf)
        self.assertNotEqual(raw, raw2)
        self.assertNotEqual(csrf, csrf2)
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM users").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM customer_auth_identities").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0], 2)
            login_at = db.execute("SELECT last_login_at FROM users WHERE id=?", (first["id"],)).fetchone()[0]
            last_used_at = db.execute(
                "SELECT last_used_at FROM customer_auth_identities WHERE user_id=?", (first["id"],)
            ).fetchone()[0]
        self.assertNotEqual(login_at, "stale")
        self.assertNotEqual(last_used_at, "stale")

    def test_concurrent_returning_google_login_reuses_uid_and_email(self):
        token = self.google("google-concurrent", "Concurrent@Example.Test")
        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(
                lambda _index: self.store.federated_session("google", {"idToken": token}),
                range(6),
            ))
        self.assertEqual(len({result[0]["id"] for result in results}), 1)
        self.assertEqual(sum(int(result[3]) for result in results), 1)
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM users").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM customer_auth_identities").fetchone()[0], 1)
            self.assertEqual(
                db.execute("SELECT normalized_email FROM users").fetchone()[0],
                "concurrent@example.test",
            )

    def test_verified_google_email_requires_authenticated_linking(self):
        existing, raw, _csrf = self.store.register({
            "name": "Password Customer",
            "email": "link@example.test",
            "password": "long test password 123",
        })
        token = self.google("google-link", "LINK@example.test")
        with self.assertRaises(SECURITY.SecurityError) as conflict:
            self.store.federated_session("google", {"idToken": token})
        self.assertEqual((conflict.exception.status, conflict.exception.code), (409, "account_link_required"))
        linked = self.store.link_federated_identity(raw, "google", {"idToken": token})
        self.assertEqual(linked["id"], existing["id"])
        returning, _raw2, _csrf2, created = self.store.federated_session("google", {"idToken": token})
        self.assertFalse(created)
        self.assertEqual(returning["id"], existing["id"])
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM users").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM customer_auth_identities").fetchone()[0], 1)

    def test_google_email_conflict_cannot_be_linked_from_another_customer(self):
        owner, _owner_raw, _csrf = self.store.register({
            "name": "Email Owner", "email": "owner@example.test", "password": "long owner password 123",
        })
        other, other_raw, _csrf2 = self.store.register({
            "name": "Other Customer", "email": "other@example.test", "password": "long other password 123",
        })
        token = self.google("owner-google", "OWNER@example.test")
        with self.assertRaises(SECURITY.SecurityError) as conflict:
            self.store.link_federated_identity(other_raw, "google", {"idToken": token})
        self.assertEqual(conflict.exception.code, "account_link_required")
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM customer_auth_identities").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM users").fetchone()[0], 2)
        self.assertNotEqual(owner["id"], other["id"])

    def test_google_email_link_reserves_email_against_later_registration(self):
        _owner, raw, _csrf = self.store.register({
            "name": "Cross Email Owner", "email": "primary@example.test",
            "password": "long primary password 123",
        })
        token = self.google("cross-email-google", "google-alias@example.test")
        self.store.link_federated_identity(raw, "google", {"idToken": token})
        with self.assertRaises(SECURITY.SecurityError) as duplicate:
            self.store.register({
                "name": "Duplicate Alias", "email": "GOOGLE-ALIAS@example.test",
                "password": "long duplicate alias password 123",
            })
        self.assertEqual((duplicate.exception.status, duplicate.exception.code), (409, "email_exists"))
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM users").fetchone()[0], 1)

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
        with self.store.connect() as db:
            columns = {row["name"]: row for row in db.execute("PRAGMA table_info(users)")}
            user = db.execute("SELECT email,password_hash,phone,last_login_at FROM users WHERE id=?", (first["id"],)).fetchone()
            identity = db.execute(
                "SELECT provider,provider_subject,verified_email,verified_phone FROM customer_auth_identities WHERE user_id=?",
                (first["id"],),
            ).fetchone()
        self.assertEqual(columns["email"]["notnull"], 0)
        self.assertEqual(columns["password_hash"]["notnull"], 0)
        self.assertIsNone(user["email"])
        self.assertIsNone(user["password_hash"])
        self.assertEqual(user["phone"], "+919876543210")
        self.assertTrue(user["last_login_at"])
        self.assertEqual((identity["provider"], identity["provider_subject"]), ("phone", "phone-1"))
        self.assertIsNone(identity["verified_email"])
        self.assertEqual(identity["verified_phone"], "+919876543210")
        with self.store.connect() as db:
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute(
                    "INSERT INTO users(id,email,normalized_email,password_hash,name,phone,normalized_phone,"
                    "created_at,updated_at,password_changed_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                    ("usr_duplicate", None, None, None, "Duplicate", "+919876543210", "+919876543210", "x", "x", "x"),
                )
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute(
                    "INSERT INTO customer_auth_identities(id,user_id,provider,provider_subject,verified_phone,"
                    "created_at,last_used_at) VALUES(?,?,?,?,?,?,?)",
                    ("cai_duplicate", first["id"], "phone", "phone-other", "+919876543210", "x", "x"),
                )

    def test_malformed_nested_firebase_claim_fails_closed(self):
        token = self.add_claim("malformed-firebase", uid="malformed-firebase", firebase="phone")
        with self.assertRaises(SECURITY.SecurityError) as caught:
            self.store.federated_session("phone", {"idToken": token})
        self.assertEqual(caught.exception.code, "identity_verification_failed")
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM users").fetchone()[0], 0)

    def test_federated_only_account_password_change_returns_controlled_error(self):
        token = self.phone("phone-no-password", "+919999999999")
        user, raw, _csrf, _created = self.store.federated_session("phone", {"idToken": token})
        with self.assertRaises(SECURITY.SecurityError) as caught:
            self.store.change_password(raw, {
                "currentPassword": "unused current password",
                "newPassword": "new long password 456",
            })
        self.assertEqual((caught.exception.status, caught.exception.code), (409, "password_not_set"))
        self.assertEqual(self.store.authenticate(raw)[0]["id"], user["id"])

    def test_federated_login_rejects_inactive_and_non_customer_accounts(self):
        inactive, _raw, _csrf = self.store.register({
            "name": "Inactive Customer",
            "email": "inactive@example.test",
            "password": "long inactive password 123",
        })
        with self.store.connect() as db:
            db.execute("UPDATE users SET is_active=0 WHERE id=?", (inactive["id"],))
        with self.assertRaises(SECURITY.SecurityError) as inactive_error:
            self.store.federated_session(
                "google", {"idToken": self.google("inactive-google", "inactive@example.test")}
            )
        self.assertEqual(inactive_error.exception.code, "identity_verification_failed")

        legacy, legacy_raw, _csrf = self.store.register({
            "name": "Legacy Role",
            "email": "legacy-role@example.test",
            "password": "long legacy password 123",
        })
        with self.store.connect() as db:
            db.execute("UPDATE users SET role='admin' WHERE id=?", (legacy["id"],))
        with self.assertRaises(SECURITY.SecurityError) as role_error:
            self.store.federated_session(
                "google", {"idToken": self.google("legacy-google", "legacy-role@example.test")}
            )
        self.assertEqual(role_error.exception.code, "identity_verification_failed")
        with self.assertRaises(SECURITY.SecurityError):
            self.store.authenticate(legacy_raw)
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM customer_auth_identities").fetchone()[0], 0)

    def test_new_firebase_uid_for_verified_phone_reuses_linked_customer(self):
        first_token = self.phone("phone-a", "09876543210")
        first, _raw, _csrf, created = self.store.federated_session("phone", {"idToken": first_token})
        second_token = self.phone("phone-b", "+919876543210")
        second, _raw2, _csrf2, created_again = self.store.federated_session(
            "phone", {"idToken": second_token}
        )
        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(second["id"], first["id"])
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM users").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM customer_auth_identities").fetchone()[0], 1)
            identity = db.execute(
                "SELECT provider_subject,verified_phone FROM customer_auth_identities"
            ).fetchone()
        self.assertEqual((identity["provider_subject"], identity["verified_phone"]), (
            "phone-b", "+919876543210",
        ))

    def test_concurrent_replacement_phone_uids_never_duplicate_customer(self):
        original = self.phone("phone-original", "+919876543210")
        user, _raw, _csrf, _created = self.store.federated_session("phone", {"idToken": original})
        replacements = [
            self.phone(f"phone-replacement-{index}", "+919876543210") for index in range(6)
        ]
        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(
                lambda token: self.store.federated_session("phone", {"idToken": token}),
                replacements,
            ))
        self.assertEqual({result[0]["id"] for result in results}, {user["id"]})
        self.assertFalse(any(result[3] for result in results))
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM users").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM customer_auth_identities").fetchone()[0], 1)

    def test_existing_phone_uid_can_change_number_without_taking_another_customer(self):
        token = self.phone("phone-change", "+919876543210")
        user, _raw, _csrf, _created = self.store.federated_session("phone", {"idToken": token})
        self.claims[token]["phone_number"] = "+919876543211"
        changed, _raw2, _csrf2, created_again = self.store.federated_session(
            "phone", {"idToken": token}
        )
        self.assertEqual(changed["id"], user["id"])
        self.assertFalse(created_again)
        self.assertEqual(changed["phone"], "+919876543211")

        self.store.register({
            "name": "Other Phone", "email": "other-phone@example.test",
            "password": "long other phone password 123", "phone": "+919876543212",
        })
        self.claims[token]["phone_number"] = "+919876543212"
        with self.assertRaises(SECURITY.SecurityError) as collision:
            self.store.federated_session("phone", {"idToken": token})
        self.assertEqual(collision.exception.code, "identity_already_linked")
        self.assertEqual(self.store.profile(user["id"])["phone"], "+919876543211")

    def test_equivalent_phone_formats_and_concurrent_login_create_one_customer(self):
        formats = [
            "9876543210", "09876543210", "91 9876543210", "+91 9876543210", "+919876543210",
        ]
        self.assertEqual(
            {SECURITY.normalize_indian_phone(value) for value in formats},
            {"+919876543210"},
        )
        token = self.phone("phone-concurrent", formats[-1])
        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(
                lambda _index: self.store.federated_session("phone", {"idToken": token}),
                range(6),
            ))
        self.assertEqual(len({result[0]["id"] for result in results}), 1)
        self.assertEqual(sum(int(result[3]) for result in results), 1)
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM users").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM customer_auth_identities").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0], 6)

    def test_password_registration_phone_is_canonical_and_unique(self):
        first, _raw, _csrf = self.store.register({
            "name": "Phone Owner", "email": "phone-owner@example.test",
            "password": "long phone owner password 123", "phone": "09876543210",
        })
        self.assertEqual(first["phone"], "+919876543210")
        with self.assertRaises(SECURITY.SecurityError) as duplicate:
            self.store.register({
                "name": "Duplicate Phone", "email": "duplicate-phone@example.test",
                "password": "long duplicate password 123", "phone": "+91 9876543210",
            })
        self.assertEqual((duplicate.exception.status, duplicate.exception.code), (409, "phone_exists"))
        phone_token = self.phone("phone-needs-link", "+919876543210")
        with self.assertRaises(SECURITY.SecurityError) as link_required:
            self.store.federated_session("phone", {"idToken": phone_token})
        self.assertEqual(link_required.exception.code, "account_link_required")
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM users").fetchone()[0], 1)

    def test_linked_mobile_cannot_be_changed_without_new_linking_proof(self):
        token = self.phone("phone-profile", "+919876543210")
        user, _raw, _csrf, _created = self.store.federated_session("phone", {"idToken": token})
        with self.assertRaises(SECURITY.SecurityError) as caught:
            self.store.update_profile(user["id"], {"phone": "+919999999999"})
        self.assertEqual(caught.exception.code, "phone_verification_required")
        self.assertEqual(self.store.profile(user["id"])["phone"], "+919876543210")

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

    def test_identity_migration_aborts_without_mutation_on_duplicate_normalized_phones(self):
        legacy_path = Path(self.temporary.name) / "duplicate-phones.db"
        legacy = sqlite3.connect(legacy_path)
        legacy.executescript(
            """
            CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
            INSERT INTO schema_migrations VALUES(1,'2026-01-01');
            INSERT INTO schema_migrations VALUES(2,'2026-01-01');
            INSERT INTO schema_migrations VALUES(3,'2026-01-01');
            INSERT INTO schema_migrations VALUES(4,'2026-01-01');
            INSERT INTO schema_migrations VALUES(5,'2026-01-01');
            CREATE TABLE users(
              id TEXT PRIMARY KEY, email TEXT, password_hash TEXT, name TEXT NOT NULL, phone TEXT,
              role TEXT NOT NULL DEFAULT 'customer', is_active INTEGER NOT NULL DEFAULT 1,
              email_verified INTEGER NOT NULL DEFAULT 0, email_verified_at TEXT,
              created_at TEXT NOT NULL, updated_at TEXT NOT NULL, password_changed_at TEXT NOT NULL,
              last_login_at TEXT
            );
            INSERT INTO users VALUES('usr_a','a@example.test','hash','A','9876543210','customer',1,0,NULL,'x','x','x',NULL);
            INSERT INTO users VALUES('usr_b','b@example.test','hash','B','+91 9876543210','customer',1,0,NULL,'x','x','x',NULL);
            CREATE TABLE customer_auth_identities(
              id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              provider TEXT NOT NULL CHECK(provider IN ('google','phone')), provider_subject TEXT NOT NULL,
              verified_email TEXT, verified_phone TEXT, created_at TEXT NOT NULL, last_used_at TEXT NOT NULL,
              UNIQUE(provider,provider_subject)
            );
            """
        )
        legacy.commit()
        legacy.close()
        with self.assertRaisesRegex(RuntimeError, "duplicate normalized customer phones"):
            SECURITY.SecurityStore(legacy_path, Fernet.generate_key().decode())
        check = sqlite3.connect(legacy_path)
        columns = {row[1] for row in check.execute("PRAGMA table_info(users)")}
        self.assertNotIn("normalized_phone", columns)
        self.assertEqual(check.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0], 5)
        self.assertEqual(check.execute("SELECT COUNT(*) FROM users").fetchone()[0], 2)
        self.assertEqual(check.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        check.close()
        audit = AUDIT.audit(legacy_path)
        self.assertFalse(audit["safeToMigrate"])
        self.assertEqual(len(audit["duplicateNormalizedPhones"]), 1)
        self.assertNotIn("9876543210", str(audit))

    def test_redacted_identity_audit_accepts_clean_database(self):
        self.store.register({
            "name": "Audit Customer", "email": "audit@example.test",
            "password": "long audit password 123", "phone": "+919876543210",
        })
        audit = AUDIT.audit(self.path)
        self.assertTrue(audit["safeToMigrate"])
        self.assertEqual(audit["databaseIntegrity"], "ok")
        self.assertEqual(audit["foreignKeyViolations"], 0)
        self.assertNotIn("audit@example.test", str(audit))
        self.assertNotIn("+919876543210", str(audit))

    def test_concurrent_security_store_startup_applies_identity_migration_once(self):
        legacy_path = Path(self.temporary.name) / "concurrent-v5.db"
        legacy = sqlite3.connect(legacy_path)
        legacy.executescript(
            """
            CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
            INSERT INTO schema_migrations VALUES(1,'2026-01-01');
            INSERT INTO schema_migrations VALUES(2,'2026-01-01');
            INSERT INTO schema_migrations VALUES(3,'2026-01-01');
            INSERT INTO schema_migrations VALUES(4,'2026-01-01');
            INSERT INTO schema_migrations VALUES(5,'2026-01-01');
            CREATE TABLE users(
              id TEXT PRIMARY KEY, email TEXT, password_hash TEXT, name TEXT NOT NULL, phone TEXT,
              role TEXT NOT NULL DEFAULT 'customer', is_active INTEGER NOT NULL DEFAULT 1,
              email_verified INTEGER NOT NULL DEFAULT 0, email_verified_at TEXT,
              created_at TEXT NOT NULL, updated_at TEXT NOT NULL, password_changed_at TEXT NOT NULL,
              last_login_at TEXT
            );
            INSERT INTO users VALUES(
              'usr_concurrent','Concurrent@Example.Test',NULL,'Concurrent','91 9876543210',
              'customer',1,1,'2026-01-01','x','x','x',NULL
            );
            CREATE TABLE customer_auth_identities(
              id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              provider TEXT NOT NULL CHECK(provider IN ('google','phone')), provider_subject TEXT NOT NULL,
              verified_email TEXT, verified_phone TEXT, created_at TEXT NOT NULL, last_used_at TEXT NOT NULL,
              UNIQUE(provider,provider_subject)
            );
            INSERT INTO customer_auth_identities VALUES(
              'cai_concurrent','usr_concurrent','phone','phone-concurrent-v5',NULL,
              '09876543210','x','x'
            );
            """
        )
        legacy.commit()
        legacy.close()

        barrier = threading.Barrier(2)
        key = Fernet.generate_key().decode()

        def start_store(_index: int):
            barrier.wait()
            return SECURITY.SecurityStore(legacy_path, key)

        with ThreadPoolExecutor(max_workers=2) as pool:
            stores = list(pool.map(start_store, range(2)))
        self.assertEqual(len(stores), 2)
        with stores[0].connect() as db:
            self.assertEqual(
                db.execute("SELECT COUNT(*) FROM schema_migrations WHERE version=6").fetchone()[0],
                1,
            )
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(len(db.execute("PRAGMA foreign_key_check").fetchall()), 0)
            user = db.execute(
                "SELECT normalized_email,normalized_phone FROM users WHERE id='usr_concurrent'"
            ).fetchone()
            self.assertEqual(
                (user["normalized_email"], user["normalized_phone"]),
                ("concurrent@example.test", "+919876543210"),
            )
            index_names = {
                row["name"] for row in db.execute("PRAGMA index_list(users)").fetchall()
            }
            self.assertIn("users_normalized_email_unique_idx", index_names)
            self.assertIn("users_normalized_phone_unique_idx", index_names)


if __name__ == "__main__":
    unittest.main()
