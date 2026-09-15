#!/usr/bin/env python3
"""Safely remove pre-launch order history while preserving inventory and business data."""

import argparse
import copy
import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

try:
    import fcntl
except ImportError:  # Windows validation; Termux provides fcntl.
    fcntl = None

CONFIRMATION = "PURGE_PRELAUNCH_ORDERS"
ORDER_KEYS = ("orders", "idempotency", "processedPayments", "processedRefunds")


def canonical_hash(value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_state(path):
    with path.open("r", encoding="utf-8") as handle:
        state = json.load(handle)
    if not isinstance(state, dict):
        raise RuntimeError("payment state must be a JSON object")
    for key in ORDER_KEYS + ("inventory", "processedWebhookEvents", "operationalAlerts"):
        if key not in state or not isinstance(state[key], dict):
            raise RuntimeError("payment state is missing required map: %s" % key)
    return state


def related_alert_ids(alerts, order_ids):
    removed = set()
    for alert_id, alert in alerts.items():
        if not isinstance(alert, dict):
            continue
        if alert.get("styleDashOrderId") in order_ids or alert.get("entityId") in order_ids:
            removed.add(alert_id)
    return removed


def write_atomic(path, state):
    temporary = path.with_suffix(path.suffix + ".prelaunch.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(state, handle, separators=(",", ":"), ensure_ascii=False)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.chmod(str(temporary), 0o600)
    except OSError:
        pass
    os.replace(str(temporary), str(path))
    try:
        os.chmod(str(path), 0o600)
    except OSError:
        pass


def purge(state):
    original = copy.deepcopy(state)
    order_ids = set(state["orders"].keys())
    removed_alerts = related_alert_ids(state["operationalAlerts"], order_ids)

    for key in ORDER_KEYS:
        state[key] = {}
    state["operationalAlerts"] = {
        key: value for key, value in state["operationalAlerts"].items() if key not in removed_alerts
    }
    state["processedWebhookEvents"] = {
        key: value for key, value in state["processedWebhookEvents"].items() if value not in removed_alerts
    }

    if canonical_hash(state["inventory"]) != canonical_hash(original["inventory"]):
        raise RuntimeError("inventory changed during purge")
    for key in ORDER_KEYS:
        if state[key]:
            raise RuntimeError("order-related state was not fully cleared: %s" % key)
    return {
        "orders": len(original["orders"]),
        "idempotency": len(original["idempotency"]),
        "payments": len(original["processedPayments"]),
        "refunds": len(original["processedRefunds"]),
        "alerts": len(removed_alerts),
        "inventory_entries": len(original["inventory"]),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("state_path", type=Path)
    parser.add_argument("backup_dir", type=Path)
    parser.add_argument("--confirm", required=True)
    args = parser.parse_args()

    if args.confirm != CONFIRMATION:
        raise SystemExit("refusing purge: confirmation token did not match")
    if os.environ.get("STYLEDASH_ORDERING_ENABLED", "false").strip().lower() == "true":
        raise SystemExit("refusing purge while STYLEDASH_ORDERING_ENABLED=true")
    if not args.state_path.is_file():
        raise SystemExit("payment state file does not exist")

    args.backup_dir.mkdir(parents=True, exist_ok=True)
    lock_path = args.state_path.with_suffix(args.state_path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as lock_handle:
        try:
            os.chmod(str(lock_path), 0o600)
        except OSError:
            pass
        if fcntl is not None:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        try:
            state = load_state(args.state_path)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            backup_path = args.backup_dir / ("orders.prelaunch.%s.json" % stamp)
            shutil.copy2(str(args.state_path), str(backup_path))
            try:
                os.chmod(str(backup_path), 0o600)
            except OSError:
                pass

            counts = purge(state)
            write_atomic(args.state_path, state)
            reloaded = load_state(args.state_path)
            if canonical_hash(reloaded["inventory"]) != canonical_hash(state["inventory"]):
                raise RuntimeError("post-write inventory verification failed")
        finally:
            if fcntl is not None:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)

    print("backup=%s" % backup_path)
    print("orders_removed=%d" % counts["orders"])
    print("order_indexes_removed=%d" % (counts["idempotency"] + counts["payments"] + counts["refunds"]))
    print("order_alerts_removed=%d" % counts["alerts"])
    print("inventory_entries_preserved=%d" % counts["inventory_entries"])
    print("prelaunch_order_purge=ok")


if __name__ == "__main__":
    main()
