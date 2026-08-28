#!/usr/bin/env python3
"""Interactively create the first separate local StyleDash administrator."""

from __future__ import annotations

import getpass
import os
import secrets
import sys
from pathlib import Path

import pyotp

tool_path = Path(__file__).resolve()
for module_root in (tool_path.parents[1], tool_path.parents[2] / "scripts"):
    sys.path.insert(0, str(module_root))

from styledash_admin import AdminStore  # noqa: E402
from styledash_security import SecurityError  # noqa: E402


def main() -> None:
    key = os.environ.get("STYLEDASH_TOTP_ENCRYPTION_KEY", "")
    database = Path(os.environ.get("STYLEDASH_DATABASE_PATH", Path.home() / ".local/share/styledash/styledash.db"))
    if not key:
        raise SystemExit("Private TOTP encryption key is not loaded; no changes made.")
    username = input("New local administrator username or email: ").strip()
    password = getpass.getpass("New administrator password (12+ characters): ")
    confirmation = getpass.getpass("Repeat administrator password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match; no changes made.")
    secret = pyotp.random_base32()
    normalized = AdminStore.normalize_username(username)
    uri = pyotp.TOTP(secret).provisioning_uri(name=normalized, issuer_name="Vibe4You Local Admin")
    print("\nAdd this account to your authenticator. This setup URI is shown locally once:")
    print(uri)
    verified = False
    for _ in range(3):
        code = getpass.getpass("Enter the current 6-digit authenticator code: ").strip()
        if pyotp.TOTP(secret).verify(code, valid_window=1):
            verified = True
            break
        print("That code was not valid.")
    if not verified:
        raise SystemExit("TOTP verification failed; no administrator was created.")
    if input(f"Type the exact username '{normalized}' to create this administrator: ").strip().casefold() != normalized:
        raise SystemExit("Confirmation failed; no changes made.")
    recovery_codes = [secrets.token_hex(6).upper() for _ in range(10)]
    try:
        admin = AdminStore(database, key).create_admin(normalized, password, secret, recovery_codes)
    except SecurityError as error:
        raise SystemExit(error.message) from None
    print(f"\nLocal administrator created: {admin['username']}")
    print("Store these one-time recovery codes securely. They will not be shown again:")
    for code in recovery_codes:
        print(code)


if __name__ == "__main__":
    main()
