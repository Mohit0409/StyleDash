#!/usr/bin/env python3
"""Read-only public SEO coverage check for Vibe4You.

This deliberately reports missing storefront URLs as warnings until the SEO
release has been deployed. It never uses admin credentials or changes data.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

ORIGIN = "https://vibe4you.in"
REPORT = Path("qa-results/ci-public-seo.json")
HTTP_TIMEOUT = 20


def fetch_text(path: str) -> str:
    request = urllib.request.Request(
        ORIGIN + path,
        headers={"User-Agent": "Vibe4You-SEO-ReadOnly-Audit/1.0", "Accept": "application/xml,text/plain,application/json"},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
        if response.status != 200:
            raise ValueError(f"{path}: unexpected HTTP {response.status}")
        return response.read(5_000_000).decode("utf-8")


def evaluate(robots: str, sitemap: str, stores: list[dict]) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    expected_sitemap = f"Sitemap: {ORIGIN}/sitemap.xml"
    if expected_sitemap not in robots.splitlines():
        errors.append("robots.txt does not advertise the canonical sitemap URL")

    try:
        root = ET.fromstring(sitemap)
        urls = [
            (node.text or "").strip()
            for node in root.iter()
            if node.tag.rsplit("}", 1)[-1] == "loc"
        ]
    except ET.ParseError as exc:
        errors.append(f"invalid XML sitemap: {exc}")
        urls = []

    if not urls:
        errors.append("empty XML sitemap")
    if len(set(urls)) != len(urls):
        errors.append("duplicate sitemap URLs")
    if any(urlsplit(url).scheme != "https" or urlsplit(url).netloc != "vibe4you.in" for url in urls):
        errors.append("sitemap contains noncanonical host or scheme")
    if f"{ORIGIN}/" not in urls:
        errors.append("canonical homepage absent from sitemap")

    expected_stores = {
        f"{ORIGIN}/store/{item['slug']}"
        for item in stores
        if isinstance(item, dict)
        and item.get("active") is True
        and item.get("approved") is True
        and isinstance(item.get("slug"), str)
        and re.fullmatch(r"[a-z0-9-]+", item["slug"]) is not None
        and (item.get("productCount") or 0) > 0
    }
    published = {u for u in urls if u.startswith(f"{ORIGIN}/store/")}
    missing = sorted(expected_stores - published)
    if missing:
        warnings.append(f"{len(missing)} active stocked storefronts are missing from sitemap (SEO release pending?)")

    return {
        "passed": not errors,
        "errors": errors,
        "warnings": warnings,
        "totals": {
            "sitemap_urls": len(urls),
            "active_stocked_stores": len(expected_stores),
            "store_urls_in_sitemap": len(published),
            "missing_active_stores": len(missing),
        },
        "missing_sample": missing[:15],
    }


def main() -> int:
    now = datetime.now(timezone.utc).isoformat()
    try:
        robots = fetch_text("/robots.txt")
        sitemap = fetch_text("/sitemap.xml")
        raw = json.loads(fetch_text("/api/stores/active"))
        if not raw.get("success") or not isinstance(raw.get("stores"), list):
            raise ValueError("public stores API did not return an approved store list")
        report = evaluate(robots, sitemap, raw["stores"])
    except Exception as exc:
        report = {"passed": False, "errors": [f"public SEO read failed: {type(exc).__name__}: {exc}"], "warnings": []}
    report["created_at"] = now
    report["scope"] = "public GET only; no credentials, edits, sitemap submissions, or live deployment"
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
