"""Offline, read-only staging isolation preflight for Vibe4You.

The caller supplies sanitized systemd settings and allowlisted staging mode flags.
The checker has no remote access, does not read secret values and never deploys.

Passing is a *configuration preflight*, NOT a runtime mount-namespace
penetration test nor certification of the staging environment.
"""
from __future__ import annotations

import argparse
import json
from pathlib import PurePosixPath, Path


PROTECTED_PRODUCTION_ROOTS = (
    "/var/lib/vibe4you-production",
    "/var/backups/vibe4you-production",
    "/opt/vibe4you-production",
    "/etc/vibe4you-production",
)
ALLOWED_STAGING_WRITE_ROOT = "/var/lib/vibe4you-staging"
REQUIRED_SCOPED_DATA_PATHS = (
    "STYLEDASH_DATABASE_PATH",
    "STYLEDASH_DATA_DIR",
    "STYLEDASH_CATALOG_PATH",
    "STYLEDASH_SETTINGS_PATH",
)
DISABLED_STAGING_SETTINGS = (
    "STYLEDASH_ORDERING_ENABLED",
    "STYLEDASH_NTFY_ENABLED",
    "STYLEDASH_NTFY_BACKGROUND",
    "STYLEDASH_ENABLE_TEST_PRODUCT",
)
FALSE_VALUES = {"false", "0", "off", "no"}
TRUE_VALUES = {"yes", "1", "true", "on"}


def _tokens(raw: object) -> set[str]:
    """Systemd lists may be space separated or JSON arrays.

    Fail closed on unsafe prefix modifiers and unusual path representations.
    """
    if isinstance(raw, str):
        values = raw.split()
    elif isinstance(raw, list) and all(isinstance(p, str) for p in raw):
        values = raw
    else:
        return set()
    return {p for p in values if p.startswith("/") and ".." not in PurePosixPath(p).parts and "\\" not in p}


def check_staging(snapshot: dict) -> dict:
    errors: list[str] = []
    staging = snapshot.get("staging", {})
    production = snapshot.get("production", {})
    settings = snapshot.get("settings", {})
    paths = snapshot.get("paths", {})
    if not isinstance(staging, dict):
        staging = {}
    if not isinstance(production, dict):
        production = {}
    if not isinstance(settings, dict):
        settings = {}
    if not isinstance(paths, dict):
        paths = {}
    if staging.get("ActiveState") != "active":
        errors.append("staging_service_not_active")
    if staging.get("ProtectSystem") != "strict":
        errors.append("protect_system_not_strict")
    if staging.get("NoNewPrivileges") != "yes":
        errors.append("privilege_escalation_not_disabled")
    if staging.get("PrivateTmp") != "yes":
        errors.append("private_tmp_not_enabled")
    if staging.get("ProtectHome") not in ("yes", "read-only"):
        errors.append("home_not_protected")

    writable = _tokens(staging.get("ReadWritePaths", ""))
    if writable != {ALLOWED_STAGING_WRITE_ROOT}:
        errors.append("unexpected_staging_write_paths")

    hidden = _tokens(staging.get("InaccessiblePaths", ""))
    missing = [p for p in PROTECTED_PRODUCTION_ROOTS if p not in hidden]
    if missing:
        errors.append("production_filesystem_not_hidden")
    if not staging.get("User"):
        errors.append("staging_user_missing")

    for key in REQUIRED_SCOPED_DATA_PATHS:
        entry = paths.get(key)
        if not isinstance(entry, dict):
            errors.append("missing_staging_path_status:" + key)
            continue
        if entry.get("scope") != "staging" or entry.get("exists") is not True:
            errors.append("data_path_outside_staging:" + key)

    if str(settings.get("RAZORPAY_MODE", "")).lower() != "test":
        errors.append("razorpay_not_test_mode")
    for key in DISABLED_STAGING_SETTINGS:
        val = str(settings.get(key, "")).casefold()
        if val not in FALSE_VALUES:
            errors.append("staging_external_actions_not_disabled:" + key)

    # Same identity is not automatically treated as a release blocker after
    # explicit mount visibility denial. Report it as a remaining trust boundary.
    shared_user = bool(staging.get("User")) and staging.get("User") == production.get("User")
    return {
        "passed": not errors,
        "issues": sorted(set(errors)),
        "shared_service_account": shared_user,
        "full_runtime_isolation_verified": False,
        "protected_roots_required": len(PROTECTED_PRODUCTION_ROOTS),
        "protected_roots_configured": sum(p in hidden for p in PROTECTED_PRODUCTION_ROOTS),
        "note": "Only static configuration. Requires stage-only runtime test and rollback before deployment.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline Vibe4You staging confinement preflight")
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    data = json.loads(args.snapshot.read_text(encoding="utf-8"))
    result = check_staging(data)
    output = json.dumps(result, indent=2)
    print(output)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(output + "\n", encoding="utf-8")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
