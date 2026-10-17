#!/usr/bin/env python3
"""Validate that an automation report covers every declared regression checkpoint.

The canonical 185-checkpoint manifest is held in the local operations package.
This module contains no production credentials and performs no network or data writes
other than an optional aggregate JSON report.
"""
from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path


ALLOWED_STATUSES = {"PASS", "FAIL", "WARN", "INFO", "BLOCKED", "NOT TESTED"}


def analyze_coverage(manifest_rows, result_rows, expected=185):
    """Check exact-once ID coverage and report official/supplementary status counts.

    A PASS from a supplementary check never upgrades an official BLOCKED checkpoint.
    All manifest statuses remain individually visible.
    """
    ids = [str(row.get("id") or "").strip() for row in manifest_rows]
    result_ids = [str(row.get("id") or "").strip() for row in result_rows]
    manifest_counts = Counter(ids)
    result_counts = Counter(result_ids)
    canonical = set(ids)
    errors = []
    if len(ids) != expected:
        errors.append(f"expected {expected} manifest checkpoints, found {len(ids)}")
    if not ids or any(not value for value in ids):
        errors.append("manifest contains missing or empty IDs")
    if any(not value for value in result_ids):
        errors.append("report contains missing or empty IDs")
    duplicate_manifest = sorted(k for k,v in manifest_counts.items() if v > 1)
    duplicate_results = sorted(k for k,v in result_counts.items() if v > 1)
    missing = sorted(k for k in canonical if result_counts[k] == 0)
    if duplicate_manifest:
        errors.append(f"{len(duplicate_manifest)} duplicate manifest IDs")
    if duplicate_results:
        errors.append(f"{len(duplicate_results)} duplicate report IDs")
    if missing:
        errors.append(f"{len(missing)} missing official checkpoints")
    invalid = [str(r.get("id") or "") for r in result_rows
               if str(r.get("status") or "") not in ALLOWED_STATUSES]
    if invalid:
        errors.append(f"{len(invalid)} rows have invalid or absent status")
    official_rows = [r for r in result_rows if r.get("id") in canonical]
    supplementary_rows = [r for r in result_rows if r.get("id") not in canonical]
    official = dict(sorted(Counter(str(r.get("status")) for r in official_rows).items()))
    supplementary = dict(sorted(Counter(str(r.get("status")) for r in supplementary_rows).items()))
    observed_count = sum(official.values())
    if observed_count != len(ids):
        errors.append(f"official row count {observed_count} differs from manifest {len(ids)}")
    return {
        "integrity_pass": not errors,
        "manifest_count": len(ids),
        "official_count": observed_count,
        "supplementary_count": len(supplementary_rows),
        "official_status": official,
        "supplementary_status": supplementary,
        "missing_official_ids": missing,
        "duplicate_manifest_ids": duplicate_manifest,
        "duplicate_report_ids": duplicate_results,
        "invalid_status_row_count": len(invalid),
        "errors": errors,
        "coverage_note": "Only PASS among official checkpoints counts toward 185; supplementary PASS cannot upgrade blocked/unrun checks.",
    }


def audit_files(manifest_path: Path, report_path: Path, out_path: Path, expected=185):
    with manifest_path.open(encoding="utf-8-sig", newline="") as f:
        manifest = list(csv.DictReader(f))
    report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    rows = report.get("results") if isinstance(report, dict) else None
    if not isinstance(rows, list):
        raise ValueError("Report does not contain a results array")
    result = analyze_coverage(manifest, rows, expected=expected)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(out_path.suffix + ".tmp")
    tmp.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    tmp.replace(out_path)
    return result


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected", type=int, default=185)
    args = parser.parse_args()
    result = audit_files(args.manifest, args.report, args.output, args.expected)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["integrity_pass"] else 2)
