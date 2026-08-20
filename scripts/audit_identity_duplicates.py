"""Read-only, PII-redacted identity preflight for a StyleDash SQLite database."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote

try:
    from styledash_security import SecurityError, normalize_email, normalize_indian_phone
except ImportError:
    from scripts.styledash_security import SecurityError, normalize_email, normalize_indian_phone


def redacted(value: str) -> str:
    """Identify a database row without exposing its ID or identity value."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def canonical_groups(
    rows: list[sqlite3.Row],
    value_key: str,
    owner_key: str,
    normalizer: Callable[[Any], str],
) -> tuple[dict[str, list[str]], list[str]]:
    groups: dict[str, list[str]] = defaultdict(list)
    invalid: list[str] = []
    for row in rows:
        value = row[value_key]
        if value is None or value == "":
            continue
        try:
            canonical = normalizer(value)
        except SecurityError:
            invalid.append(redacted(str(row[owner_key])))
            continue
        groups[canonical].append(str(row[owner_key]))
    return groups, invalid


def duplicate_refs(groups: dict[str, list[str]]) -> list[list[str]]:
    return [
        sorted(redacted(owner) for owner in owners)
        for owners in groups.values()
        if len(owners) > 1
    ]


def audit(database: Path) -> dict[str, Any]:
    uri = f"file:{quote(database.resolve().as_posix(), safe='/:')}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    try:
        users = connection.execute("SELECT id,email,phone FROM users").fetchall()
        identities = connection.execute(
            "SELECT id,user_id,provider,provider_subject,verified_email,verified_phone "
            "FROM customer_auth_identities"
        ).fetchall()
        user_emails, invalid_user_emails = canonical_groups(
            users, "email", "id", normalize_email
        )
        user_phones, invalid_user_phones = canonical_groups(
            users, "phone", "id", normalize_indian_phone
        )
        google_rows = [row for row in identities if row["provider"] == "google"]
        phone_rows = [row for row in identities if row["provider"] == "phone"]
        google_emails, invalid_google_emails = canonical_groups(
            google_rows, "verified_email", "id", normalize_email
        )
        verified_phones, invalid_verified_phones = canonical_groups(
            phone_rows, "verified_phone", "id", normalize_indian_phone
        )
        provider_subjects: dict[str, list[str]] = defaultdict(list)
        for row in identities:
            provider_subjects[f"{row['provider']}\0{row['provider_subject']}"].append(row["id"])

        conflicting_links: list[list[str]] = []
        for row in google_rows:
            try:
                canonical = normalize_email(row["verified_email"])
            except SecurityError:
                continue
            owners = user_emails.get(canonical, [])
            if owners and row["user_id"] not in owners:
                conflicting_links.append(
                    sorted([redacted(row["id"]), *(redacted(owner) for owner in owners)])
                )
        for row in phone_rows:
            try:
                canonical = normalize_indian_phone(row["verified_phone"])
            except SecurityError:
                continue
            owners = user_phones.get(canonical, [])
            if owners and row["user_id"] not in owners:
                conflicting_links.append(
                    sorted([redacted(row["id"]), *(redacted(owner) for owner in owners)])
                )

        result = {
            "databaseIntegrity": connection.execute("PRAGMA integrity_check").fetchone()[0],
            "foreignKeyViolations": len(connection.execute("PRAGMA foreign_key_check").fetchall()),
            "userCount": len(users),
            "identityCount": len(identities),
            "duplicateNormalizedEmails": duplicate_refs(user_emails),
            "duplicateNormalizedPhones": duplicate_refs(user_phones),
            "duplicateGoogleVerifiedEmails": duplicate_refs(google_emails),
            "duplicateVerifiedPhones": duplicate_refs(verified_phones),
            "duplicateProviderSubjects": duplicate_refs(provider_subjects),
            "conflictingIdentityLinks": sorted(conflicting_links),
            "invalidUserEmailRefs": sorted(invalid_user_emails),
            "invalidUserPhoneRefs": sorted(invalid_user_phones),
            "invalidGoogleEmailRefs": sorted(invalid_google_emails),
            "invalidVerifiedPhoneRefs": sorted(invalid_verified_phones),
        }
        result["safeToMigrate"] = (
            result["databaseIntegrity"] == "ok"
            and result["foreignKeyViolations"] == 0
            and not any(
                result[key]
                for key in (
                    "duplicateNormalizedEmails",
                    "duplicateNormalizedPhones",
                    "duplicateGoogleVerifiedEmails",
                    "duplicateVerifiedPhones",
                    "duplicateProviderSubjects",
                    "conflictingIdentityLinks",
                    "invalidUserEmailRefs",
                    "invalidUserPhoneRefs",
                    "invalidGoogleEmailRefs",
                    "invalidVerifiedPhoneRefs",
                )
            )
        )
        return result
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("database", type=Path)
    args = parser.parse_args()
    result = audit(args.database)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["safeToMigrate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
