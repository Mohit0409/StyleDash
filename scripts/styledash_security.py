"""Self-hosted StyleDash authentication and authoritative account data."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from cryptography.fernet import Fernet


COOKIE_NAME = "__Host-styledash_session"
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PASSWORD_MIN = 12
PASSWORD_MAX = 256
CUSTOMER_ABSOLUTE_HOURS = 24 * 7
CUSTOMER_IDLE_HOURS = 24
PASSWORD_RESET_MINUTES = 30
PasswordResetDispatcher = Callable[[str, str, Callable[[], None]], None]


class SecurityError(Exception):
    def __init__(self, status: int, message: str, code: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message
        self.code = code


class ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_value, traceback):
        result = super().__exit__(exc_type, exc_value, traceback)
        self.close()
        return result


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime) -> str:
    return value.isoformat()


def token_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_email(value: Any) -> str:
    if not isinstance(value, str):
        raise SecurityError(400, "Enter a valid email address.", "invalid_email")
    email = value.strip().casefold()
    if not 3 <= len(email) <= 254 or not EMAIL_PATTERN.fullmatch(email):
        raise SecurityError(400, "Enter a valid email address.", "invalid_email")
    return email


def clean_text(value: Any, label: str, minimum: int, maximum: int) -> str:
    if not isinstance(value, str):
        raise SecurityError(400, f"Enter a valid {label}.", f"invalid_{label.replace(' ', '_')}")
    cleaned = value.strip()
    if not minimum <= len(cleaned) <= maximum:
        raise SecurityError(400, f"Enter a valid {label}.", f"invalid_{label.replace(' ', '_')}")
    return cleaned


INDIA_MOBILE_PATTERN = re.compile(r"^[6-9]\d{9}$")


def normalize_indian_phone(value: Any) -> str:
    """Normalize an Indian mobile number to E.164 (+91XXXXXXXXXX).

    Only well-known prefixes are stripped explicitly (never a blind digit
    strip) so malformed numbers are rejected rather than silently coerced.
    """
    if not isinstance(value, str):
        raise SecurityError(400, "Enter a valid Indian mobile number.", "invalid_phone")
    condensed = re.sub(r"[\s\-()]", "", value.strip())
    if condensed.startswith("+91"):
        digits = condensed[3:]
    elif condensed.startswith("91") and len(condensed) == 12:
        digits = condensed[2:]
    elif condensed.startswith("0") and len(condensed) == 11:
        digits = condensed[1:]
    else:
        digits = condensed
    if not INDIA_MOBILE_PATTERN.fullmatch(digits):
        raise SecurityError(400, "Enter a valid Indian mobile number.", "invalid_phone")
    return f"+91{digits}"


def firebase_sign_in_provider(claims: dict[str, Any]) -> str:
    """Read Firebase's nested provider claim without trusting its shape."""
    firebase_claims = claims.get("firebase")
    if not isinstance(firebase_claims, dict):
        return ""
    provider = firebase_claims.get("sign_in_provider")
    return provider if isinstance(provider, str) else ""


class SecurityStore:
    """SQLite-backed users, sessions, profiles, vendors, and audit records."""

    def __init__(
        self,
        path: Path,
        encryption_key: str,
        *,
        password_reset_sender: Callable[[str, str], None] | None = None,
        password_reset_dispatcher: PasswordResetDispatcher | None = None,
        firebase_verifier: Callable[[str], dict[str, Any]] | None = None,
    ) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.passwords = PasswordHasher(type=Type.ID)
        # Injected so Google/Phone federated sign-in is fully testable without
        # a real Firebase project or network access.
        self.firebase_verifier = firebase_verifier
        try:
            self.fernet = Fernet(encryption_key.encode("ascii"))
        except Exception as exc:
            raise RuntimeError("Invalid STYLEDASH_TOTP_ENCRYPTION_KEY") from exc
        self.csrf_key = hashlib.sha256(encryption_key.encode("ascii")).digest()
        # Delivery is deliberately injected so the token lifecycle remains
        # testable independently from the private SMTP implementation.
        self.password_reset_sender = password_reset_sender
        self.password_reset_dispatcher = password_reset_dispatcher
        self._migrate()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.path, timeout=5, isolation_level=None, factory=ClosingConnection
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=5000")
        return connection

    def _migrate(self) -> None:
        with self.connect() as db:
            # SQLite's busy timeout is not consistently honored while two
            # processes negotiate journal_mode at the same instant.  Retry
            # only the explicit lock condition within the existing five-
            # second database timeout; all other operational errors surface.
            wal_deadline = time.monotonic() + 5
            while True:
                try:
                    mode = db.execute("PRAGMA journal_mode=WAL").fetchone()[0]
                    break
                except sqlite3.OperationalError as exc:
                    if "locked" not in str(exc).casefold() or time.monotonic() >= wal_deadline:
                        raise
                    time.sleep(0.025)
            if str(mode).lower() != "wal":
                raise RuntimeError("SQLite WAL mode is unavailable")
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations(
                  version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS users(
                  id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL,
                  name TEXT NOT NULL, phone TEXT, role TEXT NOT NULL DEFAULT 'customer'
                    CHECK(role IN ('customer','admin')),
                  is_active INTEGER NOT NULL DEFAULT 1, email_verified INTEGER NOT NULL DEFAULT 0,
                  email_verified_at TEXT,
                  created_at TEXT NOT NULL, updated_at TEXT NOT NULL, password_changed_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions(
                  id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), token_hash TEXT NOT NULL UNIQUE,
                  created_at TEXT NOT NULL, expires_at TEXT NOT NULL, idle_expires_at TEXT NOT NULL,
                  last_seen_at TEXT NOT NULL, revoked_at TEXT, admin_2fa_verified INTEGER NOT NULL DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS sessions_token_idx ON sessions(token_hash);
                CREATE TABLE IF NOT EXISTS login_attempts(
                  id INTEGER PRIMARY KEY AUTOINCREMENT, account_hash TEXT NOT NULL, client_key TEXT NOT NULL,
                  succeeded INTEGER NOT NULL, attempted_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS login_attempts_lookup_idx
                  ON login_attempts(account_hash, client_key, attempted_at);
                CREATE TABLE IF NOT EXISTS user_addresses(
                  id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                  name TEXT NOT NULL, phone TEXT NOT NULL, street TEXT NOT NULL, city TEXT NOT NULL,
                  state TEXT NOT NULL, pincode TEXT NOT NULL, address_type TEXT NOT NULL DEFAULT 'home',
                  is_default INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS vendor_applications(
                  id TEXT PRIMARY KEY, submitted_by_user_id TEXT NOT NULL REFERENCES users(id),
                  shop_name TEXT NOT NULL, owner_name TEXT NOT NULL, email TEXT NOT NULL, phone TEXT NOT NULL,
                  category TEXT NOT NULL, address TEXT NOT NULL, pincode TEXT NOT NULL,
                  description TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending'
                    CHECK(status IN ('pending','approved','rejected')),
                  reviewed_by TEXT REFERENCES users(id), created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS admin_audit_log(
                  id INTEGER PRIMARY KEY AUTOINCREMENT, admin_user_id TEXT REFERENCES users(id),
                  action TEXT NOT NULL, target_type TEXT, target_id TEXT, result TEXT NOT NULL,
                  created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS totp_credentials(
                  user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                  encrypted_secret BLOB NOT NULL, enabled_at TEXT NOT NULL, last_counter INTEGER
                );
                CREATE TABLE IF NOT EXISTS totp_recovery_codes(
                  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                  code_hash TEXT NOT NULL UNIQUE, used_at TEXT
                );
                CREATE TABLE IF NOT EXISTS password_reset_tokens(
                  id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                  token_hash TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL, expires_at TEXT NOT NULL, used_at TEXT
                );
                """
            )
            db.execute(
                "INSERT OR IGNORE INTO schema_migrations(version,applied_at) VALUES(1,?)",
                (iso(utc_now()),),
            )
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS password_reset_tokens(
                  id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                  token_hash TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL, expires_at TEXT NOT NULL, used_at TEXT
                );
                CREATE INDEX IF NOT EXISTS password_reset_tokens_lookup_idx
                  ON password_reset_tokens(token_hash, used_at, expires_at);
                """
            )
            db.execute(
                "INSERT OR IGNORE INTO schema_migrations(version,applied_at) VALUES(2,?)",
                (iso(utc_now()),),
            )
            user_columns = {
                row["name"] for row in db.execute("PRAGMA table_info(users)").fetchall()
            }
            if "email_verified_at" not in user_columns:
                db.execute("ALTER TABLE users ADD COLUMN email_verified_at TEXT")
            db.execute(
                "INSERT OR IGNORE INTO schema_migrations(version,applied_at) VALUES(3,?)",
                (iso(utc_now()),),
            )

            # Migration 4: allow email/password to be optional so Google and
            # phone-only customers can exist without fabricating placeholder
            # credentials. Additive/idempotent: skipped once email is already
            # nullable. Existing rows and IDs are preserved verbatim.
            users_info = db.execute("PRAGMA table_info(users)").fetchall()
            email_notnull = next((row["notnull"] for row in users_info if row["name"] == "email"), 1)
            if email_notnull:
                db.execute("PRAGMA foreign_keys=OFF")
                db.execute("BEGIN IMMEDIATE")
                db.execute(
                    """
                    CREATE TABLE users_new(
                      id TEXT PRIMARY KEY, email TEXT, password_hash TEXT,
                      name TEXT NOT NULL, phone TEXT, role TEXT NOT NULL DEFAULT 'customer'
                        CHECK(role IN ('customer','admin')),
                      is_active INTEGER NOT NULL DEFAULT 1, email_verified INTEGER NOT NULL DEFAULT 0,
                      email_verified_at TEXT,
                      created_at TEXT NOT NULL, updated_at TEXT NOT NULL, password_changed_at TEXT NOT NULL
                    )
                    """
                )
                db.execute(
                    "INSERT INTO users_new(id,email,password_hash,name,phone,role,is_active,email_verified,"
                    "email_verified_at,created_at,updated_at,password_changed_at) "
                    "SELECT id,email,password_hash,name,phone,role,is_active,email_verified,"
                    "email_verified_at,created_at,updated_at,password_changed_at FROM users"
                )
                db.execute("DROP TABLE users")
                db.execute("ALTER TABLE users_new RENAME TO users")
                db.execute("CREATE INDEX IF NOT EXISTS sessions_token_idx ON sessions(token_hash)")
                db.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS users_email_unique_idx ON users(email) WHERE email IS NOT NULL"
                )
                fk_problems = db.execute("PRAGMA foreign_key_check").fetchall()
                if fk_problems:
                    db.rollback()
                    db.execute("PRAGMA foreign_keys=ON")
                    raise RuntimeError("users table migration (nullable email/password) failed foreign key check")
                db.commit()
                db.execute("PRAGMA foreign_keys=ON")
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS customer_auth_identities(
                  id TEXT PRIMARY KEY,
                  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                  provider TEXT NOT NULL CHECK(provider IN ('google','phone')),
                  provider_subject TEXT NOT NULL,
                  verified_email TEXT,
                  verified_phone TEXT,
                  created_at TEXT NOT NULL,
                  last_used_at TEXT NOT NULL,
                  UNIQUE(provider, provider_subject)
                );
                CREATE INDEX IF NOT EXISTS customer_auth_identities_user_idx
                  ON customer_auth_identities(user_id);
                """
            )
            db.execute(
                "INSERT OR IGNORE INTO schema_migrations(version,applied_at) VALUES(4,?)",
                (iso(utc_now()),),
            )
            user_columns = {
                row["name"] for row in db.execute("PRAGMA table_info(users)").fetchall()
            }
            if "last_login_at" not in user_columns:
                db.execute("ALTER TABLE users ADD COLUMN last_login_at TEXT")
            db.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS users_email_unique_idx ON users(email) WHERE email IS NOT NULL"
            )
            db.execute(
                "INSERT OR IGNORE INTO schema_migrations(version,applied_at) VALUES(5,?)",
                (iso(utc_now()),),
            )

            # Migration 6: persist canonical identity keys and enforce them at
            # the database boundary.  The preflight deliberately fails rather
            # than guessing how to merge legacy customers.  Because the whole
            # migration is transactional, a conflict leaves the v5 schema and
            # every customer row unchanged for manual remediation.
            migration_versions = {
                row["version"] for row in db.execute("SELECT version FROM schema_migrations")
            }
            if 6 not in migration_versions:
                db.execute("BEGIN IMMEDIATE")
                # Public and private services start independently against the
                # same SQLite file.  Another process may have completed v6
                # while this connection waited for the write lock, so the
                # authoritative version check must happen after BEGIN
                # IMMEDIATE, not only before it.
                if db.execute(
                    "SELECT 1 FROM schema_migrations WHERE version=6"
                ).fetchone():
                    db.rollback()
                    self._secure_files()
                    return
                users = db.execute("SELECT id,email,phone FROM users").fetchall()
                normalized_users: dict[str, tuple[str | None, str | None]] = {}
                email_owners: dict[str, str] = {}
                phone_owners: dict[str, str] = {}
                try:
                    for user in users:
                        normalized_email = normalize_email(user["email"]) if user["email"] is not None else None
                        normalized_phone = normalize_indian_phone(user["phone"]) if user["phone"] else None
                        if normalized_email is not None:
                            owner = email_owners.setdefault(normalized_email, user["id"])
                            if owner != user["id"]:
                                raise RuntimeError("duplicate normalized customer emails require remediation")
                        if normalized_phone is not None:
                            owner = phone_owners.setdefault(normalized_phone, user["id"])
                            if owner != user["id"]:
                                raise RuntimeError("duplicate normalized customer phones require remediation")
                        normalized_users[user["id"]] = (normalized_email, normalized_phone)

                    identity_emails: dict[str, str] = {}
                    identity_phones: dict[str, str] = {}
                    canonical_identities: list[tuple[str | None, str | None, str]] = []
                    identities = db.execute(
                        "SELECT id,user_id,provider,verified_email,verified_phone FROM customer_auth_identities"
                    ).fetchall()
                    for identity in identities:
                        verified_email = None
                        verified_phone = None
                        if identity["provider"] == "google":
                            verified_email = normalize_email(identity["verified_email"])
                            existing_identity = identity_emails.setdefault(verified_email, identity["id"])
                            if existing_identity != identity["id"]:
                                raise RuntimeError("conflicting Google email identities require remediation")
                            user_email = email_owners.get(verified_email)
                            if user_email is not None and user_email != identity["user_id"]:
                                raise RuntimeError("Google identity conflicts with another customer email")
                        elif identity["provider"] == "phone":
                            verified_phone = normalize_indian_phone(identity["verified_phone"])
                            existing_identity = identity_phones.setdefault(verified_phone, identity["id"])
                            if existing_identity != identity["id"]:
                                raise RuntimeError("conflicting mobile identities require remediation")
                            user_phone = phone_owners.get(verified_phone)
                            if user_phone is not None and user_phone != identity["user_id"]:
                                raise RuntimeError("mobile identity conflicts with another customer phone")
                            current_email, current_phone = normalized_users[identity["user_id"]]
                            if current_phone is None:
                                normalized_users[identity["user_id"]] = (current_email, verified_phone)
                                phone_owners[verified_phone] = identity["user_id"]
                            elif current_phone != verified_phone:
                                raise RuntimeError("customer mobile identity does not match the customer phone")
                        canonical_identities.append((verified_email, verified_phone, identity["id"]))
                except SecurityError as exc:
                    raise RuntimeError("invalid legacy customer identity requires remediation") from exc

                user_columns = {
                    row["name"] for row in db.execute("PRAGMA table_info(users)").fetchall()
                }
                if "normalized_email" not in user_columns:
                    db.execute("ALTER TABLE users ADD COLUMN normalized_email TEXT")
                if "normalized_phone" not in user_columns:
                    db.execute("ALTER TABLE users ADD COLUMN normalized_phone TEXT")
                for user_id, (normalized_email, normalized_phone) in normalized_users.items():
                    db.execute(
                        "UPDATE users SET email=COALESCE(?,email),phone=COALESCE(?,phone),"
                        "normalized_email=?,normalized_phone=? WHERE id=?",
                        (normalized_email, normalized_phone, normalized_email, normalized_phone, user_id),
                    )
                for verified_email, verified_phone, identity_id in canonical_identities:
                    db.execute(
                        "UPDATE customer_auth_identities SET verified_email=?,verified_phone=? WHERE id=?",
                        (verified_email, verified_phone, identity_id),
                    )
                db.execute(
                    "CREATE UNIQUE INDEX users_normalized_email_unique_idx "
                    "ON users(normalized_email) WHERE normalized_email IS NOT NULL"
                )
                db.execute(
                    "CREATE UNIQUE INDEX users_normalized_phone_unique_idx "
                    "ON users(normalized_phone) WHERE normalized_phone IS NOT NULL"
                )
                db.execute(
                    "CREATE UNIQUE INDEX customer_auth_phone_unique_idx "
                    "ON customer_auth_identities(verified_phone) "
                    "WHERE provider='phone' AND verified_phone IS NOT NULL"
                )
                db.execute(
                    "CREATE UNIQUE INDEX customer_auth_google_email_unique_idx "
                    "ON customer_auth_identities(verified_email) "
                    "WHERE provider='google' AND verified_email IS NOT NULL"
                )
                db.execute(
                    "INSERT INTO schema_migrations(version,applied_at) VALUES(6,?)",
                    (iso(utc_now()),),
                )
                if db.execute("PRAGMA foreign_key_check").fetchall():
                    raise RuntimeError("identity uniqueness migration failed foreign key check")
                db.commit()
        self._secure_files()

    def _secure_files(self) -> None:
        for candidate in (self.path, Path(str(self.path) + "-wal"), Path(str(self.path) + "-shm")):
            if candidate.exists():
                candidate.chmod(0o600)

    @staticmethod
    def safe_user(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"], "uid": row["id"], "email": row["email"], "name": row["name"],
            "phone": row["phone"], "role": row["role"],
            "emailVerified": bool(row["email_verified_at"]),
            "hasPassword": bool(row["password_hash"]),
        }

    def _new_session(self, db: sqlite3.Connection, user: sqlite3.Row) -> tuple[str, str]:
        raw = secrets.token_urlsafe(48)
        now = utc_now()
        absolute = now + timedelta(hours=CUSTOMER_ABSOLUTE_HOURS)
        idle = now + timedelta(hours=CUSTOMER_IDLE_HOURS)
        db.execute(
            "INSERT INTO sessions(id,user_id,token_hash,created_at,expires_at,idle_expires_at,last_seen_at,admin_2fa_verified) VALUES(?,?,?,?,?,?,?,?)",
            (secrets.token_hex(16), user["id"], token_hash(raw), iso(now), iso(absolute), iso(idle), iso(now), 0),
        )
        db.execute("UPDATE users SET last_login_at=? WHERE id=?", (iso(now), user["id"]))
        return raw, self.csrf_token(raw)

    def csrf_token(self, raw_session: str) -> str:
        return hmac.new(self.csrf_key, raw_session.encode("utf-8"), hashlib.sha256).hexdigest()

    @staticmethod
    def cookie(raw_session: str, max_age: int = CUSTOMER_ABSOLUTE_HOURS * 3600) -> str:
        return f"{COOKIE_NAME}={raw_session}; Path=/; Max-Age={max_age}; HttpOnly; Secure; SameSite=Lax"

    @staticmethod
    def clear_cookie() -> str:
        return f"{COOKIE_NAME}=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Lax"

    def register(self, payload: dict[str, Any]) -> tuple[dict[str, Any], str, str]:
        if any(field in payload for field in (
            "role", "isAdmin", "admin", "emailVerified", "email_verified",
            "emailVerifiedAt", "email_verified_at",
        )):
            raise SecurityError(400, "Unsupported registration field.", "invalid_registration")
        email = normalize_email(payload.get("email"))
        password = payload.get("password")
        if not isinstance(password, str) or not PASSWORD_MIN <= len(password) <= PASSWORD_MAX:
            raise SecurityError(400, f"Password must be {PASSWORD_MIN}–{PASSWORD_MAX} characters.", "weak_password")
        name = clean_text(payload.get("name"), "name", 2, 80)
        phone_value = payload.get("phone")
        phone = normalize_indian_phone(phone_value) if phone_value else None
        now = iso(utc_now())
        user_id = "usr_" + secrets.token_hex(12)
        encoded = self.passwords.hash(password)
        with self.connect() as db:
            try:
                db.execute("BEGIN IMMEDIATE")
                if db.execute(
                    "SELECT 1 FROM users WHERE normalized_email=?", (email,)
                ).fetchone():
                    raise SecurityError(409, "An account with this email already exists.", "email_exists")
                if db.execute(
                    "SELECT 1 FROM customer_auth_identities "
                    "WHERE provider='google' AND verified_email=?",
                    (email,),
                ).fetchone():
                    raise SecurityError(409, "An account with this email already exists.", "email_exists")
                if phone and db.execute(
                    "SELECT 1 FROM users WHERE normalized_phone=?", (phone,)
                ).fetchone():
                    raise SecurityError(409, "An account with this mobile number already exists.", "phone_exists")
                db.execute(
                    "INSERT INTO users(id,email,normalized_email,password_hash,name,phone,normalized_phone,"
                    "created_at,updated_at,password_changed_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (user_id, email, email, encoded, name, phone, phone, now, now, now),
                )
                user = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
                raw, csrf = self._new_session(db, user)
                db.commit()
            except SecurityError:
                db.rollback()
                raise
            except sqlite3.IntegrityError:
                db.rollback()
                raise SecurityError(409, "An account with these details already exists.", "identity_exists") from None
        self._secure_files()
        return self.safe_user(user), raw, csrf

    def login(self, payload: dict[str, Any], client_key: str) -> tuple[dict[str, Any], str, str]:
        email = normalize_email(payload.get("email"))
        password = payload.get("password")
        if not isinstance(password, str) or len(password) > PASSWORD_MAX:
            raise SecurityError(401, "Invalid email or password.", "invalid_credentials")
        account = token_hash(email)
        cutoff = iso(utc_now() - timedelta(minutes=15))
        with self.connect() as db:
            failures = db.execute(
                "SELECT COUNT(*) FROM login_attempts WHERE succeeded=0 AND attempted_at>=? AND (account_hash=? OR client_key=?)",
                (cutoff, account, client_key),
            ).fetchone()[0]
            if failures >= 8:
                raise SecurityError(429, "Too many login attempts. Please wait and try again.", "login_rate_limited")
            user = db.execute("SELECT * FROM users WHERE normalized_email=?", (email,)).fetchone()
            valid = False
            if user is not None and user["is_active"] and user["role"] == "customer" and user["password_hash"]:
                try:
                    valid = self.passwords.verify(user["password_hash"], password)
                except (VerifyMismatchError, InvalidHashError):
                    valid = False
            db.execute(
                "INSERT INTO login_attempts(account_hash,client_key,succeeded,attempted_at) VALUES(?,?,?,?)",
                (account, client_key, int(valid), iso(utc_now())),
            )
            if not valid:
                raise SecurityError(401, "Invalid email or password.", "invalid_credentials")
            raw, csrf = self._new_session(db, user)
        return self.safe_user(user), raw, csrf

    def authenticate(self, raw_session: str | None) -> tuple[dict[str, Any], sqlite3.Row]:
        if not raw_session:
            raise SecurityError(401, "Authentication required.", "authentication_required")
        now = utc_now()
        with self.connect() as db:
            row = db.execute(
                "SELECT s.*,u.id AS authenticated_user_id,u.email,u.name,u.phone,u.role,u.is_active,u.email_verified,u.email_verified_at,u.password_hash FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=?",
                (token_hash(raw_session),),
            ).fetchone()
            if row is None or row["revoked_at"] or not row["is_active"] or row["role"] != "customer":
                raise SecurityError(401, "Authentication required.", "authentication_required")
            if datetime.fromisoformat(row["expires_at"]) <= now or datetime.fromisoformat(row["idle_expires_at"]) <= now:
                db.execute("UPDATE sessions SET revoked_at=? WHERE id=?", (iso(now), row["id"]))
                raise SecurityError(401, "Your session has expired.", "session_expired")
            db.execute(
                "UPDATE sessions SET last_seen_at=?,idle_expires_at=? WHERE id=?",
                (iso(now), iso(now + timedelta(hours=CUSTOMER_IDLE_HOURS)), row["id"]),
            )
        user = {
            "id": row["authenticated_user_id"], "uid": row["authenticated_user_id"],
            "email": row["email"], "name": row["name"], "phone": row["phone"],
            "role": row["role"], "emailVerified": bool(row["email_verified_at"]),
            "hasPassword": bool(row["password_hash"]),
        }
        return user, row

    def revoke(self, raw_session: str) -> None:
        with self.connect() as db:
            db.execute("UPDATE sessions SET revoked_at=? WHERE token_hash=?", (iso(utc_now()), token_hash(raw_session)))

    def federated_session(
        self, provider: str, payload: dict[str, Any]
    ) -> tuple[dict[str, Any], str, str, bool]:
        """Exchange a verified Firebase ID token for a normal StyleDash session.

        Firebase is used only to cryptographically prove a Google or phone
        identity. Nothing from the request body is trusted; every claim used
        below comes from the verified token, never from ``payload`` directly.
        Returns (safe_user, raw_session, csrf_token, created).
        """
        if provider not in ("google", "phone"):
            raise SecurityError(400, "Unsupported sign-in method.", "invalid_provider")
        id_token = payload.get("idToken")
        if not isinstance(id_token, str) or not 20 <= len(id_token) <= 4096:
            raise SecurityError(400, "A valid identity token is required.", "invalid_token")
        verifier = self.firebase_verifier
        if verifier is None:
            try:
                from styledash_firebase import verify_firebase_id_token as verifier  # type: ignore[assignment]
            except ImportError:
                from scripts.styledash_firebase import verify_firebase_id_token as verifier  # type: ignore[assignment]
        try:
            claims = verifier(id_token)
        except Exception:
            # Never surface Firebase's internal exception (expired/invalid
            # signature/revoked/wrong project) — a single generic error
            # avoids leaking which case applies.
            raise SecurityError(401, "Unable to complete sign in. Please try again.", "identity_verification_failed") from None
        if not isinstance(claims, dict):
            raise SecurityError(401, "Unable to complete sign in. Please try again.", "identity_verification_failed")
        sign_in_provider = firebase_sign_in_provider(claims)
        expected_provider = "google.com" if provider == "google" else "phone"
        if sign_in_provider != expected_provider:
            raise SecurityError(401, "Unable to complete sign in. Please try again.", "identity_verification_failed")
        uid = claims.get("uid") or claims.get("sub")
        if not isinstance(uid, str) or not uid:
            raise SecurityError(401, "Unable to complete sign in. Please try again.", "identity_verification_failed")
        verified_phone_claim = None
        if provider == "phone":
            try:
                verified_phone_claim = normalize_indian_phone(claims.get("phone_number"))
            except SecurityError:
                raise SecurityError(400, "Unable to complete sign in with mobile.", "phone_required") from None
        now = iso(utc_now())
        try:
            with self.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                identity = db.execute(
                    "SELECT * FROM customer_auth_identities WHERE provider=? AND provider_subject=?",
                    (provider, uid),
                ).fetchone()
                created = False
                if identity is not None:
                    user = db.execute("SELECT * FROM users WHERE id=?", (identity["user_id"],)).fetchone()
                    if user is None or not user["is_active"] or user["role"] != "customer":
                        raise SecurityError(401, "Unable to complete sign in. Please try again.", "identity_verification_failed")
                    if provider == "phone" and identity["verified_phone"] != verified_phone_claim:
                        phone_identity = db.execute(
                            "SELECT user_id FROM customer_auth_identities "
                            "WHERE provider='phone' AND verified_phone=? AND id<>?",
                            (verified_phone_claim, identity["id"]),
                        ).fetchone()
                        phone_owner = db.execute(
                            "SELECT id FROM users WHERE normalized_phone=? AND id<>?",
                            (verified_phone_claim, user["id"]),
                        ).fetchone()
                        if phone_identity is not None or phone_owner is not None:
                            raise SecurityError(
                                409,
                                "This mobile number is already linked.",
                                "identity_already_linked",
                            )
                        db.execute(
                            "UPDATE customer_auth_identities SET verified_phone=? WHERE id=?",
                            (verified_phone_claim, identity["id"]),
                        )
                        db.execute(
                            "UPDATE users SET phone=?,normalized_phone=?,updated_at=? WHERE id=?",
                            (verified_phone_claim, verified_phone_claim, now, user["id"]),
                        )
                        user = db.execute("SELECT * FROM users WHERE id=?", (user["id"],)).fetchone()
                    db.execute(
                        "UPDATE customer_auth_identities SET last_used_at=? WHERE id=?", (now, identity["id"])
                    )
                elif provider == "google":
                    user, created = self._google_identity(db, uid, claims, now)
                else:
                    user, created = self._phone_identity(db, uid, claims, now)
                raw, csrf = self._new_session(db, user)
                db.commit()
        except sqlite3.IntegrityError:
            raise SecurityError(401, "Unable to complete sign in. Please try again.", "identity_verification_failed") from None
        self._secure_files()
        result = self.safe_user(user)
        result["needsProfile"] = provider == "phone" and not user["name"]
        return result, raw, csrf, created

    def link_federated_identity(
        self, raw_session: str, provider: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Link a verified external identity to the authenticated customer."""
        current, _session = self.authenticate(raw_session)
        if provider not in ("google", "phone"):
            raise SecurityError(400, "Unsupported sign-in method.", "invalid_provider")
        id_token = payload.get("idToken")
        if not isinstance(id_token, str) or not 20 <= len(id_token) <= 4096:
            raise SecurityError(400, "A valid identity token is required.", "invalid_token")
        verifier = self.firebase_verifier
        if verifier is None:
            try:
                from styledash_firebase import verify_firebase_id_token as verifier  # type: ignore[assignment]
            except ImportError:
                from scripts.styledash_firebase import verify_firebase_id_token as verifier  # type: ignore[assignment]
        try:
            claims = verifier(id_token)
        except Exception:
            raise SecurityError(401, "Unable to complete sign in. Please try again.", "identity_verification_failed") from None
        expected_provider = "google.com" if provider == "google" else "phone"
        if not isinstance(claims, dict) or firebase_sign_in_provider(claims) != expected_provider:
            raise SecurityError(401, "Unable to complete sign in. Please try again.", "identity_verification_failed")
        uid = claims.get("uid") or claims.get("sub")
        if not isinstance(uid, str) or not uid:
            raise SecurityError(401, "Unable to complete sign in. Please try again.", "identity_verification_failed")
        verified_email = None
        verified_phone = None
        if provider == "google":
            if claims.get("email_verified") is not True or not isinstance(claims.get("email"), str) or not claims.get("email"):
                raise SecurityError(400, "Unable to link Google securely.", "google_email_required")
            verified_email = normalize_email(claims["email"])
        else:
            try:
                verified_phone = normalize_indian_phone(claims.get("phone_number"))
            except SecurityError:
                raise SecurityError(400, "Unable to link mobile securely.", "phone_required") from None
        now = iso(utc_now())
        with self.connect() as db:
            try:
                db.execute("BEGIN IMMEDIATE")
                subject_identity = db.execute(
                    "SELECT * FROM customer_auth_identities WHERE provider=? AND provider_subject=?",
                    (provider, uid),
                ).fetchone()
                if subject_identity and subject_identity["user_id"] != current["id"]:
                    raise SecurityError(409, "This identity is already linked.", "identity_already_linked")
                if provider == "google":
                    email_owner = db.execute(
                        "SELECT id FROM users WHERE normalized_email=?", (verified_email,)
                    ).fetchone()
                    if email_owner and email_owner["id"] != current["id"]:
                        raise SecurityError(
                            409,
                            "An account already uses this email. Sign in to that account before linking Google.",
                            "account_link_required",
                        )
                    matching_identity = db.execute(
                        "SELECT * FROM customer_auth_identities "
                        "WHERE provider='google' AND verified_email=?",
                        (verified_email,),
                    ).fetchone()
                else:
                    phone_owner = db.execute(
                        "SELECT id FROM users WHERE normalized_phone=?", (verified_phone,)
                    ).fetchone()
                    if phone_owner and phone_owner["id"] != current["id"]:
                        raise SecurityError(
                            409,
                            "An account already uses this mobile number. Sign in to that account before linking it.",
                            "account_link_required",
                        )
                    matching_identity = db.execute(
                        "SELECT * FROM customer_auth_identities "
                        "WHERE provider='phone' AND verified_phone=?",
                        (verified_phone,),
                    ).fetchone()
                if matching_identity and (
                    matching_identity["user_id"] != current["id"]
                    or matching_identity["provider_subject"] != uid
                ):
                    raise SecurityError(409, "This identity is already linked.", "identity_already_linked")
                if subject_identity is None:
                    db.execute(
                        "INSERT INTO customer_auth_identities(id,user_id,provider,provider_subject,"
                        "verified_email,verified_phone,created_at,last_used_at) VALUES(?,?,?,?,?,?,?,?)",
                        (
                            "cai_" + secrets.token_hex(12), current["id"], provider, uid,
                            verified_email, verified_phone, now, now,
                        ),
                    )
                else:
                    db.execute(
                        "UPDATE customer_auth_identities SET verified_email=?,verified_phone=?,last_used_at=? "
                        "WHERE id=?",
                        (verified_email, verified_phone, now, subject_identity["id"]),
                    )
                if provider == "google":
                    db.execute(
                        "UPDATE users SET email=COALESCE(email,?),normalized_email=COALESCE(normalized_email,?),"
                        "email_verified=CASE WHEN normalized_email IS NULL OR normalized_email=? THEN 1 ELSE email_verified END,"
                        "email_verified_at=CASE WHEN normalized_email IS NULL OR normalized_email=? "
                        "THEN COALESCE(email_verified_at,?) ELSE email_verified_at END,updated_at=? WHERE id=?",
                        (verified_email, verified_email, verified_email, verified_email, now, now, current["id"]),
                    )
                else:
                    db.execute(
                        "UPDATE users SET phone=?,normalized_phone=?,updated_at=? WHERE id=?",
                        (verified_phone, verified_phone, now, current["id"]),
                    )
                db.commit()
            except SecurityError:
                db.rollback()
                raise
            except sqlite3.IntegrityError:
                db.rollback()
                raise SecurityError(409, "This identity is already linked.", "identity_already_linked") from None
        return self.profile(current["id"])

    def _google_identity(
        self, db: sqlite3.Connection, uid: str, claims: dict[str, Any], now: str
    ) -> tuple[sqlite3.Row, bool]:
        if claims.get("email_verified") is not True or not isinstance(claims.get("email"), str) or not claims.get("email"):
            raise SecurityError(400, "Unable to complete sign in with Google.", "google_email_required")
        email = normalize_email(claims["email"])
        existing = db.execute("SELECT * FROM users WHERE normalized_email=?", (email,)).fetchone()
        created = False
        if existing is not None:
            if not existing["is_active"] or existing["role"] != "customer":
                raise SecurityError(401, "Unable to complete sign in. Please try again.", "identity_verification_failed")
            raise SecurityError(
                409,
                "An account already uses this email. Sign in to that account and link Google securely.",
                "account_link_required",
            )
        existing_identity = db.execute(
            "SELECT 1 FROM customer_auth_identities WHERE provider='google' AND verified_email=?",
            (email,),
        ).fetchone()
        if existing_identity is not None:
            raise SecurityError(
                409,
                "An account already uses this email. Sign in to that account and link Google securely.",
                "account_link_required",
            )
        raw_name = claims.get("name")
        name = clean_text(raw_name, "name", 1, 80) if isinstance(raw_name, str) and raw_name.strip() else email.split("@", 1)[0][:80]
        user_id = "usr_" + secrets.token_hex(12)
        db.execute(
            "INSERT INTO users(id,email,normalized_email,password_hash,name,phone,normalized_phone,"
            "created_at,updated_at,password_changed_at,email_verified,email_verified_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,1,?)",
            (user_id, email, email, None, name, None, None, now, now, now, now),
        )
        created = True
        db.execute(
            "INSERT INTO customer_auth_identities(id,user_id,provider,provider_subject,verified_email,created_at,last_used_at) "
            "VALUES(?,?,?,?,?,?,?)",
            ("cai_" + secrets.token_hex(12), user_id, "google", uid, email, now, now),
        )
        user = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        return user, created

    def _phone_identity(
        self, db: sqlite3.Connection, uid: str, claims: dict[str, Any], now: str
    ) -> tuple[sqlite3.Row, bool]:
        raw_phone = claims.get("phone_number")
        if not isinstance(raw_phone, str) or not raw_phone:
            raise SecurityError(400, "Unable to complete sign in with mobile.", "phone_required")
        try:
            phone = normalize_indian_phone(raw_phone)
        except SecurityError:
            raise SecurityError(400, "Unable to complete sign in with mobile.", "phone_required") from None
        existing = db.execute(
            "SELECT * FROM customer_auth_identities WHERE provider='phone' AND verified_phone=?",
            (phone,),
        ).fetchone()
        if existing is not None:
            user = db.execute("SELECT * FROM users WHERE id=?", (existing["user_id"],)).fetchone()
            if user is None or not user["is_active"] or user["role"] != "customer":
                raise SecurityError(401, "Unable to complete sign in. Please try again.", "identity_verification_failed")
            # Firebase OTP proves control of the canonical number.  If
            # Firebase has issued a replacement UID for the same number,
            # rotate the provider subject on the one existing identity rather
            # than rejecting the customer or creating a duplicate user.
            db.execute(
                "UPDATE customer_auth_identities SET provider_subject=?,last_used_at=? WHERE id=?",
                (uid, now, existing["id"]),
            )
            return user, False
        phone_owner = db.execute(
            "SELECT id FROM users WHERE normalized_phone=?", (phone,)
        ).fetchone()
        if phone_owner is not None:
            raise SecurityError(
                409,
                "An account already uses this mobile number. Sign in to that account and link mobile securely.",
                "account_link_required",
            )
        # A password account with this canonical phone is never auto-linked:
        # the caller must authenticate that account and use the explicit link
        # endpoint, proving control of both the StyleDash session and OTP.
        user_id = "usr_" + secrets.token_hex(12)
        db.execute(
            "INSERT INTO users(id,email,normalized_email,password_hash,name,phone,normalized_phone,"
            "created_at,updated_at,password_changed_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (user_id, None, None, None, "", phone, phone, now, now, now),
        )
        db.execute(
            "INSERT INTO customer_auth_identities(id,user_id,provider,provider_subject,verified_phone,created_at,last_used_at) "
            "VALUES(?,?,?,?,?,?,?)",
            ("cai_" + secrets.token_hex(12), user_id, "phone", uid, phone, now, now),
        )
        user = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        return user, True

    def verify_csrf(self, raw_session: str | None, supplied: str | None) -> None:
        if not raw_session or not supplied or not hmac.compare_digest(self.csrf_token(raw_session), supplied):
            raise SecurityError(403, "CSRF verification failed.", "csrf_failed")

    def change_password(self, raw_session: str, payload: dict[str, Any]) -> tuple[str, str]:
        user, session = self.authenticate(raw_session)
        current = payload.get("currentPassword")
        new = payload.get("newPassword")
        if not isinstance(current, str) or not isinstance(new, str) or not PASSWORD_MIN <= len(new) <= PASSWORD_MAX:
            raise SecurityError(400, "Invalid password change request.", "invalid_password_change")
        with self.connect() as db:
            row = db.execute("SELECT * FROM users WHERE id=?", (user["id"],)).fetchone()
            if row is None or not isinstance(row["password_hash"], str) or not row["password_hash"]:
                raise SecurityError(
                    409,
                    "This account does not have a password. Use its linked sign-in method.",
                    "password_not_set",
                )
            try:
                self.passwords.verify(row["password_hash"], current)
            except (VerifyMismatchError, InvalidHashError):
                raise SecurityError(401, "Current password is incorrect.", "invalid_credentials") from None
            now = iso(utc_now())
            db.execute("BEGIN IMMEDIATE")
            db.execute("UPDATE users SET password_hash=?,password_changed_at=?,updated_at=? WHERE id=?", (self.passwords.hash(new), now, now, user["id"]))
            db.execute("UPDATE sessions SET revoked_at=? WHERE user_id=?", (now, user["id"]))
            refreshed = db.execute("SELECT * FROM users WHERE id=?", (user["id"],)).fetchone()
            new_raw, csrf = self._new_session(db, refreshed)
            db.commit()
        return new_raw, csrf

    def request_password_reset(self, payload: dict[str, Any]) -> None:
        """Create a reset token only when a trusted delivery boundary exists.

        Callers always return the same public response for known and unknown
        accounts.  Raw tokens exist only in this stack frame and the injected
        sender; SQLite stores a SHA-256 hash exclusively.
        """
        try:
            email = normalize_email(payload.get("email"))
        except SecurityError:
            return
        if self.password_reset_sender is None and self.password_reset_dispatcher is None:
            return
        raw_token: str | None = None
        reset_id: str | None = None
        with self.connect() as db:
            user = db.execute(
                "SELECT id,email FROM users WHERE normalized_email=? AND is_active=1 AND role='customer' AND password_hash IS NOT NULL",
                (email,),
            ).fetchone()
            if user is None:
                return
            now = utc_now()
            now_value = iso(now)
            raw_token = secrets.token_urlsafe(48)
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "UPDATE password_reset_tokens SET used_at=? WHERE user_id=? AND used_at IS NULL",
                (now_value, user["id"]),
            )
            reset_id = "reset_" + secrets.token_hex(16)
            db.execute(
                "INSERT INTO password_reset_tokens(id,user_id,token_hash,created_at,expires_at) VALUES(?,?,?,?,?)",
                (
                    reset_id, user["id"], token_hash(raw_token), now_value,
                    iso(now + timedelta(minutes=PASSWORD_RESET_MINUTES)),
                ),
            )
            db.commit()
        assert raw_token is not None and reset_id is not None

        def invalidate_delivery_failure() -> None:
            # Do not leave a usable token behind when delivery fails. The
            # public response remains generic and no token/configuration is
            # logged or exposed.
            with self.connect() as db:
                db.execute("UPDATE password_reset_tokens SET used_at=? WHERE id=? AND used_at IS NULL", (iso(utc_now()), reset_id))

        try:
            if self.password_reset_dispatcher is not None:
                self.password_reset_dispatcher(email, raw_token, invalidate_delivery_failure)
            else:
                assert self.password_reset_sender is not None
                self.password_reset_sender(email, raw_token)
        except Exception:
            invalidate_delivery_failure()
        self._secure_files()

    def confirm_password_reset(self, payload: dict[str, Any]) -> None:
        raw_token = payload.get("token")
        new_password = payload.get("newPassword")
        if not isinstance(new_password, str) or not PASSWORD_MIN <= len(new_password) <= PASSWORD_MAX:
            raise SecurityError(400, f"Password must be {PASSWORD_MIN}–{PASSWORD_MAX} characters.", "weak_password")
        if not isinstance(raw_token, str) or not 32 <= len(raw_token) <= 256:
            raise SecurityError(400, "This password reset link is invalid or has expired.", "invalid_reset_token")
        now = utc_now()
        now_value = iso(now)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            reset = db.execute(
                """SELECT r.id,r.user_id,u.is_active,u.role FROM password_reset_tokens r
                   JOIN users u ON u.id=r.user_id
                   WHERE r.token_hash=? AND r.used_at IS NULL AND r.expires_at>?""",
                (token_hash(raw_token), now_value),
            ).fetchone()
            if reset is None or not reset["is_active"] or reset["role"] != "customer":
                if reset is not None:
                    db.execute("UPDATE password_reset_tokens SET used_at=? WHERE id=? AND used_at IS NULL", (now_value, reset["id"]))
                    db.commit()
                else:
                    db.rollback()
                raise SecurityError(400, "This password reset link is invalid or has expired.", "invalid_reset_token")
            consumed = db.execute(
                "UPDATE password_reset_tokens SET used_at=? WHERE id=? AND used_at IS NULL",
                (now_value, reset["id"]),
            )
            if consumed.rowcount != 1:
                db.rollback()
                raise SecurityError(400, "This password reset link is invalid or has expired.", "invalid_reset_token")
            db.execute(
                "UPDATE password_reset_tokens SET used_at=? WHERE user_id=? AND used_at IS NULL",
                (now_value, reset["user_id"]),
            )
            db.execute(
                """UPDATE users
                   SET password_hash=?,password_changed_at=?,updated_at=?,
                       email_verified=1,email_verified_at=COALESCE(email_verified_at,?)
                   WHERE id=?""",
                (
                    self.passwords.hash(new_password), now_value, now_value,
                    now_value, reset["user_id"],
                ),
            )
            db.execute("UPDATE sessions SET revoked_at=? WHERE user_id=? AND revoked_at IS NULL", (now_value, reset["user_id"]))
            db.commit()
        self._secure_files()

    def list_orders(self, payment_store: Any, user_id: str) -> list[dict[str, Any]]:
        with payment_store.lock:
            orders = list(payment_store.state["orders"].values())
            orders = [order for order in orders if order.get("userId") == user_id]
            return [dict(order) for order in sorted(orders, key=lambda order: order.get("createdAt", ""), reverse=True)]

    def get_order(self, payment_store: Any, order_id: str, user_id: str) -> dict[str, Any]:
        with payment_store.lock:
            order = payment_store.state["orders"].get(order_id)
            if order is None or order.get("userId") != user_id:
                raise SecurityError(404, "Order not found.", "order_not_found")
            return dict(order)

    def create_vendor_application(self, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        allowed_categories = {"Clothing & Fashion", "Footwear", "Electronics", "Home & Living", "General Store"}
        category = payload.get("category")
        if category not in allowed_categories:
            raise SecurityError(400, "Invalid store category.", "invalid_vendor_application")
        values = {
            "shop_name": clean_text(payload.get("storeName"), "store name", 2, 100),
            "owner_name": clean_text(payload.get("ownerName"), "owner name", 2, 80),
            "email": normalize_email(payload.get("email")),
            "phone": clean_text(payload.get("phone"), "phone", 10, 20),
            "address": clean_text(payload.get("address"), "address", 5, 250),
            "pincode": clean_text(payload.get("pincode"), "pincode", 6, 6),
            "description": clean_text(payload.get("description"), "description", 10, 1000),
        }
        application_id = "vendor_" + secrets.token_hex(12)
        now = iso(utc_now())
        with self.connect() as db:
            db.execute(
                "INSERT INTO vendor_applications(id,submitted_by_user_id,shop_name,owner_name,email,phone,category,address,pincode,description,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (application_id, user_id, values["shop_name"], values["owner_name"], values["email"], values["phone"], category, values["address"], values["pincode"], values["description"], now, now),
            )
        return {"id": application_id, "status": "pending", "createdAt": now}

    def list_vendor_applications(self) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute("SELECT * FROM vendor_applications ORDER BY created_at DESC").fetchall()
        return [{key: row[key] for key in row.keys()} for row in rows]

    def profile(self, user_id: str) -> dict[str, Any]:
        with self.connect() as db:
            user = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
            if user is None:
                raise SecurityError(404, "Profile not found.", "profile_not_found")
            addresses = db.execute("SELECT * FROM user_addresses WHERE user_id=? ORDER BY is_default DESC,created_at", (user_id,)).fetchall()
        result = self.safe_user(user)
        result["addresses"] = [{
            "id": row["id"], "name": row["name"], "phone": row["phone"], "street": row["street"],
            "city": row["city"], "state": row["state"], "pincode": row["pincode"],
            "type": row["address_type"], "isDefault": bool(row["is_default"]),
        } for row in addresses]
        return result

    def update_profile(self, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        forbidden = {
            "id", "uid", "role", "password_hash", "is_active", "email",
            "emailVerified", "email_verified", "emailVerifiedAt", "email_verified_at",
        }
        if forbidden.intersection(payload):
            raise SecurityError(400, "Unsupported profile field.", "invalid_profile")
        if set(payload) - {"name", "phone", "addresses"}:
            raise SecurityError(400, "Unsupported profile field.", "invalid_profile")
        updates = []
        values: list[Any] = []
        normalized_profile_phone: str | None = None
        if "name" in payload:
            updates.append("name=?"); values.append(clean_text(payload["name"], "name", 2, 80))
        if "phone" in payload:
            normalized_profile_phone = normalize_indian_phone(payload["phone"])
            updates.extend(("phone=?", "normalized_phone=?"))
            values.extend((normalized_profile_phone, normalized_profile_phone))
        addresses = payload.get("addresses") if "addresses" in payload else None
        if addresses is not None and (not isinstance(addresses, list) or len(addresses) > 10):
            raise SecurityError(400, "Invalid saved addresses.", "invalid_profile")
        cleaned_addresses = []
        if addresses is not None:
            for index, address in enumerate(addresses):
                if not isinstance(address, dict):
                    raise SecurityError(400, "Invalid saved address.", "invalid_profile")
                pincode = clean_text(address.get("pincode"), "pincode", 6, 6)
                if not pincode.isdigit():
                    raise SecurityError(400, "Invalid saved address.", "invalid_profile")
                address_type = address.get("type", "home")
                if address_type not in ("home", "work", "other"):
                    raise SecurityError(400, "Invalid saved address.", "invalid_profile")
                cleaned_addresses.append({
                    "id": "addr_" + secrets.token_hex(12),
                    "name": clean_text(address.get("name"), "name", 2, 80),
                    "phone": clean_text(address.get("phone"), "phone", 10, 20),
                    "street": clean_text(address.get("street"), "street", 5, 200),
                    "city": clean_text(address.get("city"), "city", 2, 80),
                    "state": clean_text(address.get("state", "Madhya Pradesh"), "state", 2, 80),
                    "pincode": pincode, "type": address_type,
                    "default": bool(address.get("isDefault")) or (index == 0 and not any(bool(item.get("isDefault")) for item in addresses)),
                })
        if not updates and addresses is None:
            raise SecurityError(400, "No profile changes supplied.", "invalid_profile")
        now = iso(utc_now())
        with self.connect() as db:
            try:
                db.execute("BEGIN IMMEDIATE")
                if normalized_profile_phone is not None:
                    phone_identity = db.execute(
                        "SELECT verified_phone FROM customer_auth_identities "
                        "WHERE user_id=? AND provider='phone'",
                        (user_id,),
                    ).fetchone()
                    if phone_identity and phone_identity["verified_phone"] != normalized_profile_phone:
                        raise SecurityError(
                            409,
                            "Verify a new mobile number before changing it.",
                            "phone_verification_required",
                        )
                    phone_owner = db.execute(
                        "SELECT id FROM users WHERE normalized_phone=?", (normalized_profile_phone,)
                    ).fetchone()
                    if phone_owner and phone_owner["id"] != user_id:
                        raise SecurityError(
                            409,
                            "An account with this mobile number already exists.",
                            "phone_exists",
                        )
                if updates:
                    updates.append("updated_at=?"); values.append(now); values.append(user_id)
                    db.execute(f"UPDATE users SET {','.join(updates)} WHERE id=?", values)
                if addresses is not None:
                    db.execute("DELETE FROM user_addresses WHERE user_id=?", (user_id,))
                    db.executemany(
                        "INSERT INTO user_addresses(id,user_id,name,phone,street,city,state,pincode,address_type,is_default,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                        [(item["id"], user_id, item["name"], item["phone"], item["street"], item["city"], item["state"], item["pincode"], item["type"], int(item["default"]), now, now) for item in cleaned_addresses],
                    )
                db.commit()
            except (SecurityError, sqlite3.IntegrityError) as exc:
                db.rollback()
                if isinstance(exc, SecurityError):
                    raise
                raise SecurityError(409, "An account with this mobile number already exists.", "phone_exists") from None
        return self.profile(user_id)

    def health(self) -> bool:
        try:
            with self.connect() as db:
                return db.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        except sqlite3.Error:
            return False
