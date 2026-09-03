"""Plan or apply canonical catalogue metadata to existing shop products."""
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from catalog_normalization import (
        infer_audience,
        normalize_brand,
        normalize_delivery_type,
        normalize_department,
        normalize_product_category,
        normalize_size_label,
        normalize_subcategory,
    )
    from styledash_security import SecurityError
except ModuleNotFoundError:
    from scripts.catalog_normalization import (
        infer_audience,
        normalize_brand,
        normalize_delivery_type,
        normalize_department,
        normalize_product_category,
        normalize_size_label,
        normalize_subcategory,
    )

SHOP_AUDIENCE_FALLBACKS = {
    "Goutam Shoes": "men",
}


def utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def row_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def known_brand_from_name(name: str) -> str | None:
    return normalize_brand(None, name=name)


def active_variants(raw: str) -> list[dict[str, Any]]:
    values = json.loads(raw or "[]")
    if not isinstance(values, list):
        raise RuntimeError("Invalid variants JSON in catalogue row.")
    return values

def canonical_department(row: dict[str, Any], shop_name: str, category: str) -> tuple[str, str | None]:
    name = row["name"]
    description = row["description"]
    raw = row["department"]
    explicit = infer_audience(name, description, category)
    if explicit:
        return explicit, None
    try:
        return normalize_department(
            raw,
            name=name,
            description=description,
            category=category,
        ), None
    except SecurityError:
        fallback = SHOP_AUDIENCE_FALLBACKS.get(shop_name)
        if fallback:
            return fallback, f"department inferred from audited shop fallback: {shop_name} -> {fallback}"
        raise


def canonical_brand(row: dict[str, Any], shop_name: str) -> tuple[str | None, str | None]:
    inferred = known_brand_from_name(row["name"])
    if inferred:
        return inferred, None
    current = normalize_brand(row["brand"], name=row["name"])
    if current and current.casefold() == shop_name.casefold():
        return current, "manufacturer brand unresolved; retaining existing shop-name brand"
    return current, None

def plan_product(row: dict[str, Any]) -> dict[str, Any]:
    shop_name = row["shop_name"]
    category = normalize_product_category(
        row["category"],
        name=row["name"],
        description=row["description"],
        legacy_department=row["department"],
    )
    department, department_note = canonical_department(row, shop_name, category)
    brand, brand_note = canonical_brand(row, shop_name)
    attributes = json.loads(row["attributes_json"] or "{}")
    subcategory = normalize_subcategory(
        attributes.get("subcategory"),
        name=row["name"],
        category=category,
    )
    delivery_type = normalize_delivery_type(attributes.get("deliveryType", "normal"))
    if subcategory:
        attributes["subcategory"] = subcategory
    else:
        attributes.pop("subcategory", None)
    attributes["deliveryType"] = delivery_type
    variants = active_variants(row["variants_json"])
    normalized_variants: list[dict[str, Any]] = []
    for item in variants:
        updated = dict(item)
        updated["size"] = normalize_size_label(item.get("size"), category)
        normalized_variants.append(updated)
    active_sizes = [
        item["size"] for item in normalized_variants if item.get("active", True)
    ]
    size_summary = ", ".join(active_sizes)
    changes = {
        "brand": brand,
        "department": department,
        "category": category,
        "size": size_summary,
        "variants_json": json.dumps(normalized_variants, separators=(",", ":")),
        "attributes_json": json.dumps(attributes, separators=(",", ":"), sort_keys=True),
    }
    before = {key: row[key] for key in changes}
    changed = {key: {"before": before[key], "after": value} for key, value in changes.items() if before[key] != value}
    notes = [value for value in (department_note, brand_note) if value]
    return {
        "id": row["id"],
        "name": row["name"],
        "shopName": shop_name,
        "status": row["status"],
        "changes": changed,
        "notes": notes,
        "values": changes,
    }

def load_rows(db: sqlite3.Connection) -> list[dict[str, Any]]:
    db.row_factory = sqlite3.Row
    rows = db.execute(
        """
        SELECT p.*, a.shop_name
          FROM shop_product_submissions p
          JOIN vendor_applications a ON a.id=p.application_id
         WHERE p.status='PUBLISHED'
         ORDER BY p.id
        """
    ).fetchall()
    return [row_dict(row) for row in rows]


def summarize(plans: list[dict[str, Any]]) -> dict[str, Any]:
    changed = [plan for plan in plans if plan["changes"]]
    ambiguities = [
        {"id": plan["id"], "name": plan["name"], "shopName": plan["shopName"], "notes": plan["notes"]}
        for plan in plans if plan["notes"]
    ]
    departments: dict[str, int] = {}
    categories: dict[str, int] = {}
    for plan in plans:
        values = plan["values"]
        departments[values["department"]] = departments.get(values["department"], 0) + 1
        categories[values["category"]] = categories.get(values["category"], 0) + 1
    return {
        "totalProducts": len(plans),
        "changedProducts": len(changed),
        "unchangedProducts": len(plans) - len(changed),
        "ambiguityCount": len(ambiguities),
        "departmentsAfter": dict(sorted(departments.items())),
        "categoriesAfter": dict(sorted(categories.items())),
        "ambiguities": ambiguities,
    }

def sqlite_backup(source_path: Path, backup_path: Path) -> None:
    if backup_path.exists():
        raise RuntimeError(f"Backup already exists: {backup_path}")
    source = sqlite3.connect(source_path)
    destination = sqlite3.connect(backup_path)
    try:
        source.backup(destination)
        if destination.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("Backup integrity check failed.")
    finally:
        destination.close()
        source.close()


def apply_plans(db_path: Path, plans: list[dict[str, Any]], backup_path: Path) -> int:
    sqlite_backup(db_path, backup_path)
    db = sqlite3.connect(db_path)
    try:
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("BEGIN IMMEDIATE")
        now = utc_iso()
        changed = 0
        for plan in plans:
            if not plan["changes"]:
                continue
            values = plan["values"]
            db.execute(
                """UPDATE shop_product_submissions
                   SET brand=?,department=?,category=?,size=?,variants_json=?,attributes_json=?,updated_at=?
                 WHERE id=? AND status='PUBLISHED'""",
                (values["brand"], values["department"], values["category"], values["size"],
                 values["variants_json"], values["attributes_json"], now, plan["id"]),
            )
            changed += 1
        if db.execute("PRAGMA foreign_key_check").fetchall():
            raise RuntimeError("Foreign-key check failed after backfill.")
        db.commit()
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("Database integrity check failed after backfill.")
        return changed
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("db", type=Path, help="Path to styledash.db")
    parser.add_argument("--apply", action="store_true", help="Apply the planned changes. Default is dry-run.")
    parser.add_argument("--backup", type=Path, help="Backup path used only with --apply.")
    parser.add_argument("--report", type=Path, help="Optional JSON report output path.")
    args = parser.parse_args()
    if not args.db.exists():
        raise SystemExit(f"Database not found: {args.db}")
    db = sqlite3.connect(f"file:{args.db.resolve().as_posix()}?mode=ro", uri=True)
    try:
        plans = [plan_product(row) for row in load_rows(db)]
    finally:
        db.close()
    summary = summarize(plans)
    result = {
        "mode": "apply" if args.apply else "dry-run",
        "database": str(args.db.resolve()),
        "summary": summary,
        "products": plans,
    }
    if args.apply:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = args.backup or args.db.with_name(f"{args.db.stem}.pre-catalog-backfill-{stamp}{args.db.suffix}")
        result["backup"] = str(backup.resolve())
        result["appliedProducts"] = apply_plans(args.db, plans, backup)
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.report:
        args.report.write_text(text + "\n", encoding="utf-8")
    print(json.dumps({"mode": result["mode"], **summary}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
