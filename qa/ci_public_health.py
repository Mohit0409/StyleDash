#!/usr/bin/env python3
"""Scheduled production read-only availability check; no credentials or mutations."""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://vibe4you.in"
PUBLIC = ("/", "/api/health", "/products", "/stores", "/offers")
OUT = Path("qa-results/ci-public-health.json")
USER_AGENT = "Vibe4You-Scheduled-Public-Regression/1.0 (read-only site health)"

def get(path: str):
    if not (path == "/" or path.startswith("/assets/") or path in PUBLIC):
        raise ValueError("Refusing unapproved path")
    request = urllib.request.Request(BASE + path, headers={"User-Agent": USER_AGENT, "Accept": "*/*"}, method="GET")
    t = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read(450_000 if path.startswith("/assets/") else 30_000)
            return {"status": response.status, "latency_ms": round((time.monotonic()-t)*1000), "body": body,
                    "type": response.headers.get("content-type", "")}
    except urllib.error.HTTPError as exc:
        return {"status":exc.code, "latency_ms":round((time.monotonic()-t)*1000), "body":b"", "type":""}

def run():
    results = []
    index = None
    for path in PUBLIC:
        try:
            response = get(path)
            status = response["status"]
            content = response["body"]
            kind = response["type"]
            good = status == 200 and (path == "/api/health" or b"<html" in content[:2000].lower())
            if path == "/":
                index = content
                good = good and b"vibe4you-ga4-consent-3c9d1b529f9a.js" not in content
            results.append({"path":path, "status":status, "latency_ms":response["latency_ms"], "passed":bool(good),
                            "detail": "200 with expected public content" if good else "unexpected status, body or emergency GA4 loader"})
        except Exception as exc:
            results.append({"path":path, "status":None, "passed":False, "detail":type(exc).__name__})
    if index:
        found = re.search(rb'<script\b[^>]*type="module"[^>]*src="(/assets/[^"]+\.js)"', index)
        if found:
            asset_path = found.group(1).decode("ascii")
            try:
                response = get(asset_path)
                got_id = b"G-PSHXB46P50" in response["body"]
                good = response["status"] == 200 and got_id
                results.append({"path":"active frontend bundle", "status":response["status"],
                                "latency_ms":response["latency_ms"], "passed":bool(good),
                                "detail":"GA4 configured in active bundle" if good else "bundle missing or GA4 ID not found"})
            except Exception as exc:
                results.append({"path":"active frontend bundle", "passed":False, "detail":type(exc).__name__})
        else:
            results.append({"path":"active frontend bundle", "passed":False, "detail":"module script missing"})
    report = {"timestamp_utc":datetime.now(timezone.utc).isoformat(), "scope":"public read-only external checks",
              "site":BASE, "results":results, "passed":all(item["passed"] for item in results),
              "note":"HTTP 200/GA4 ID do not prove checkout, conversions, data integrity, Realtime dashboard, or customer auth."}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 2

if __name__=="__main__":
    sys.exit(run())
