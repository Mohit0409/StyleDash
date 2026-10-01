#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DATA_ROOT = Path(os.getenv("VIBE4YOU_DATA_ROOT", "/var/lib/vibe4you-production"))
BACKUP_ROOT = Path(
    os.getenv("VIBE4YOU_BACKUP_ROOT", "/var/backups/vibe4you-production/data")
)
RUN_DIR = Path(os.getenv("VIBE4YOU_RUN_DIR", str(DATA_ROOT / "run")))
PUBLIC_HEALTH_URL = os.getenv(
    "VIBE4YOU_PUBLIC_HEALTH_URL", "http://127.0.0.1:8080/api/health"
)
PUBLIC_EXTERNAL_URL = os.getenv(
    "VIBE4YOU_PUBLIC_EXTERNAL_URL", "https://vibe4you.in/"
)
ADMIN_EXTERNAL_URL = os.getenv(
    "VIBE4YOU_ADMIN_EXTERNAL_URL", "https://admin.vibe4you.in/"
)
MAX_BACKUP_AGE_SECONDS = int(
    os.getenv("VIBE4YOU_MAX_BACKUP_AGE_SECONDS", "129600")
)
MAX_DISK_USE_PERCENT = float(
    os.getenv("VIBE4YOU_MAX_DISK_USE_PERCENT", "85")
)
MIN_DISK_FREE_BYTES = int(
    os.getenv("VIBE4YOU_MIN_DISK_FREE_BYTES", str(20 * 1024**3))
)
SKIP_SYSTEMD = os.getenv("VIBE4YOU_SKIP_SYSTEMD", "").lower() in {
    "1", "true", "yes", "on"
}
SKIP_EXTERNAL = os.getenv("VIBE4YOU_SKIP_EXTERNAL", "").lower() in {
    "1", "true", "yes", "on"
}

UNITS = (
    "vibe4you-production-public.service",
    "vibe4you-production-admin.service",
    "vibe4you-cloudflared.service",
    "vibe4you-backup.timer",
)


def command_ok(*args: str) -> bool:
    result = subprocess.run(
        args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def fetch_json(url: str) -> dict:
    request = Request(url, headers={"User-Agent": "Vibe4You-Ops-Health/1.0"})
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_status(url: str) -> int:
    request = Request(url, headers={"User-Agent": "Vibe4You-Ops-Health/1.0"})
    try:
        with urlopen(request, timeout=15) as response:
            return int(response.status)
    except HTTPError as exc:
        return int(exc.code)


def marker_stamp(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def marker_age_seconds(stamp: str) -> int:
    parsed = datetime.strptime(stamp, "%Y%m%dT%H%M%SZ").replace(
        tzinfo=timezone.utc
    )
    return int((datetime.now(timezone.utc) - parsed).total_seconds())


def sqlite_integrity(path: Path) -> str:
    uri = path.resolve().as_uri() + "?mode=ro&immutable=1"
    connection = sqlite3.connect(uri, uri=True)
    try:
        return str(connection.execute("PRAGMA integrity_check").fetchone()[0])
    finally:
        connection.close()


def main() -> int:
    failures: list[str] = []

    if not SKIP_SYSTEMD:
        for unit in UNITS:
            if not command_ok("systemctl", "is-enabled", "--quiet", unit):
                failures.append(f"unit_not_enabled:{unit}")
            if not command_ok("systemctl", "is-active", "--quiet", unit):
                failures.append(f"unit_not_active:{unit}")

    try:
        payload = fetch_json(PUBLIC_HEALTH_URL)
        if payload.get("status") != "ok" or payload.get("database") != "ok":
            failures.append("public_health_not_ok")
    except (OSError, ValueError, json.JSONDecodeError, URLError):
        failures.append("public_health_unreachable")

    if not SKIP_EXTERNAL:
        for label, url in (
            ("public_external", PUBLIC_EXTERNAL_URL),
            ("admin_external", ADMIN_EXTERNAL_URL),
        ):
            try:
                status = fetch_status(url)
                if not 200 <= status < 400:
                    failures.append(f"{label}_http:{status}")
            except (OSError, URLError):
                failures.append(f"{label}_unreachable")

    try:
        usage = shutil.disk_usage(DATA_ROOT)
        used_percent = (usage.used / usage.total) * 100 if usage.total else 100
        if used_percent >= MAX_DISK_USE_PERCENT:
            failures.append(f"disk_usage_percent:{used_percent:.1f}")
        if usage.free < MIN_DISK_FREE_BYTES:
            failures.append(f"disk_free_bytes:{usage.free}")
    except OSError:
        failures.append("disk_usage_unavailable")

    markers = (
        "styledash-last-local-backup",
        "styledash-last-offdevice-backup",
        "styledash-last-secondary-backup",
    )
    stamps: dict[str, str] = {}
    for name in markers:
        path = RUN_DIR / name
        try:
            stamp = marker_stamp(path)
            age = marker_age_seconds(stamp)
            stamps[name] = stamp
            if age < 0 or age > MAX_BACKUP_AGE_SECONDS:
                failures.append(f"backup_marker_stale:{name}:{age}")
        except (OSError, ValueError):
            failures.append(f"backup_marker_invalid_or_unreadable:{name}")

    latest_stamp = stamps.get("styledash-last-local-backup")
    if latest_stamp:
        backup_db = BACKUP_ROOT / latest_stamp / "styledash.db"
        try:
            if sqlite_integrity(backup_db) != "ok":
                failures.append("latest_backup_sqlite_integrity")
        except (OSError, sqlite3.Error):
            failures.append("latest_backup_db_unreadable")

    if failures:
        print("VIBE4YOU_HEALTH=FAIL")
        for failure in failures:
            print(f"failure={failure}")
        return 1

    print("VIBE4YOU_HEALTH=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())