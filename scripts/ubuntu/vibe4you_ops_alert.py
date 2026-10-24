#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen

STATE_DIR = Path(
    os.getenv(
        "VIBE4YOU_ALERT_STATE_DIR",
        "/var/lib/vibe4you-production/run/ops-alerts",
    )
)
THROTTLE_SECONDS = int(os.getenv("VIBE4YOU_ALERT_THROTTLE_SECONDS", "3600"))


def enabled(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def safe_event(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.@-]+", "_", value)[:120]
    return cleaned or "unknown"


def main() -> int:
    event = safe_event(sys.argv[1] if len(sys.argv) > 1 else "unknown")
    if not enabled(os.getenv("STYLEDASH_NTFY_ENABLED")):
        print("VIBE4YOU_OPS_ALERT=DISABLED")
        return 0

    base_url = os.getenv("STYLEDASH_NTFY_BASE_URL", "https://ntfy.sh").strip()
    topic = os.getenv("STYLEDASH_NTFY_TOPIC", "").strip()
    if not base_url.startswith(("https://", "http://")) or not topic:
        print("VIBE4YOU_OPS_ALERT=NOT_CONFIGURED")
        return 1

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    state_file = STATE_DIR / event
    now = int(time.time())
    try:
        previous = int(state_file.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        previous = 0

    if 0 <= now - previous < THROTTLE_SECONDS:
        print("VIBE4YOU_OPS_ALERT=SUPPRESSED")
        return 0

    payload = {
        "topic": topic,
        "title": "Vibe4You production alert",
        "message": f"Operational check failed: {event}",
        "priority": 5,
        "tags": ["warning", "vibe4you"],
    }
    request = Request(
        base_url.rstrip("/"),
        data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "Vibe4You-Ops-Alert/1.0",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=3) as response:
            if not 200 <= int(getattr(response, "status", 200)) < 300:
                print("VIBE4YOU_OPS_ALERT=DELIVERY_FAILED")
                return 1
    except Exception:
        print("VIBE4YOU_OPS_ALERT=DELIVERY_FAILED")
        return 1

    state_file.write_text(str(now), encoding="utf-8")
    os.chmod(state_file, 0o600)
    print("VIBE4YOU_OPS_ALERT=SENT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())