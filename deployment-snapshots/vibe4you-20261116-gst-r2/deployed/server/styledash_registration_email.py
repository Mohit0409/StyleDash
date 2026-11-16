"""Pending email registrations: no customer account until inbox ownership is proved."""
from __future__ import annotations

import re
import secrets
import sqlite3
import smtplib
import ssl
from datetime import timedelta
from email.headerregistry import Address
from email.message import EmailMessage
from urllib.parse import urlsplit, urlunsplit, quote

from argon2.exceptions import InvalidHashError, VerificationError

try:
    from styledash_security import (
        SecurityError, TERMS_VERSION, PASSWORD_MIN, PASSWORD_MAX,
        normalize_email, normalize_indian_phone, clean_text, token_hash, iso, utc_now,
    )
except ModuleNotFoundError:
    from scripts.styledash_security import (
        SecurityError, TERMS_VERSION, PASSWORD_MIN, PASSWORD_MAX,
        normalize_email, normalize_indian_phone, clean_text, token_hash, iso, utc_now,
    )

RESERVED_SUFFIXES = (".test", ".invalid", ".example", ".localhost", ".local", ".internal")
RESERVED_DOMAINS = {"localhost", "example.com", "example.net", "example.org"}
DISPOSABLE_DOMAINS = {
    "10minutemail.com", "guerrillamail.com", "guerrillamail.info", "mailinator.com",
    "yopmail.com", "tempmail.com", "temp-mail.org", "maildrop.cc", "sharklasers.com",
    "dispostable.com", "getnada.com", "trashmail.com", "throwawaymail.com",
}
DOMAIN_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43}$")
TOKEN_LIFETIME_MINUTES = 30
# Wrong-password guesses allowed per verification link before it is destroyed.
MAX_CONFIRM_ATTEMPTS = 5
INVALID_CONFIRMATION_MESSAGE = (
    "This verification link is invalid or expired, or the password does not match."
)


def require_real_email_domain(email: str) -> None:
    domain = email.rsplit("@", 1)[-1]
    labels = domain.split(".")
    if (len(labels) < 2 or len(domain) > 253
            or any(not DOMAIN_LABEL.fullmatch(label) for label in labels)
            or len(labels[-1]) < 2 or labels[-1].isdigit()):
        raise SecurityError(400, "Use a valid email address.", "invalid_email_domain")
    if (domain in RESERVED_DOMAINS or domain.endswith(RESERVED_SUFFIXES)
            or any(domain == candidate or domain.endswith("." + candidate)
                   for candidate in DISPOSABLE_DOMAINS)):
        raise SecurityError(
            400, "Temporary or test email addresses are not accepted. Use your real inbox.",
            "blocked_email_domain",
        )


class SmtpRegistrationSender:
    """Uses validated private password-reset SMTP settings; never logs links or credentials."""
    def __init__(self, base_mailer):
        self.base = base_mailer
        parsed = urlsplit(base_mailer.reset_url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("An HTTPS customer origin is required for verification links")
        self.verify_url = urlunsplit((parsed.scheme, parsed.netloc, "/verify-email.html", "", ""))

    def __call__(self, recipient: str, token: str) -> None:
        url = self.verify_url + "#token=" + quote(token, safe="")
        msg = EmailMessage()
        msg["From"] = Address(display_name="Vibe4You Support", addr_spec=self.base.from_address)
        msg["To"] = recipient
        msg["Subject"] = "Verify your Vibe4You email"
        msg.set_content(
            "Complete your Vibe4You registration by verifying your email address.\n\n"
            f"Verify email: {url}\n\n"
            "You will be asked for the password you chose when registering.\n\n"
            "This one-time link expires in 30 minutes. If you did not request it, ignore this email."
        )
        client = self.base.smtp_factory(self.base.host, self.base.port, timeout=10)
        try:
            client.ehlo()
            client.starttls(context=ssl.create_default_context())
            client.ehlo()
            client.login(self.base.username, self.base.password)
            client.send_message(msg)
        finally:
            try:
                client.quit()
            except Exception:
                pass


class PendingEmailRegistration:
    def __init__(self, store, dispatcher=None):
        self.store = store
        self.dispatcher = dispatcher
        with self.store.connect() as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS pending_email_registrations(
                    token_hash TEXT PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    name TEXT NOT NULL,
                    phone TEXT,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                )"""
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS pending_email_expires_idx "
                "ON pending_email_registrations(expires_at)"
            )
            self._ensure_confirm_attempts_column(db)
        self.store._secure_files()

    @staticmethod
    def _ensure_confirm_attempts_column(db) -> None:
        """Idempotent, forward-safe migration; older code ignores the column."""
        columns = {row[1] for row in db.execute("PRAGMA table_info(pending_email_registrations)")}
        if "confirm_attempts" in columns:
            return
        try:
            db.execute(
                "ALTER TABLE pending_email_registrations "
                "ADD COLUMN confirm_attempts INTEGER NOT NULL DEFAULT 0"
            )
        except sqlite3.OperationalError as exc:
            # Another process may have added it between the check and ALTER.
            if "duplicate column" not in str(exc).lower():
                raise

    def expire(self, digest: str) -> None:
        with self.store.connect() as db:
            db.execute("DELETE FROM pending_email_registrations WHERE token_hash=?", (digest,))

    def begin(self, payload: dict) -> None:
        if self.dispatcher is None:
            raise SecurityError(
                503, "Email confirmation is temporarily unavailable. Use Google or mobile OTP sign-in.",
                "email_verification_unavailable",
            )
        if any(key in payload for key in (
            "role", "isAdmin", "admin", "emailVerified", "email_verified",
            "emailVerifiedAt", "email_verified_at",
        )):
            raise SecurityError(400, "Unsupported registration field.", "invalid_registration")
        email = normalize_email(payload.get("email"))
        require_real_email_domain(email)
        pwd = payload.get("password")
        if not isinstance(pwd, str) or not PASSWORD_MIN <= len(pwd) <= PASSWORD_MAX:
            raise SecurityError(400, f"Password must be {PASSWORD_MIN}–{PASSWORD_MAX} characters.", "weak_password")
        name = clean_text(payload.get("name"), "name", 2, 80)
        phone = normalize_indian_phone(payload["phone"]) if payload.get("phone") else None
        self.store._require_current_terms(payload)
        now = utc_now()
        now_value = iso(now)
        token = secrets.token_urlsafe(32)
        digest = token_hash(token)
        password_hash = self.store.passwords.hash(pwd)
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM pending_email_registrations WHERE expires_at<=?", (now_value,))
            if (db.execute("SELECT 1 FROM users WHERE normalized_email=?", (email,)).fetchone()
                    or db.execute(
                        "SELECT 1 FROM customer_auth_identities WHERE provider='google' AND verified_email=?",
                        (email,),
                    ).fetchone()):
                db.rollback()
                # Generic response avoids account enumeration.
                return
            if phone and db.execute("SELECT 1 FROM users WHERE normalized_phone=?", (phone,)).fetchone():
                raise SecurityError(409, "An account already uses this mobile number.", "phone_exists")
            db.execute("DELETE FROM pending_email_registrations WHERE email=?", (email,))
            db.execute(
                "INSERT INTO pending_email_registrations "
                "(token_hash,email,password_hash,name,phone,created_at,expires_at) "
                "VALUES(?,?,?,?,?,?,?)",
                (digest, email, password_hash, name, phone, now_value,
                 iso(now + timedelta(minutes=TOKEN_LIFETIME_MINUTES))),
            )
            db.commit()
        self.store._secure_files()
        try:
            self.dispatcher(email, token, lambda: self.expire(digest))
        except Exception:
            self.expire(digest)
            raise SecurityError(
                503, "Email verification is temporarily unavailable. Try Google or mobile OTP.",
                "email_verification_unavailable",
            ) from None

    @staticmethod
    def _invalid_confirmation() -> SecurityError:
        # One generic answer for bad/expired/used links and wrong passwords.
        return SecurityError(400, INVALID_CONFIRMATION_MESSAGE, "invalid_email_verification")

    def confirm(self, payload: dict):
        """Create the account only when the inbox owner proves the password.

        The link alone proves inbox control, but the stored password was chosen
        by whoever submitted the registration. Requiring that password here
        stops a third party from pre-registering a victim's address with an
        attacker-known password that the victim then activates.
        """
        token = payload.get("token")
        password = payload.get("password")
        if not isinstance(token, str) or not TOKEN_PATTERN.fullmatch(token):
            raise self._invalid_confirmation()
        if not isinstance(password, str) or not password or len(password) > PASSWORD_MAX:
            raise self._invalid_confirmation()
        digest = token_hash(token)
        # Reserve an attempt before the Argon2id check so concurrent guesses can
        # never exceed MAX_CONFIRM_ATTEMPTS verifications for one link.
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            now = iso(utc_now())
            reserved = db.execute(
                "UPDATE pending_email_registrations SET confirm_attempts=confirm_attempts+1 "
                "WHERE token_hash=? AND expires_at>? AND confirm_attempts<?",
                (digest, now, MAX_CONFIRM_ATTEMPTS),
            ).rowcount
            pending_hash = None
            attempt_number = 0
            if reserved == 1:
                reservation = db.execute(
                    "SELECT password_hash,confirm_attempts FROM pending_email_registrations WHERE token_hash=?",
                    (digest,),
                ).fetchone()
                pending_hash = reservation["password_hash"]
                attempt_number = reservation["confirm_attempts"]
            else:
                # Only purge an expired link here. An exhausted link may still
                # have reserved attempts verifying (e.g. a double-submitted
                # correct password); deleting it now would discard them.
                db.execute(
                    "DELETE FROM pending_email_registrations WHERE token_hash=? AND expires_at<=?",
                    (digest, now),
                )
            db.commit()
        if pending_hash is None:
            raise self._invalid_confirmation()
        try:
            matches = self.store.passwords.verify(pending_hash, password)
        except (VerificationError, InvalidHashError):
            matches = False
        if not matches:
            if attempt_number >= MAX_CONFIRM_ATTEMPTS:
                # The holder of the final attempt destroys the exhausted link.
                with self.store.connect() as db:
                    db.execute(
                        "DELETE FROM pending_email_registrations WHERE token_hash=? AND confirm_attempts>=?",
                        (digest, MAX_CONFIRM_ATTEMPTS),
                    )
            raise self._invalid_confirmation()
        with self.store.connect() as db:
            try:
                db.execute("BEGIN IMMEDIATE")
                now = iso(utc_now())
                pending = db.execute(
                    "SELECT * FROM pending_email_registrations "
                    "WHERE token_hash=? AND expires_at>? AND password_hash=?",
                    (digest, now, pending_hash),
                ).fetchone()
                if not pending:
                    raise self._invalid_confirmation()
                require_real_email_domain(pending["email"])
                user_id = "usr_" + secrets.token_hex(12)
                db.execute(
                    "INSERT INTO users(id,email,normalized_email,password_hash,name,phone,normalized_phone,"
                    "created_at,updated_at,password_changed_at,email_verified,email_verified_at) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,1,?)",
                    (user_id, pending["email"], pending["email"], pending["password_hash"],
                     pending["name"], pending["phone"], pending["phone"], now, now, now, now),
                )
                self.store._record_terms_acceptance(db, user_id, "password")
                user = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
                raw, csrf = self.store._new_session(db, user)
                db.execute("DELETE FROM pending_email_registrations WHERE token_hash=?", (digest,))
                db.commit()
            except SecurityError:
                db.rollback()
                raise
            except sqlite3.IntegrityError:
                db.rollback()
                raise SecurityError(409, "An account with these details already exists.", "identity_exists") from None
        self.store._secure_files()
        return self.store.safe_user(user), raw, csrf

