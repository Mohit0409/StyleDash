"""Private, loopback-only StyleDash administrator identity and operations."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import sqlite3
from datetime import timedelta
from pathlib import Path
from typing import Any

import pyotp
from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken

try:
    from styledash_security import ClosingConnection, SecurityError, iso, token_hash, utc_now
except ModuleNotFoundError:
    from scripts.styledash_security import ClosingConnection, SecurityError, iso, token_hash, utc_now


ADMIN_COOKIE = "styledash_admin_session"
CHALLENGE_COOKIE = "styledash_admin_challenge"
ADMIN_ABSOLUTE_HOURS = 8
ADMIN_IDLE_MINUTES = 30
CHALLENGE_MINUTES = 5
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.@+-]{2,253}$")


class AdminStore:
    def __init__(self, path: Path, encryption_key: str) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.passwords = PasswordHasher(type=Type.ID)
        try:
            self.fernet = Fernet(encryption_key.encode("ascii"))
        except Exception as exc:
            raise RuntimeError("Invalid STYLEDASH_TOTP_ENCRYPTION_KEY") from exc
        self.csrf_key = hashlib.sha256(b"styledash-local-admin-csrf\0" + encryption_key.encode("ascii")).digest()
        self._migrate()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5, isolation_level=None, factory=ClosingConnection)
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
                CREATE TABLE IF NOT EXISTS admin_users(
                  id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL,
                  is_active INTEGER NOT NULL DEFAULT 1, totp_enabled INTEGER NOT NULL DEFAULT 0,
                  encrypted_totp_secret BLOB NOT NULL, last_totp_counter INTEGER,
                  created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS admin_sessions(
                  id TEXT PRIMARY KEY, admin_user_id TEXT NOT NULL REFERENCES admin_users(id) ON DELETE CASCADE,
                  token_hash TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL, expires_at TEXT NOT NULL,
                  idle_expires_at TEXT NOT NULL, last_seen_at TEXT NOT NULL, revoked_at TEXT
                );
                CREATE INDEX IF NOT EXISTS admin_sessions_token_idx ON admin_sessions(token_hash);
                CREATE TABLE IF NOT EXISTS admin_login_challenges(
                  id TEXT PRIMARY KEY, admin_user_id TEXT NOT NULL REFERENCES admin_users(id) ON DELETE CASCADE,
                  token_hash TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL, expires_at TEXT NOT NULL, used_at TEXT
                );
                CREATE TABLE IF NOT EXISTS admin_login_attempts(
                  id INTEGER PRIMARY KEY AUTOINCREMENT, username_hash TEXT NOT NULL, client_key TEXT NOT NULL,
                  stage TEXT NOT NULL, succeeded INTEGER NOT NULL, attempted_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS admin_attempt_lookup_idx
                  ON admin_login_attempts(username_hash,client_key,stage,attempted_at);
                CREATE TABLE IF NOT EXISTS admin_recovery_codes(
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  admin_user_id TEXT NOT NULL REFERENCES admin_users(id) ON DELETE CASCADE,
                  code_hash TEXT NOT NULL UNIQUE, used_at TEXT
                );
                CREATE TABLE IF NOT EXISTS local_admin_audit_log(
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  admin_user_id TEXT REFERENCES admin_users(id), action TEXT NOT NULL,
                  target_type TEXT, target_id TEXT, result TEXT NOT NULL,
                  metadata_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL
                );
                """
            )
            db.execute(
                "INSERT OR IGNORE INTO schema_migrations(version,applied_at) VALUES(2,?)",
                (iso(utc_now()),),
            )
        self._secure_files()

    def _secure_files(self) -> None:
        for candidate in (self.path, Path(str(self.path) + "-wal"), Path(str(self.path) + "-shm")):
            if candidate.exists():
                candidate.chmod(0o600)

    @staticmethod
    def normalize_username(value: Any) -> str:
        if not isinstance(value, str):
            raise SecurityError(400, "Enter a valid administrator username.", "invalid_admin_username")
        username = value.strip().casefold()
        if not USERNAME_PATTERN.fullmatch(username):
            raise SecurityError(400, "Enter a valid administrator username.", "invalid_admin_username")
        return username

    @staticmethod
    def safe_admin(row: sqlite3.Row) -> dict[str, Any]:
        return {"id": row["id"], "username": row["username"]}

    @staticmethod
    def session_cookie(raw: str) -> str:
        return f"{ADMIN_COOKIE}={raw}; Path=/; Max-Age={ADMIN_ABSOLUTE_HOURS * 3600}; HttpOnly; SameSite=Strict"

    @staticmethod
    def challenge_cookie(raw: str) -> str:
        return f"{CHALLENGE_COOKIE}={raw}; Path=/; Max-Age={CHALLENGE_MINUTES * 60}; HttpOnly; SameSite=Strict"

    @staticmethod
    def clear_cookie(name: str) -> str:
        return f"{name}=; Path=/; Max-Age=0; HttpOnly; SameSite=Strict"

    def csrf_token(self, raw_session: str) -> str:
        return hmac.new(self.csrf_key, raw_session.encode("utf-8"), hashlib.sha256).hexdigest()

    def verify_csrf(self, raw_session: str | None, supplied: str | None) -> None:
        if not raw_session or not supplied or not hmac.compare_digest(self.csrf_token(raw_session), supplied):
            raise SecurityError(403, "Administrator CSRF verification failed.", "admin_csrf_failed")

    def _audit(
        self, db: sqlite3.Connection, admin_id: str | None, action: str,
        target_type: str | None, target_id: str | None, result: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        db.execute(
            "INSERT INTO local_admin_audit_log(admin_user_id,action,target_type,target_id,result,metadata_json,created_at) VALUES(?,?,?,?,?,?,?)",
            (admin_id, action, target_type, target_id, result, json.dumps(metadata or {}, separators=(",", ":")), iso(utc_now())),
        )

    def create_admin(self, username: str, password: str, secret: str, recovery_codes: list[str]) -> dict[str, Any]:
        normalized = self.normalize_username(username)
        if not 12 <= len(password) <= 256:
            raise SecurityError(400, "Administrator password must be 12–256 characters.", "weak_password")
        admin_id = "adm_" + secrets.token_hex(12)
        now = iso(utc_now())
        with self.connect() as db:
            try:
                db.execute("BEGIN IMMEDIATE")
                db.execute(
                    "INSERT INTO admin_users(id,username,password_hash,totp_enabled,encrypted_totp_secret,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                    (admin_id, normalized, self.passwords.hash(password), 1, self.fernet.encrypt(secret.encode("ascii")), now, now),
                )
                db.executemany(
                    "INSERT INTO admin_recovery_codes(admin_user_id,code_hash) VALUES(?,?)",
                    [(admin_id, token_hash(code.upper())) for code in recovery_codes],
                )
                self._audit(db, admin_id, "admin_created", "admin_user", admin_id, "success")
                row = db.execute("SELECT * FROM admin_users WHERE id=?", (admin_id,)).fetchone()
                db.commit()
            except sqlite3.IntegrityError:
                db.rollback()
                raise SecurityError(409, "That administrator username already exists.", "admin_exists") from None
        self._secure_files()
        return self.safe_admin(row)

    def begin_login(self, payload: dict[str, Any], client_key: str) -> str:
        try:
            username = self.normalize_username(payload.get("username"))
        except SecurityError:
            username = "invalid"
        password = payload.get("password")
        account_hash = token_hash(username)
        cutoff = iso(utc_now() - timedelta(minutes=15))
        with self.connect() as db:
            failures = db.execute(
                "SELECT COUNT(*) FROM admin_login_attempts WHERE succeeded=0 AND stage='password' AND attempted_at>=? AND (username_hash=? OR client_key=?)",
                (cutoff, account_hash, client_key),
            ).fetchone()[0]
            if failures >= 6:
                raise SecurityError(429, "Too many administrator login attempts.", "admin_login_rate_limited")
            admin = db.execute("SELECT * FROM admin_users WHERE username=?", (username,)).fetchone()
            valid = False
            if admin is not None and admin["is_active"] and isinstance(password, str) and len(password) <= 256:
                try:
                    valid = self.passwords.verify(admin["password_hash"], password)
                except (VerifyMismatchError, InvalidHashError):
                    valid = False
            db.execute(
                "INSERT INTO admin_login_attempts(username_hash,client_key,stage,succeeded,attempted_at) VALUES(?,?,?,?,?)",
                (account_hash, client_key, "password", int(valid), iso(utc_now())),
            )
            if not valid:
                self._audit(db, admin["id"] if admin else None, "admin_login_password", "admin_user", admin["id"] if admin else None, "failed")
                raise SecurityError(401, "Invalid administrator credentials.", "invalid_admin_credentials")
            raw = secrets.token_urlsafe(48)
            now = utc_now()
            db.execute("UPDATE admin_login_challenges SET used_at=? WHERE admin_user_id=? AND used_at IS NULL", (iso(now), admin["id"]))
            db.execute(
                "INSERT INTO admin_login_challenges(id,admin_user_id,token_hash,created_at,expires_at) VALUES(?,?,?,?,?)",
                (secrets.token_hex(16), admin["id"], token_hash(raw), iso(now), iso(now + timedelta(minutes=CHALLENGE_MINUTES))),
            )
            self._audit(db, admin["id"], "admin_login_password", "admin_user", admin["id"], "success")
        return raw

    def verify_totp(self, raw_challenge: str | None, code: Any, client_key: str) -> tuple[dict[str, Any], str, str]:
        if not raw_challenge or not isinstance(code, str) or not re.fullmatch(r"[0-9]{6}|[A-Fa-f0-9]{12}", code):
            raise SecurityError(401, "Invalid administrator verification code.", "invalid_admin_totp")
        now = utc_now()
        with self.connect() as db:
            row = db.execute(
                "SELECT c.*,a.username,a.is_active,a.encrypted_totp_secret,a.last_totp_counter FROM admin_login_challenges c JOIN admin_users a ON a.id=c.admin_user_id WHERE c.token_hash=?",
                (token_hash(raw_challenge),),
            ).fetchone()
            if row is None or row["used_at"] or not row["is_active"] or iso(now) >= row["expires_at"]:
                raise SecurityError(401, "Administrator challenge expired.", "admin_challenge_expired")
            cutoff = iso(now - timedelta(minutes=10))
            failures = db.execute(
                "SELECT COUNT(*) FROM admin_login_attempts WHERE succeeded=0 AND stage='totp' AND attempted_at>=? AND (username_hash=? OR client_key=?)",
                (cutoff, token_hash(row["username"]), client_key),
            ).fetchone()[0]
            if failures >= 8:
                raise SecurityError(429, "Too many administrator verification attempts.", "admin_totp_rate_limited")
            verified = False
            counter = None
            recovery_id = None
            if code.isdigit():
                try:
                    secret = self.fernet.decrypt(row["encrypted_totp_secret"]).decode("ascii")
                except InvalidToken:
                    raise SecurityError(500, "Administrator verification is unavailable.", "admin_totp_unavailable") from None
                totp = pyotp.TOTP(secret)
                current = int(now.timestamp()) // totp.interval
                for candidate in range(current - 1, current + 2):
                    if totp.verify(code, for_time=candidate * totp.interval, valid_window=0):
                        counter = candidate
                        verified = row["last_totp_counter"] is None or candidate > row["last_totp_counter"]
                        break
            else:
                recovery = db.execute(
                    "SELECT id FROM admin_recovery_codes WHERE admin_user_id=? AND code_hash=? AND used_at IS NULL",
                    (row["admin_user_id"], token_hash(code.upper())),
                ).fetchone()
                if recovery:
                    verified = True
                    recovery_id = recovery["id"]
            db.execute(
                "INSERT INTO admin_login_attempts(username_hash,client_key,stage,succeeded,attempted_at) VALUES(?,?,?,?,?)",
                (token_hash(row["username"]), client_key, "totp", int(verified), iso(now)),
            )
            if not verified:
                self._audit(db, row["admin_user_id"], "admin_totp", "admin_user", row["admin_user_id"], "failed")
                raise SecurityError(401, "Invalid administrator verification code.", "invalid_admin_totp")
            db.execute("BEGIN IMMEDIATE")
            db.execute("UPDATE admin_login_challenges SET used_at=? WHERE id=?", (iso(now), row["id"]))
            if counter is not None:
                db.execute("UPDATE admin_users SET last_totp_counter=? WHERE id=?", (counter, row["admin_user_id"]))
            if recovery_id is not None:
                db.execute("UPDATE admin_recovery_codes SET used_at=? WHERE id=?", (iso(now), recovery_id))
            raw = secrets.token_urlsafe(48)
            session_id = secrets.token_hex(16)
            db.execute(
                "INSERT INTO admin_sessions(id,admin_user_id,token_hash,created_at,expires_at,idle_expires_at,last_seen_at) VALUES(?,?,?,?,?,?,?)",
                (session_id, row["admin_user_id"], token_hash(raw), iso(now), iso(now + timedelta(hours=ADMIN_ABSOLUTE_HOURS)), iso(now + timedelta(minutes=ADMIN_IDLE_MINUTES)), iso(now)),
            )
            self._audit(db, row["admin_user_id"], "admin_login", "admin_session", session_id, "success")
            db.commit()
        return {"id": row["admin_user_id"], "username": row["username"]}, raw, self.csrf_token(raw)

    def authenticate(self, raw_session: str | None) -> tuple[dict[str, Any], sqlite3.Row]:
        if not raw_session:
            raise SecurityError(401, "Administrator authentication required.", "admin_authentication_required")
        now = utc_now()
        with self.connect() as db:
            row = db.execute(
                "SELECT s.*,a.username,a.is_active FROM admin_sessions s JOIN admin_users a ON a.id=s.admin_user_id WHERE s.token_hash=?",
                (token_hash(raw_session),),
            ).fetchone()
            if row is None or row["revoked_at"] or not row["is_active"]:
                raise SecurityError(401, "Administrator authentication required.", "admin_authentication_required")
            if iso(now) >= row["expires_at"] or iso(now) >= row["idle_expires_at"]:
                db.execute("UPDATE admin_sessions SET revoked_at=? WHERE id=?", (iso(now), row["id"]))
                raise SecurityError(401, "Administrator session expired.", "admin_session_expired")
            db.execute(
                "UPDATE admin_sessions SET last_seen_at=?,idle_expires_at=? WHERE id=?",
                (iso(now), iso(now + timedelta(minutes=ADMIN_IDLE_MINUTES)), row["id"]),
            )
        return {"id": row["admin_user_id"], "username": row["username"]}, row

    def logout(self, raw_session: str | None) -> None:
        if raw_session:
            with self.connect() as db:
                row = db.execute("SELECT id,admin_user_id FROM admin_sessions WHERE token_hash=?", (token_hash(raw_session),)).fetchone()
                if row:
                    db.execute("UPDATE admin_sessions SET revoked_at=? WHERE id=?", (iso(utc_now()), row["id"]))
                    self._audit(db, row["admin_user_id"], "admin_logout", "admin_session", row["id"], "success")

    def customers(self, query: str = "") -> list[dict[str, Any]]:
        pattern = f"%{query.strip().casefold()[:100]}%"
        with self.connect() as db:
            rows = db.execute(
                "SELECT id,email,name,phone,is_active,created_at FROM users WHERE email LIKE ? OR lower(name) LIKE ? ORDER BY created_at DESC LIMIT 200",
                (pattern, pattern),
            ).fetchall()
        return [{key: row[key] for key in row.keys()} for row in rows]

    def set_customer_active(self, admin_id: str, user_id: str, active: bool) -> dict[str, Any]:
        now = iso(utc_now())
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            changed = db.execute("UPDATE users SET is_active=?,updated_at=? WHERE id=?", (int(active), now, user_id)).rowcount
            if not changed:
                db.rollback()
                raise SecurityError(404, "Customer not found.", "customer_not_found")
            if not active:
                db.execute("UPDATE sessions SET revoked_at=? WHERE user_id=?", (now, user_id))
            self._audit(db, admin_id, "customer_enabled" if active else "customer_disabled", "customer", user_id, "success")
            db.commit()
        return {"id": user_id, "active": active}

    def vendor_applications(self) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute("SELECT * FROM vendor_applications ORDER BY created_at DESC LIMIT 200").fetchall()
        return [{key: row[key] for key in row.keys()} for row in rows]

    def review_vendor(self, admin_id: str, application_id: str, status: str) -> dict[str, Any]:
        if status not in ("approved", "rejected"):
            raise SecurityError(400, "Invalid vendor decision.", "invalid_vendor_status")
        now = iso(utc_now())
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            changed = db.execute(
                "UPDATE vendor_applications SET status=?,reviewed_by=NULL,updated_at=? WHERE id=? AND status='pending'",
                (status, now, application_id),
            ).rowcount
            if not changed:
                db.rollback()
                raise SecurityError(409, "Vendor application cannot be changed.", "invalid_vendor_transition")
            self._audit(db, admin_id, f"vendor_{status}", "vendor_application", application_id, "success")
            db.commit()
        return {"id": application_id, "status": status, "updatedAt": now}

    def audit(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT id,admin_user_id,action,target_type,target_id,result,metadata_json,created_at FROM local_admin_audit_log ORDER BY id DESC LIMIT ?",
                (max(1, min(limit, 500)),),
            ).fetchall()
        return [{key: row[key] for key in row.keys()} for row in rows]

    def record_action(
        self, admin_id: str, action: str, target_type: str, target_id: str, result: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        with self.connect() as db:
            self._audit(db, admin_id, action, target_type, target_id, result, metadata)

    def integrity(self) -> dict[str, Any]:
        with self.connect() as db:
            check = db.execute("PRAGMA integrity_check").fetchone()[0]
            migration = db.execute("SELECT COALESCE(MAX(version),0) FROM schema_migrations").fetchone()[0]
        return {"database": check, "migrationVersion": migration}
