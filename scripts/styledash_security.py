"""Self-hosted StyleDash authentication and authoritative account data."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from cryptography.fernet import Fernet


COOKIE_NAME = "__Host-styledash_session"
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PASSWORD_MIN = 12
PASSWORD_MAX = 256
CUSTOMER_ABSOLUTE_HOURS = 24 * 7
CUSTOMER_IDLE_HOURS = 24


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


class SecurityStore:
    """SQLite-backed users, sessions, profiles, vendors, and audit records."""

    def __init__(self, path: Path, encryption_key: str) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.passwords = PasswordHasher(type=Type.ID)
        try:
            self.fernet = Fernet(encryption_key.encode("ascii"))
        except Exception as exc:
            raise RuntimeError("Invalid STYLEDASH_TOTP_ENCRYPTION_KEY") from exc
        self.csrf_key = hashlib.sha256(encryption_key.encode("ascii")).digest()
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
            mode = db.execute("PRAGMA journal_mode=WAL").fetchone()[0]
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
        self._secure_files()

    def _secure_files(self) -> None:
        for candidate in (self.path, Path(str(self.path) + "-wal"), Path(str(self.path) + "-shm")):
            if candidate.exists():
                candidate.chmod(0o600)

    @staticmethod
    def safe_user(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"], "uid": row["id"], "email": row["email"], "name": row["name"],
            "phone": row["phone"], "role": row["role"], "emailVerified": bool(row["email_verified"]),
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
        if any(field in payload for field in ("role", "isAdmin", "admin")):
            raise SecurityError(400, "Unsupported registration field.", "invalid_registration")
        email = normalize_email(payload.get("email"))
        password = payload.get("password")
        if not isinstance(password, str) or not PASSWORD_MIN <= len(password) <= PASSWORD_MAX:
            raise SecurityError(400, f"Password must be {PASSWORD_MIN}–{PASSWORD_MAX} characters.", "weak_password")
        name = clean_text(payload.get("name"), "name", 2, 80)
        phone_value = payload.get("phone")
        phone = clean_text(phone_value, "phone", 10, 20) if phone_value else None
        now = iso(utc_now())
        user_id = "usr_" + secrets.token_hex(12)
        encoded = self.passwords.hash(password)
        with self.connect() as db:
            try:
                db.execute("BEGIN IMMEDIATE")
                db.execute(
                    "INSERT INTO users(id,email,password_hash,name,phone,created_at,updated_at,password_changed_at) VALUES(?,?,?,?,?,?,?,?)",
                    (user_id, email, encoded, name, phone, now, now, now),
                )
                user = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
                raw, csrf = self._new_session(db, user)
                db.commit()
            except sqlite3.IntegrityError:
                db.rollback()
                raise SecurityError(409, "An account with this email already exists.", "email_exists") from None
        self._secure_files()
        return self.safe_user(user), raw, csrf

    def login(self, payload: dict[str, Any], client_key: str) -> tuple[dict[str, Any], str, str, bool]:
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
            user = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
            valid = False
            if user is not None and user["is_active"] and user["role"] == "customer":
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
                "SELECT s.*,u.id AS authenticated_user_id,u.email,u.name,u.phone,u.role,u.is_active,u.email_verified FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=?",
                (token_hash(raw_session),),
            ).fetchone()
            if row is None or row["revoked_at"] or not row["is_active"]:
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
            "role": row["role"], "emailVerified": bool(row["email_verified"]),
        }
        return user, row

    def revoke(self, raw_session: str) -> None:
        with self.connect() as db:
            db.execute("UPDATE sessions SET revoked_at=? WHERE token_hash=?", (iso(utc_now()), token_hash(raw_session)))

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
        forbidden = {"id", "uid", "role", "password_hash", "is_active", "email"}
        if forbidden.intersection(payload):
            raise SecurityError(400, "Unsupported profile field.", "invalid_profile")
        if set(payload) - {"name", "phone", "addresses"}:
            raise SecurityError(400, "Unsupported profile field.", "invalid_profile")
        updates = []
        values: list[Any] = []
        if "name" in payload:
            updates.append("name=?"); values.append(clean_text(payload["name"], "name", 2, 80))
        if "phone" in payload:
            updates.append("phone=?"); values.append(clean_text(payload["phone"], "phone", 10, 20))
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
            db.execute("BEGIN IMMEDIATE")
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
        return self.profile(user_id)

    def health(self) -> bool:
        try:
            with self.connect() as db:
                return db.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        except sqlite3.Error:
            return False
