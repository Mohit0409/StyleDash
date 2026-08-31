"""Server-authoritative shop applications and seller product submissions.

This module deliberately contains no HTTP or administrator authentication
logic.  The public and loopback-only admin servers authenticate requests and
enforce CSRF before calling these methods.  All ownership and state-transition
checks are repeated here so a handler mistake cannot grant seller/admin powers.
"""

from __future__ import annotations

import json
import re
import secrets
import sqlite3
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

try:
    from styledash_security import ClosingConnection, SecurityError, clean_text, iso, utc_now
except ModuleNotFoundError:  # Repository test import path.
    from scripts.styledash_security import ClosingConnection, SecurityError, clean_text, iso, utc_now


APPLICATION_STATUSES = (
    "DRAFT",
    "SUBMITTED",
    "UNDER_REVIEW",
    "APPROVED",
    "REJECTED",
    "ACTIVE",
    "SUSPENDED",
)
PRODUCT_STATUSES = (
    "DRAFT",
    "SUBMITTED",
    "UNDER_REVIEW",
    "APPROVED",
    "PUBLISHED",
    "REJECTED",
)
PRODUCT_CHANGE_ACTIONS = ("EDIT", "UNPUBLISH")
PRODUCT_CHANGE_STATUSES = ("SUBMITTED", "UNDER_REVIEW", "APPROVED", "REJECTED")
PRODUCT_CHANGE_ADMIN_TRANSITIONS = {
    "SUBMITTED": {"UNDER_REVIEW"},
    "UNDER_REVIEW": {"APPROVED", "REJECTED"},
}
ALLOWED_CATEGORIES = {
    "Clothing & Fashion",
    "Footwear",
    "Electronics",
    "Home & Living",
    "General Store",
}
APPLICATION_ADMIN_TRANSITIONS = {
    "SUBMITTED": {"UNDER_REVIEW"},
    "UNDER_REVIEW": {"APPROVED", "REJECTED"},
    "APPROVED": {"ACTIVE"},
    "ACTIVE": {"SUSPENDED"},
    "SUSPENDED": {"ACTIVE"},
}
PRODUCT_ADMIN_TRANSITIONS = {
    "SUBMITTED": {"UNDER_REVIEW"},
    "UNDER_REVIEW": {"APPROVED", "REJECTED"},
    "APPROVED": {"PUBLISHED"},
    "PUBLISHED": {"APPROVED"},  # Explicit unpublish.
}
PINCODE_PATTERN = re.compile(r"^\d{6}$")
APPLICATION_PAYLOAD_FIELDS = {
    "shopName",
    "ownerName",
    "category",
    "description",
    "address",
    "city",
    "state",
    "pincode",
    "businessInformation",
}
PRODUCT_PAYLOAD_FIELDS = {
    "name",
    "description",
    "brand",
    "department",
    "category",
    "pricePaise",
    "originalPricePaise",
    "inventory",
    "imageUrls",
    "attributes",
    "size",
    "colourName",
    "colourHex",
    "variants",
}
PRODUCT_CHANGE_PAYLOAD_FIELDS = PRODUCT_PAYLOAD_FIELDS - {"inventory", "size"}
DEPARTMENTS = {"men", "women", "kids", "unisex", "footwear", "accessories"}
COLOUR_HEX_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")
PRODUCT_MEDIA_PATH_PATTERN = re.compile(r"^/media/product-images/[0-9a-f]{32}\.(?:webp|jpg|png)$")


def _optional_text(value: Any, label: str, maximum: int) -> str | None:
    if value is None or value == "":
        return None
    return clean_text(value, label, 1, maximum)


def _row_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def _store_slug(application_id: str) -> str:
    return f"local-shop-{application_id[-12:]}"

def _row_variants(row: sqlite3.Row) -> list[dict[str, Any]]:
    raw = row["variants_json"] if "variants_json" in row.keys() else None
    try:
        variants = json.loads(raw or "[]")
    except (TypeError, json.JSONDecodeError):
        variants = []
    clean: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    if isinstance(variants, list):
        for index, item in enumerate(variants):
            if not isinstance(item, dict):
                continue
            size = item.get("size")
            inventory = item.get("inventory")
            if not (isinstance(size, str) and size.strip() and isinstance(inventory, int) and not isinstance(inventory, bool)):
                continue
            variant_id = item.get("id")
            if not isinstance(variant_id, str) or not variant_id.strip() or len(variant_id) > 128 or variant_id in seen_ids:
                variant_id = f"{row['id']}-var-{index + 1}"
            seen_ids.add(variant_id)
            clean.append({
                "id": variant_id,
                "size": size.strip(),
                "inventory": max(0, inventory),
                "active": item.get("active") is not False,
            })
    if clean:
        return clean
    return [{
        "id": f"{row['id']}-var-1",
        "size": row["size"],
        "inventory": row["inventory"],
        "active": True,
    }]


class ShopWorkflow:
    """SQLite-backed shop workflow with customer ownership enforcement."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._migrate()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.path, timeout=5, isolation_level=None, factory=ClosingConnection
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=5000")
        return connection

    def _migrate(self) -> None:
        with self.connect() as db:
            mode = db.execute("PRAGMA journal_mode=WAL").fetchone()[0]
            if str(mode).lower() != "wal":
                raise RuntimeError("SQLite WAL mode is unavailable")
            if db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='users'"
            ).fetchone() is None:
                raise RuntimeError("Shop migration requires the customer users table")
            db.execute(
                "CREATE TABLE IF NOT EXISTS shop_schema_migrations("
                "version INTEGER PRIMARY KEY,applied_at TEXT NOT NULL)"
            )
            # Each migration rechecks its marker only after BEGIN IMMEDIATE.
            # This is required because the public and private services may
            # start concurrently against the same SQLite database.
            self._migrate_applications(db)
            self._migrate_products(db)
            self._migrate_product_change_requests(db)
            self._migrate_product_variants(db)
            check = db.execute("PRAGMA foreign_key_check").fetchall()
            if check:
                raise RuntimeError("Shop migration failed foreign key validation")

    @staticmethod
    def _application_table_sql(name: str) -> str:
        if name not in {"vendor_applications", "vendor_applications_v2"}:
            raise ValueError("invalid migration table name")
        statuses = ",".join(f"'{status}'" for status in APPLICATION_STATUSES)
        return f"""
            CREATE TABLE {name}(
              id TEXT PRIMARY KEY,
              submitted_by_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              shop_name TEXT NOT NULL,
              owner_name TEXT NOT NULL,
              email TEXT,
              phone TEXT,
              category TEXT NOT NULL,
              description TEXT NOT NULL,
              address TEXT NOT NULL,
              city TEXT NOT NULL,
              state TEXT NOT NULL,
              pincode TEXT NOT NULL,
              business_information TEXT,
              status TEXT NOT NULL DEFAULT 'DRAFT' CHECK(status IN ({statuses})),
              rejection_reason TEXT,
              suspension_reason TEXT,
              reviewed_by TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              submitted_at TEXT,
              reviewed_at TEXT,
              approved_at TEXT,
              activated_at TEXT,
              suspended_at TEXT
            )
        """

    def _migrate_applications(self, db: sqlite3.Connection) -> None:
        now = iso(utc_now())
        db.execute("BEGIN IMMEDIATE")
        try:
            if db.execute(
                "SELECT 1 FROM shop_schema_migrations WHERE version=1"
            ).fetchone() is not None:
                db.commit()
                return
            existing = db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='vendor_applications'"
            ).fetchone()
            if existing is not None:
                duplicates = db.execute(
                    "SELECT submitted_by_user_id,COUNT(*) AS count "
                    "FROM vendor_applications GROUP BY submitted_by_user_id HAVING COUNT(*)>1"
                ).fetchall()
                if duplicates:
                    raise RuntimeError(
                        "Shop migration blocked: duplicate applications exist for "
                        f"{len(duplicates)} customer account(s)"
                    )
            if existing is None:
                db.execute(self._application_table_sql("vendor_applications"))
            else:
                db.execute(self._application_table_sql("vendor_applications_v2"))
                db.execute(
                    """
                    INSERT INTO vendor_applications_v2(
                      id,submitted_by_user_id,shop_name,owner_name,email,phone,
                      category,description,address,city,state,pincode,status,
                      reviewed_by,created_at,updated_at,submitted_at,reviewed_at,
                      approved_at
                    )
                    SELECT id,submitted_by_user_id,shop_name,owner_name,email,phone,
                           category,description,address,'Neemuch','Madhya Pradesh',pincode,
                           CASE status
                             WHEN 'pending' THEN 'SUBMITTED'
                             WHEN 'approved' THEN 'APPROVED'
                             WHEN 'rejected' THEN 'REJECTED'
                             ELSE 'SUBMITTED'
                           END,
                           reviewed_by,created_at,updated_at,created_at,
                           CASE WHEN status IN ('approved','rejected') THEN updated_at END,
                           CASE WHEN status='approved' THEN updated_at END
                    FROM vendor_applications
                    """
                )
                db.execute("DROP TABLE vendor_applications")
                db.execute(
                    "ALTER TABLE vendor_applications_v2 RENAME TO vendor_applications"
                )
            db.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS vendor_application_customer_unique_idx "
                "ON vendor_applications(submitted_by_user_id)"
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS vendor_application_status_idx "
                "ON vendor_applications(status,updated_at)"
            )
            db.execute(
                "INSERT INTO shop_schema_migrations(version,applied_at) VALUES(1,?)",
                (now,),
            )
            db.commit()
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def _migrate_products(db: sqlite3.Connection) -> None:
        now = iso(utc_now())
        statuses = ",".join(f"'{status}'" for status in PRODUCT_STATUSES)
        db.execute("BEGIN IMMEDIATE")
        try:
            if db.execute(
                "SELECT 1 FROM shop_schema_migrations WHERE version=2"
            ).fetchone() is not None:
                db.commit()
                return
            db.execute(
                f"""
                CREATE TABLE IF NOT EXISTS shop_product_submissions(
                  id TEXT PRIMARY KEY,
                  slug TEXT NOT NULL UNIQUE,
                  application_id TEXT NOT NULL REFERENCES vendor_applications(id) ON DELETE CASCADE,
                  submitted_by_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                  name TEXT NOT NULL,
                  description TEXT NOT NULL,
                  brand TEXT,
                  department TEXT NOT NULL CHECK(department IN ('men','women','kids','unisex','footwear','accessories')),
                  category TEXT NOT NULL,
                  price_paise INTEGER NOT NULL CHECK(price_paise BETWEEN 100 AND 100000000),
                  original_price_paise INTEGER NOT NULL CHECK(original_price_paise BETWEEN 100 AND 100000000),
                  inventory INTEGER NOT NULL CHECK(inventory BETWEEN 0 AND 100000),
                  size TEXT NOT NULL,
                  colour_name TEXT NOT NULL,
                  colour_hex TEXT,
                  image_urls_json TEXT NOT NULL DEFAULT '[]',
                  attributes_json TEXT NOT NULL DEFAULT '{{}}',
                  status TEXT NOT NULL DEFAULT 'DRAFT' CHECK(status IN ({statuses})),
                  rejection_reason TEXT,
                  reviewed_by TEXT,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  submitted_at TEXT,
                  reviewed_at TEXT,
                  published_at TEXT
                )
                """
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS shop_products_customer_idx "
                "ON shop_product_submissions(submitted_by_user_id,updated_at)"
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS shop_products_public_idx "
                "ON shop_product_submissions(status,published_at)"
            )
            db.execute(
                "INSERT INTO shop_schema_migrations(version,applied_at) VALUES(2,?)",
                (now,),
            )
            db.commit()
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def _migrate_product_change_requests(db: sqlite3.Connection) -> None:
        now = iso(utc_now())
        actions = ",".join(f"'{action}'" for action in PRODUCT_CHANGE_ACTIONS)
        statuses = ",".join(f"'{status}'" for status in PRODUCT_CHANGE_STATUSES)
        db.execute("BEGIN IMMEDIATE")
        try:
            if db.execute(
                "SELECT 1 FROM shop_schema_migrations WHERE version=3"
            ).fetchone() is not None:
                db.commit()
                return
            db.execute(
                f"""
                CREATE TABLE IF NOT EXISTS shop_product_change_requests(
                  id TEXT PRIMARY KEY,
                  product_id TEXT NOT NULL REFERENCES shop_product_submissions(id) ON DELETE CASCADE,
                  application_id TEXT NOT NULL REFERENCES vendor_applications(id) ON DELETE CASCADE,
                  submitted_by_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                  action TEXT NOT NULL CHECK(action IN ({actions})),
                  payload_json TEXT,
                  status TEXT NOT NULL DEFAULT 'SUBMITTED' CHECK(status IN ({statuses})),
                  rejection_reason TEXT,
                  reviewed_by TEXT,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  submitted_at TEXT NOT NULL,
                  reviewed_at TEXT
                )
                """
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS shop_product_change_customer_idx "
                "ON shop_product_change_requests(submitted_by_user_id,updated_at)"
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS shop_product_change_admin_idx "
                "ON shop_product_change_requests(status,updated_at)"
            )
            db.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS shop_product_change_pending_idx "
                "ON shop_product_change_requests(product_id) "
                "WHERE status IN ('SUBMITTED','UNDER_REVIEW')"
            )
            db.execute(
                "INSERT INTO shop_schema_migrations(version,applied_at) VALUES(3,?)",
                (now,),
            )
            db.commit()
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def _migrate_product_variants(db: sqlite3.Connection) -> None:
        now = iso(utc_now())
        db.execute("BEGIN IMMEDIATE")
        try:
            # Historical production databases may already contain a version-4
            # marker from an older migration sequence while still lacking the
            # variants_json column. Treat the physical schema as authoritative
            # and repair it idempotently instead of trusting the marker alone.
            marker_exists = db.execute(
                "SELECT 1 FROM shop_schema_migrations WHERE version=4"
            ).fetchone() is not None
            columns = {row["name"] for row in db.execute(
                "PRAGMA table_info(shop_product_submissions)"
            ).fetchall()}
            if "variants_json" not in columns:
                db.execute(
                    "ALTER TABLE shop_product_submissions "
                    "ADD COLUMN variants_json TEXT NOT NULL DEFAULT '[]'"
                )
            rows = db.execute(
                "SELECT id,size,inventory,variants_json FROM shop_product_submissions"
            ).fetchall()
            for row in rows:
                try:
                    existing = json.loads(row["variants_json"] or "[]")
                except (TypeError, json.JSONDecodeError):
                    existing = []
                if existing:
                    continue
                db.execute(
                    "UPDATE shop_product_submissions SET variants_json=? WHERE id=?",
                    (json.dumps([{"size": row["size"], "inventory": row["inventory"]}], separators=(",", ":")), row["id"]),
                )
            if not marker_exists:
                db.execute(
                    "INSERT INTO shop_schema_migrations(version,applied_at) VALUES(4,?)",
                    (now,),
                )
            db.commit()
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def _application_payload(
        payload: dict[str, Any],
        current: sqlite3.Row | None = None,
        *,
        require_complete: bool = False,
    ) -> dict[str, Any]:
        if not isinstance(payload, dict) or set(payload) - APPLICATION_PAYLOAD_FIELDS:
            raise SecurityError(
                400, "Unsupported shop application field.", "invalid_vendor_application"
            )

        def supplied(key: str, column: str) -> Any:
            if key in payload:
                return payload[key]
            return current[column] if current is not None else None

        def draft_text(
            key: str, column: str, label: str, minimum: int, maximum: int
        ) -> str:
            value = supplied(key, column)
            if not require_complete and (value is None or value == ""):
                return ""
            return clean_text(value, label, minimum, maximum)

        category = supplied("category", "category")
        if not require_complete and (category is None or category == ""):
            category = ""
        elif category not in ALLOWED_CATEGORIES:
            raise SecurityError(400, "Invalid store category.", "invalid_vendor_application")
        raw_pincode = supplied("pincode", "pincode")
        if not require_complete and (raw_pincode is None or raw_pincode == ""):
            pincode = ""
        else:
            pincode = clean_text(raw_pincode, "pincode", 6, 6)
        if pincode and not PINCODE_PATTERN.fullmatch(pincode):
            raise SecurityError(400, "Enter a valid pincode.", "invalid_pincode")
        return {
            "shop_name": draft_text("shopName", "shop_name", "store name", 2, 100),
            "owner_name": draft_text("ownerName", "owner_name", "owner name", 2, 80),
            "category": category,
            "description": draft_text(
                "description", "description", "description", 10, 1000
            ),
            "address": draft_text("address", "address", "address", 5, 250),
            "city": draft_text("city", "city", "city", 2, 80),
            "state": draft_text("state", "state", "state", 2, 80),
            "pincode": pincode,
            "business_information": _optional_text(
                supplied("businessInformation", "business_information"),
                "business information",
                1000,
            ),
        }

    @staticmethod
    def _registered_customer(db: sqlite3.Connection, user_id: str) -> sqlite3.Row:
        user = db.execute(
            "SELECT id,email,phone,name,is_active FROM users WHERE id=?", (user_id,)
        ).fetchone()
        if user is None:
            raise SecurityError(404, "Customer not found.", "customer_not_found")
        if not user["is_active"]:
            raise SecurityError(403, "Customer account is disabled.", "account_disabled")
        if not user["email"] and not user["phone"]:
            raise SecurityError(
                409,
                "Add a verified email address or mobile number before applying.",
                "registered_contact_required",
            )
        return user

    @staticmethod
    def _customer_application(db: sqlite3.Connection, user_id: str) -> sqlite3.Row | None:
        return db.execute(
            "SELECT * FROM vendor_applications WHERE submitted_by_user_id=?",
            (user_id,),
        ).fetchone()

    @staticmethod
    def _serialize_application(row: sqlite3.Row, *, admin: bool = False) -> dict[str, Any]:
        result = {
            "id": row["id"],
            "status": row["status"],
            "shopName": row["shop_name"],
            "ownerName": row["owner_name"],
            "registeredEmail": row["email"],
            "registeredMobile": row["phone"],
            "category": row["category"],
            "description": row["description"],
            "address": row["address"],
            "city": row["city"],
            "state": row["state"],
            "pincode": row["pincode"],
            "businessInformation": row["business_information"],
            "rejectionReason": row["rejection_reason"] if row["status"] == "REJECTED" else None,
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
            "submittedAt": row["submitted_at"],
            "approvedAt": row["approved_at"],
            "activatedAt": row["activated_at"],
        }
        if admin:
            result.update(
                {
                    "submittedByUserId": row["submitted_by_user_id"],
                    "reviewedBy": row["reviewed_by"],
                    "reviewedAt": row["reviewed_at"],
                    "suspensionReason": row["suspension_reason"],
                    "suspendedAt": row["suspended_at"],
                }
            )
        return result

    def get_application(self, user_id: str) -> dict[str, Any] | None:
        with self.connect() as db:
            row = self._customer_application(db, user_id)
        return self._serialize_application(row) if row is not None else None

    def create_draft(self, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        values = self._application_payload(payload)
        now = iso(utc_now())
        # Preserve the existing public identifier prefix for compatibility
        # with notifications and operational tooling.
        application_id = "vendor_" + secrets.token_hex(12)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            user = self._registered_customer(db, user_id)
            if self._customer_application(db, user_id) is not None:
                db.rollback()
                raise SecurityError(
                    409,
                    "A shop application already exists for this account.",
                    "vendor_application_exists",
                )
            try:
                db.execute(
                    """
                    INSERT INTO vendor_applications(
                      id,submitted_by_user_id,shop_name,owner_name,email,phone,
                      category,description,address,city,state,pincode,
                      business_information,status,created_at,updated_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,'DRAFT',?,?)
                    """,
                    (
                        application_id,
                        user_id,
                        values["shop_name"],
                        values["owner_name"],
                        user["email"],
                        user["phone"],
                        values["category"],
                        values["description"],
                        values["address"],
                        values["city"],
                        values["state"],
                        values["pincode"],
                        values["business_information"],
                        now,
                        now,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                db.rollback()
                raise SecurityError(
                    409,
                    "A shop application already exists for this account.",
                    "vendor_application_exists",
                ) from exc
            db.commit()
            row = db.execute(
                "SELECT * FROM vendor_applications WHERE id=?", (application_id,)
            ).fetchone()
        return self._serialize_application(row)

    def update_draft(self, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            user = self._registered_customer(db, user_id)
            current = self._customer_application(db, user_id)
            if current is None:
                db.rollback()
                raise SecurityError(404, "Shop application not found.", "vendor_application_not_found")
            if current["status"] not in {"DRAFT", "REJECTED"}:
                db.rollback()
                raise SecurityError(
                    409,
                    "This shop application cannot be edited in its current state.",
                    "invalid_vendor_transition",
                )
            values = self._application_payload(payload, current)
            now = iso(utc_now())
            db.execute(
                """
                UPDATE vendor_applications
                   SET shop_name=?,owner_name=?,email=?,phone=?,category=?,description=?,
                       address=?,city=?,state=?,pincode=?,business_information=?,
                       status='DRAFT',rejection_reason=NULL,reviewed_by=NULL,
                       reviewed_at=NULL,updated_at=?
                 WHERE id=? AND submitted_by_user_id=?
                """,
                (
                    values["shop_name"],
                    values["owner_name"],
                    user["email"],
                    user["phone"],
                    values["category"],
                    values["description"],
                    values["address"],
                    values["city"],
                    values["state"],
                    values["pincode"],
                    values["business_information"],
                    now,
                    current["id"],
                    user_id,
                ),
            )
            db.commit()
            row = db.execute(
                "SELECT * FROM vendor_applications WHERE id=?", (current["id"],)
            ).fetchone()
        return self._serialize_application(row)

    def submit_application(self, user_id: str) -> dict[str, Any]:
        now = iso(utc_now())
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            current = self._customer_application(db, user_id)
            if current is None:
                db.rollback()
                raise SecurityError(404, "Shop application not found.", "vendor_application_not_found")
            if current["status"] not in {"DRAFT", "REJECTED"}:
                db.rollback()
                raise SecurityError(
                    409,
                    "This shop application cannot be submitted in its current state.",
                    "invalid_vendor_transition",
                )
            # Drafts may be saved incrementally, but submission is the trust
            # boundary: every required business field must be valid here.
            self._application_payload({}, current, require_complete=True)
            db.execute(
                """
                UPDATE vendor_applications
                   SET status='SUBMITTED',submitted_at=?,updated_at=?,
                       rejection_reason=NULL,reviewed_by=NULL,reviewed_at=NULL
                 WHERE id=? AND submitted_by_user_id=?
                """,
                (now, now, current["id"], user_id),
            )
            db.commit()
            row = db.execute(
                "SELECT * FROM vendor_applications WHERE id=?", (current["id"],)
            ).fetchone()
        return self._serialize_application(row)

    def admin_create_application(
        self, admin_id: str, user_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        values = self._application_payload(payload, require_complete=True)
        application_id = "vendor_" + secrets.token_hex(12)
        now = iso(utc_now())
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._require_admin(db, admin_id)
            user = self._registered_customer(db, user_id)
            if self._customer_application(db, user_id) is not None:
                db.rollback()
                raise SecurityError(409, "A shop already exists for this owner account.", "vendor_application_exists")
            db.execute(
                """
                INSERT INTO vendor_applications(
                  id,submitted_by_user_id,shop_name,owner_name,email,phone,
                  category,description,address,city,state,pincode,business_information,
                  status,reviewed_by,created_at,updated_at,submitted_at,reviewed_at,
                  approved_at,activated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,'ACTIVE',?,?,?,?,?,?,?)
                """,
                (
                    application_id, user_id, values["shop_name"], values["owner_name"],
                    user["email"], user["phone"], values["category"], values["description"],
                    values["address"], values["city"], values["state"], values["pincode"],
                    values["business_information"], admin_id, now, now, now, now, now, now,
                ),
            )
            self._audit_if_available(
                db, admin_id, "shop_admin_created", "shop_application", application_id,
                {"ownerUserId": user_id, "status": "ACTIVE"},
            )
            db.commit()
            row = db.execute(
                "SELECT * FROM vendor_applications WHERE id=?", (application_id,)
            ).fetchone()
        return self._serialize_application(row, admin=True)

    def admin_list_applications(self, admin_id: str) -> list[dict[str, Any]]:
        with self.connect() as db:
            self._require_admin(db, admin_id)
            rows = db.execute(
                "SELECT * FROM vendor_applications ORDER BY updated_at DESC LIMIT 500"
            ).fetchall()
        return [self._serialize_application(row, admin=True) for row in rows]

    def admin_transition_application(
        self,
        admin_id: str,
        application_id: str,
        target_status: Any,
        reason: Any = None,
    ) -> dict[str, Any]:
        if not isinstance(target_status, str):
            raise SecurityError(400, "Invalid shop status.", "invalid_vendor_status")
        target = target_status.strip().upper()
        now = iso(utc_now())
        clean_reason = _optional_text(reason, "review reason", 1000)
        if target == "REJECTED" and clean_reason is None:
            raise SecurityError(400, "A rejection reason is required.", "rejection_reason_required")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._require_admin(db, admin_id)
            current = db.execute(
                "SELECT * FROM vendor_applications WHERE id=?", (application_id,)
            ).fetchone()
            if current is None:
                db.rollback()
                raise SecurityError(404, "Shop application not found.", "vendor_application_not_found")
            if target not in APPLICATION_ADMIN_TRANSITIONS.get(current["status"], set()):
                db.rollback()
                raise SecurityError(
                    409,
                    "Shop application transition is not allowed.",
                    "invalid_vendor_transition",
                )
            rejection_reason = clean_reason if target == "REJECTED" else None
            suspension_reason = clean_reason if target == "SUSPENDED" else None
            db.execute(
                """
                UPDATE vendor_applications
                   SET status=?,rejection_reason=?,suspension_reason=?,reviewed_by=?,
                       reviewed_at=?,updated_at=?,
                       approved_at=CASE WHEN ?='APPROVED' THEN ? ELSE approved_at END,
                       activated_at=CASE WHEN ?='ACTIVE' THEN ? ELSE activated_at END,
                       suspended_at=CASE WHEN ?='SUSPENDED' THEN ? ELSE suspended_at END
                 WHERE id=?
                """,
                (
                    target,
                    rejection_reason,
                    suspension_reason,
                    admin_id,
                    now,
                    now,
                    target,
                    now,
                    target,
                    now,
                    target,
                    now,
                    application_id,
                ),
            )
            self._audit_if_available(
                db,
                admin_id,
                f"shop_{target.casefold()}",
                "shop_application",
                application_id,
                {"from": current["status"], "to": target},
            )
            db.commit()
            row = db.execute(
                "SELECT * FROM vendor_applications WHERE id=?", (application_id,)
            ).fetchone()
        return self._serialize_application(row, admin=True)

    @staticmethod
    def _product_payload(
        payload: dict[str, Any],
        current: sqlite3.Row | None = None,
        *,
        allow_legacy_current_images: bool = False,
        trusted_variant_metadata: bool = False,
    ) -> dict[str, Any]:
        if not isinstance(payload, dict) or set(payload) - PRODUCT_PAYLOAD_FIELDS:
            raise SecurityError(400, "Unsupported product field.", "invalid_product")

        def supplied(key: str, column: str) -> Any:
            if key in payload:
                return payload[key]
            return current[column] if current is not None else None

        category = supplied("category", "category")
        if category not in ALLOWED_CATEGORIES:
            raise SecurityError(400, "Invalid product category.", "invalid_product")
        department = supplied("department", "department")
        if department not in DEPARTMENTS:
            raise SecurityError(400, "Invalid product department.", "invalid_product")
        price = supplied("pricePaise", "price_paise")
        original_price = supplied("originalPricePaise", "original_price_paise")
        if original_price is None:
            original_price = price
        if isinstance(price, bool) or not isinstance(price, int) or not 100 <= price <= 100_000_000:
            raise SecurityError(400, "Enter a valid product price.", "invalid_product")
        if (
            isinstance(original_price, bool)
            or not isinstance(original_price, int)
            or not price <= original_price <= 100_000_000
        ):
            raise SecurityError(400, "Enter a valid original price.", "invalid_product")

        variants_value = payload.get("variants") if "variants" in payload else None
        current_variants = _row_variants(current) if current is not None else []
        variants_from_current = variants_value is None and current is not None
        legacy_variant_change = "inventory" in payload or (
            "size" in payload and (len([item for item in current_variants if item.get("active", True)]) <= 1 or payload.get("size") != current["size"])
        )
        if variants_value is not None and legacy_variant_change:
            raise SecurityError(400, "Use either variants or legacy size/inventory fields.", "invalid_product")
        if variants_value is None and current is not None and not legacy_variant_change:
            variants_value = current_variants
        elif variants_value is None:
            variants_value = [{
                "size": supplied("size", "size"),
                "inventory": supplied("inventory", "inventory"),
            }]
        max_rows = 60 if trusted_variant_metadata or variants_from_current else 20
        if not isinstance(variants_value, list) or not 1 <= len(variants_value) <= max_rows:
            raise SecurityError(400, "Add between 1 and 20 active size variants.", "invalid_product")
        clean_variants: list[dict[str, Any]] = []
        seen_sizes: set[str] = set()
        seen_ids: set[str] = set()
        total_inventory = 0
        active_count = 0
        metadata_allowed = trusted_variant_metadata or variants_from_current
        for item in variants_value:
            allowed_fields = {"size", "inventory", "id", "active"} if metadata_allowed else {"size", "inventory"}
            if not isinstance(item, dict) or set(item) - allowed_fields:
                raise SecurityError(400, "Enter valid size inventory rows.", "invalid_product")
            size = clean_text(item.get("size"), "size", 1, 40)
            inventory = item.get("inventory")
            if isinstance(inventory, bool) or not isinstance(inventory, int) or not 0 <= inventory <= 100_000:
                raise SecurityError(400, "Enter valid product inventory.", "invalid_product")
            active = item.get("active", True) if metadata_allowed else True
            if not isinstance(active, bool):
                raise SecurityError(400, "Enter valid size inventory rows.", "invalid_product")
            variant_id = item.get("id") if metadata_allowed else None
            if metadata_allowed:
                if variant_id is not None and (
                    not isinstance(variant_id, str) or not variant_id.strip() or len(variant_id) > 128
                ):
                    raise SecurityError(400, "Enter valid size inventory rows.", "invalid_product")
                variant_id = variant_id.strip() if isinstance(variant_id, str) else "shopvar_" + secrets.token_hex(12)
                if variant_id in seen_ids:
                    raise SecurityError(400, "Duplicate product variant identity.", "invalid_product")
                seen_ids.add(variant_id)
            if active:
                key = size.casefold()
                if key in seen_sizes:
                    raise SecurityError(400, "Each active size can appear only once.", "invalid_product")
                seen_sizes.add(key)
                active_count += 1
                total_inventory += inventory
            clean = {"size": size, "inventory": inventory}
            if metadata_allowed:
                clean.update({"id": variant_id, "active": active})
            clean_variants.append(clean)
        if not 1 <= active_count <= 20:
            raise SecurityError(400, "Add between 1 and 20 active size variants.", "invalid_product")
        if total_inventory > 100_000:
            raise SecurityError(400, "Total active product inventory cannot exceed 100000.", "invalid_product")
        size_summary = ", ".join(item["size"] for item in clean_variants if item.get("active", True))

        raw_colour_hex = supplied("colourHex", "colour_hex")
        colour_hex = _optional_text(raw_colour_hex, "colour", 7)
        if colour_hex is not None and not COLOUR_HEX_PATTERN.fullmatch(colour_hex):
            raise SecurityError(400, "Enter a valid colour.", "invalid_product")

        image_value = payload.get("imageUrls") if "imageUrls" in payload else None
        preserving_current_images = image_value is None and current is not None
        if preserving_current_images:
            image_urls = json.loads(current["image_urls_json"])
        else:
            image_urls = image_value
        if not isinstance(image_urls, list) or len(image_urls) > 8:
            raise SecurityError(400, "Enter valid product images.", "invalid_product")
        clean_images: list[str] = []
        has_uploaded_image = any(
            isinstance(value, str) and PRODUCT_MEDIA_PATH_PATTERN.fullmatch(value)
            for value in image_urls
        )
        for value in image_urls:
            if not isinstance(value, str) or len(value) > 500:
                raise SecurityError(400, "Enter valid product images.", "invalid_product")
            if PRODUCT_MEDIA_PATH_PATTERN.fullmatch(value):
                clean_images.append(value)
                continue
            parsed = urlsplit(value)
            if (
                parsed.scheme != "https"
                or not parsed.netloc
                or re.search(r"\.html?$", parsed.path, re.IGNORECASE)
            ):
                # Older published products can contain webpage URLs that were
                # accepted before direct-image validation existed. If the seller
                # has supplied a new uploaded Vibe4You image, silently discard
                # only those legacy invalid URL strings so stale browser state
                # cannot block a legitimate repair edit.
                if has_uploaded_image:
                    continue
                if allow_legacy_current_images and preserving_current_images:
                    clean_images.append(value)
                    continue
                raise SecurityError(
                    400,
                    "Product image links must point directly to an HTTPS image, not a webpage, or use an uploaded Vibe4You image.",
                    "invalid_product",
                )
            clean_images.append(value)

        attributes_value = payload.get("attributes") if "attributes" in payload else None
        if attributes_value is None and current is not None:
            attributes = json.loads(current["attributes_json"])
        else:
            attributes = attributes_value if attributes_value is not None else {}
        if not isinstance(attributes, dict) or len(attributes) > 30:
            raise SecurityError(400, "Enter valid product attributes.", "invalid_product")

        clean_attributes: dict[str, str] = {}
        for key, value in attributes.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise SecurityError(400, "Enter valid product attributes.", "invalid_product")
            clean_attributes[clean_text(key, "attribute name", 1, 60)] = clean_text(
                value, "attribute value", 1, 200
            )

        return {
            "name": clean_text(supplied("name", "name"), "product name", 2, 140),
            "description": clean_text(
                supplied("description", "description"), "product description", 10, 2000
            ),
            "brand": _optional_text(supplied("brand", "brand"), "brand", 100),
            "department": department,
            "category": category,
            "price_paise": price,
            "original_price_paise": original_price,
            "inventory": total_inventory,
            "size": size_summary,
            "variants_json": json.dumps(clean_variants, separators=(",", ":")),
            "colour_name": clean_text(
                supplied("colourName", "colour_name"), "colour name", 1, 80
            ),
            "colour_hex": colour_hex,
            "image_urls_json": json.dumps(clean_images, separators=(",", ":")),
            "attributes_json": json.dumps(clean_attributes, separators=(",", ":"), sort_keys=True),
        }

    @staticmethod
    def _seller_application(db: sqlite3.Connection, user_id: str) -> sqlite3.Row:
        application = db.execute(
            "SELECT * FROM vendor_applications WHERE submitted_by_user_id=?", (user_id,)
        ).fetchone()
        if application is None or application["status"] not in {"APPROVED", "ACTIVE"}:
            raise SecurityError(
                403,
                "An approved shop is required before submitting products.",
                "approved_shop_required",
            )
        return application

    @staticmethod
    def _serialize_product(row: sqlite3.Row, *, admin: bool = False) -> dict[str, Any]:
        variants = [
            {"id": item["id"], "size": item["size"], "inventory": item["inventory"]}
            for item in _row_variants(row) if item.get("active", True)
        ]
        result = {
            "id": row["id"],
            "slug": row["slug"],
            "applicationId": row["application_id"],
            "name": row["name"],
            "description": row["description"],
            "brand": row["brand"],
            "department": row["department"],
            "category": row["category"],
            "pricePaise": row["price_paise"],
            "originalPricePaise": row["original_price_paise"],
            "inventory": sum(item["inventory"] for item in variants),
            "size": ", ".join(item["size"] for item in variants),
            "variants": variants,
            "colourName": row["colour_name"],
            "colourHex": row["colour_hex"],
            "imageUrls": json.loads(row["image_urls_json"]),
            "attributes": json.loads(row["attributes_json"]),
            "status": row["status"],
            "rejectionReason": row["rejection_reason"] if row["status"] == "REJECTED" else None,
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
            "submittedAt": row["submitted_at"],
            "publishedAt": row["published_at"],
        }
        if admin:
            result.update(
                {
                    "submittedByUserId": row["submitted_by_user_id"],
                    "reviewedBy": row["reviewed_by"],
                    "reviewedAt": row["reviewed_at"],
                }
            )
        return result

    @staticmethod
    def _product_values_to_change_payload(values: dict[str, Any]) -> dict[str, Any]:
        return {
            "name": values["name"],
            "description": values["description"],
            "brand": values["brand"],
            "department": values["department"],
            "category": values["category"],
            "pricePaise": values["price_paise"],
            "originalPricePaise": values["original_price_paise"],
            "variants": json.loads(values["variants_json"]),
            "colourName": values["colour_name"],
            "colourHex": values["colour_hex"],
            "imageUrls": json.loads(values["image_urls_json"]),
            "attributes": json.loads(values["attributes_json"]),
        }

    @staticmethod
    def _serialize_change_request(
        row: sqlite3.Row, *, admin: bool = False
    ) -> dict[str, Any]:
        result = {
            "id": row["id"],
            "productId": row["product_id"],
            "applicationId": row["application_id"],
            "action": row["action"],
            "status": row["status"],
            "proposedProduct": (
                json.loads(row["payload_json"]) if row["payload_json"] else None
            ),
            "rejectionReason": (
                row["rejection_reason"] if row["status"] == "REJECTED" else None
            ),
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
            "submittedAt": row["submitted_at"],
            "reviewedAt": row["reviewed_at"],
        }
        if "product_name" in row.keys():
            result["productName"] = row["product_name"]
        if "shop_name" in row.keys():
            result["shopName"] = row["shop_name"]
        if admin:
            result.update(
                {
                    "submittedByUserId": row["submitted_by_user_id"],
                    "reviewedBy": row["reviewed_by"],
                }
            )
        return result

    def _seller_published_product(
        self, db: sqlite3.Connection, user_id: str, product_id: str
    ) -> sqlite3.Row:
        application = self._seller_application(db, user_id)
        if application["status"] != "ACTIVE":
            raise SecurityError(
                403,
                "An active shop is required to manage a live product.",
                "active_shop_required",
            )
        current = db.execute(
            "SELECT * FROM shop_product_submissions "
            "WHERE id=? AND submitted_by_user_id=?",
            (product_id, user_id),
        ).fetchone()
        if current is None:
            raise SecurityError(404, "Product submission not found.", "product_not_found")
        if current["status"] != "PUBLISHED":
            raise SecurityError(
                409,
                "A published product is required for this action.",
                "published_product_required",
            )
        return current

    @staticmethod
    def _product_slug(name: str, product_id: str) -> str:
        stem = re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-")[:80]
        return f"{stem or 'local-product'}-{product_id[-12:]}"

    def list_products(self, user_id: str) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT * FROM shop_product_submissions "
                "WHERE submitted_by_user_id=? ORDER BY updated_at DESC",
                (user_id,),
            ).fetchall()
        return [self._serialize_product(row) for row in rows]

    def create_product_draft(self, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        values = self._product_payload(payload)
        now = iso(utc_now())
        product_id = "shopprod_" + secrets.token_hex(12)
        slug = self._product_slug(values["name"], product_id)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            application = self._seller_application(db, user_id)
            db.execute(
                """
                INSERT INTO shop_product_submissions(
                  id,slug,application_id,submitted_by_user_id,name,description,brand,
                  department,category,price_paise,original_price_paise,inventory,
                  size,variants_json,colour_name,colour_hex,image_urls_json,attributes_json,status,
                  created_at,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'DRAFT',?,?)
                """,
                (
                    product_id,
                    slug,
                    application["id"],
                    user_id,
                    values["name"],
                    values["description"],
                    values["brand"],
                    values["department"],
                    values["category"],
                    values["price_paise"],
                    values["original_price_paise"],
                    values["inventory"],
                    values["size"],
                    values["variants_json"],
                    values["colour_name"],
                    values["colour_hex"],
                    values["image_urls_json"],
                    values["attributes_json"],
                    now,
                    now,
                ),
            )
            db.commit()
            row = db.execute(
                "SELECT * FROM shop_product_submissions WHERE id=?", (product_id,)
            ).fetchone()
        return self._serialize_product(row)

    def update_product_draft(
        self, user_id: str, product_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._seller_application(db, user_id)
            current = db.execute(
                "SELECT * FROM shop_product_submissions WHERE id=? AND submitted_by_user_id=?",
                (product_id, user_id),
            ).fetchone()
            if current is None:
                db.rollback()
                raise SecurityError(404, "Product submission not found.", "product_not_found")
            if current["status"] not in {"DRAFT", "REJECTED"}:
                db.rollback()
                raise SecurityError(
                    409,
                    "This product submission cannot be edited in its current state.",
                    "invalid_product_transition",
                )
            values = self._product_payload(payload, current)
            now = iso(utc_now())
            db.execute(
                """
                UPDATE shop_product_submissions
                   SET name=?,description=?,brand=?,department=?,category=?,price_paise=?,
                       original_price_paise=?,inventory=?,size=?,variants_json=?,colour_name=?,colour_hex=?,
                       image_urls_json=?,attributes_json=?,status='DRAFT',
                       rejection_reason=NULL,reviewed_by=NULL,reviewed_at=NULL,updated_at=?
                 WHERE id=? AND submitted_by_user_id=?
                """,
                (
                    values["name"],
                    values["description"],
                    values["brand"],
                    values["department"],
                    values["category"],
                    values["price_paise"],
                    values["original_price_paise"],
                    values["inventory"],
                    values["size"],
                    values["variants_json"],
                    values["colour_name"],
                    values["colour_hex"],
                    values["image_urls_json"],
                    values["attributes_json"],
                    now,
                    product_id,
                    user_id,
                ),
            )
            db.commit()
            row = db.execute(
                "SELECT * FROM shop_product_submissions WHERE id=?", (product_id,)
            ).fetchone()
        return self._serialize_product(row)

    def submit_product(self, user_id: str, product_id: str) -> dict[str, Any]:
        now = iso(utc_now())
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._seller_application(db, user_id)
            current = db.execute(
                "SELECT * FROM shop_product_submissions WHERE id=? AND submitted_by_user_id=?",
                (product_id, user_id),
            ).fetchone()
            if current is None:
                db.rollback()
                raise SecurityError(404, "Product submission not found.", "product_not_found")
            if current["status"] not in {"DRAFT", "REJECTED"}:
                db.rollback()
                raise SecurityError(
                    409,
                    "This product submission cannot be submitted in its current state.",
                    "invalid_product_transition",
                )
            if not json.loads(current["image_urls_json"]):
                db.rollback()
                raise SecurityError(
                    400,
                    "Add at least one product image before submission.",
                    "product_image_required",
                )
            db.execute(
                """
                UPDATE shop_product_submissions
                   SET status='SUBMITTED',submitted_at=?,updated_at=?,
                       rejection_reason=NULL,reviewed_by=NULL,reviewed_at=NULL
                 WHERE id=? AND submitted_by_user_id=?
                """,
                (now, now, product_id, user_id),
            )
            db.commit()
            row = db.execute(
                "SELECT * FROM shop_product_submissions WHERE id=?", (product_id,)
            ).fetchone()
        return self._serialize_product(row)

    def admin_create_product(
        self, admin_id: str, application_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        values = self._product_payload(payload)
        product_id = "shopprod_" + secrets.token_hex(12)
        slug = self._product_slug(values["name"], product_id)
        now = iso(utc_now())
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._require_admin(db, admin_id)
            application = db.execute(
                "SELECT * FROM vendor_applications WHERE id=?", (application_id,)
            ).fetchone()
            if application is None:
                db.rollback()
                raise SecurityError(404, "Shop application not found.", "vendor_application_not_found")
            if application["status"] != "ACTIVE":
                db.rollback()
                raise SecurityError(409, "Activate the shop before publishing products.", "active_shop_required")
            if not json.loads(values["image_urls_json"]):
                db.rollback()
                raise SecurityError(400, "Add at least one product image.", "product_image_required")
            db.execute(
                """
                INSERT INTO shop_product_submissions(
                  id,slug,application_id,submitted_by_user_id,name,description,brand,
                  department,category,price_paise,original_price_paise,inventory,size,
                  variants_json,colour_name,colour_hex,image_urls_json,attributes_json,
                  status,reviewed_by,created_at,updated_at,submitted_at,reviewed_at,published_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'PUBLISHED',?,?,?,?,?,?)
                """,
                (
                    product_id, slug, application_id, application["submitted_by_user_id"],
                    values["name"], values["description"], values["brand"], values["department"],
                    values["category"], values["price_paise"], values["original_price_paise"],
                    values["inventory"], values["size"], values["variants_json"],
                    values["colour_name"], values["colour_hex"], values["image_urls_json"],
                    values["attributes_json"], admin_id, now, now, now, now, now,
                ),
            )
            self._audit_if_available(
                db, admin_id, "shop_product_admin_created", "shop_product", product_id,
                {"applicationId": application_id, "status": "PUBLISHED"},
            )
            db.commit()
            row = db.execute(
                "SELECT * FROM shop_product_submissions WHERE id=?", (product_id,)
            ).fetchone()
        return self._serialize_product(row, admin=True)

    def admin_update_product(
        self, admin_id: str, product_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._require_admin(db, admin_id)
            current = db.execute(
                "SELECT * FROM shop_product_submissions WHERE id=?", (product_id,)
            ).fetchone()
            if current is None:
                db.rollback()
                raise SecurityError(404, "Product submission not found.", "product_not_found")
            if current["status"] == "PUBLISHED" and ({"variants", "inventory", "size"} & set(payload)):
                db.rollback()
                raise SecurityError(
                    409,
                    "Unpublish this product before changing its size structure. Live stock can be edited from Inventory.",
                    "live_variant_change_blocked",
                )
            values = self._product_payload(payload, current)
            now = iso(utc_now())
            db.execute(
                """
                UPDATE shop_product_submissions
                   SET name=?,description=?,brand=?,department=?,category=?,price_paise=?,
                       original_price_paise=?,inventory=?,size=?,variants_json=?,colour_name=?,
                       colour_hex=?,image_urls_json=?,attributes_json=?,reviewed_by=?,reviewed_at=?,updated_at=?
                 WHERE id=?
                """,
                (
                    values["name"], values["description"], values["brand"], values["department"],
                    values["category"], values["price_paise"], values["original_price_paise"],
                    values["inventory"], values["size"], values["variants_json"], values["colour_name"],
                    values["colour_hex"], values["image_urls_json"], values["attributes_json"],
                    admin_id, now, now, product_id,
                ),
            )
            self._audit_if_available(
                db, admin_id, "shop_product_admin_updated", "shop_product", product_id,
                {"status": current["status"]},
            )
            db.commit()
            row = db.execute(
                "SELECT * FROM shop_product_submissions WHERE id=?", (product_id,)
            ).fetchone()
        return self._serialize_product(row, admin=True)

    def admin_list_products(self, admin_id: str) -> list[dict[str, Any]]:
        with self.connect() as db:
            self._require_admin(db, admin_id)
            rows = db.execute(
                "SELECT * FROM shop_product_submissions ORDER BY updated_at DESC LIMIT 1000"
            ).fetchall()
        return [self._serialize_product(row, admin=True) for row in rows]

    def admin_transition_product(
        self,
        admin_id: str,
        product_id: str,
        target_status: Any,
        reason: Any = None,
    ) -> dict[str, Any]:
        if not isinstance(target_status, str):
            raise SecurityError(400, "Invalid product status.", "invalid_product_status")
        target = target_status.strip().upper()
        clean_reason = _optional_text(reason, "review reason", 1000)
        if target == "REJECTED" and clean_reason is None:
            raise SecurityError(400, "A rejection reason is required.", "rejection_reason_required")
        now = iso(utc_now())
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._require_admin(db, admin_id)
            current = db.execute(
                "SELECT * FROM shop_product_submissions WHERE id=?", (product_id,)
            ).fetchone()
            if current is None:
                db.rollback()
                raise SecurityError(404, "Product submission not found.", "product_not_found")
            if target not in PRODUCT_ADMIN_TRANSITIONS.get(current["status"], set()):
                db.rollback()
                raise SecurityError(
                    409,
                    "Product transition is not allowed.",
                    "invalid_product_transition",
                )
            if target == "PUBLISHED" and not json.loads(current["image_urls_json"]):
                db.rollback()
                raise SecurityError(
                    409,
                    "A product image is required before publication.",
                    "product_image_required",
                )
            db.execute(
                """
                UPDATE shop_product_submissions
                   SET status=?,rejection_reason=?,reviewed_by=?,reviewed_at=?,updated_at=?,
                       published_at=CASE
                         WHEN ?='PUBLISHED' THEN ?
                         WHEN ?='APPROVED' THEN NULL
                         ELSE published_at
                       END
                 WHERE id=?
                """,
                (
                    target,
                    clean_reason if target == "REJECTED" else None,
                    admin_id,
                    now,
                    now,
                    target,
                    now,
                    target,
                    product_id,
                ),
            )
            self._audit_if_available(
                db,
                admin_id,
                f"shop_product_{target.casefold()}",
                "shop_product",
                product_id,
                {"from": current["status"], "to": target},
            )
            db.commit()
            row = db.execute(
                "SELECT * FROM shop_product_submissions WHERE id=?", (product_id,)
            ).fetchone()
        return self._serialize_product(row, admin=True)

    def require_seller_published_product(
        self, user_id: str, product_id: str
    ) -> dict[str, Any]:
        with self.connect() as db:
            row = self._seller_published_product(db, user_id, product_id)
        return self._serialize_product(row)

    def require_seller_stock_update_allowed(
        self, user_id: str, product_id: str
    ) -> dict[str, Any]:
        with self.connect() as db:
            row = self._seller_published_product(db, user_id, product_id)
            pending = db.execute(
                "SELECT 1 FROM shop_product_change_requests "
                "WHERE product_id=? AND status IN ('SUBMITTED','UNDER_REVIEW')",
                (product_id,),
            ).fetchone()
            if pending is not None:
                raise SecurityError(
                    409,
                    "Finish the pending product change review before updating stock.",
                    "product_change_pending",
                )
        return self._serialize_product(row)

    def list_product_change_requests(self, user_id: str) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute(
                """
                SELECT r.*,p.name AS product_name
                  FROM shop_product_change_requests r
                  JOIN shop_product_submissions p ON p.id=r.product_id
                 WHERE r.submitted_by_user_id=?
                 ORDER BY r.updated_at DESC
                """,
                (user_id,),
            ).fetchall()
        return [self._serialize_change_request(row) for row in rows]

    def _create_product_change_request(
        self,
        user_id: str,
        product_id: str,
        action: str,
        payload: dict[str, Any] | None = None,
        live_inventory: dict[str, int] | None = None,
    ) -> dict[str, Any]:
        now = iso(utc_now())
        request_id = "shopchg_" + secrets.token_hex(12)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            current = self._seller_published_product(db, user_id, product_id)
            pending = db.execute(
                "SELECT id FROM shop_product_change_requests "
                "WHERE product_id=? AND status IN ('SUBMITTED','UNDER_REVIEW')",
                (product_id,),
            ).fetchone()
            if pending is not None:
                db.rollback()
                raise SecurityError(
                    409,
                    "A product change request is already pending.",
                    "product_change_pending",
                )

            if action == "EDIT":
                if (
                    not isinstance(payload, dict)
                    or set(payload) - PRODUCT_CHANGE_PAYLOAD_FIELDS
                ):
                    db.rollback()
                    raise SecurityError(
                        400,
                        "Unsupported product change field.",
                        "invalid_product_change",
                    )
                candidate = dict(payload)
                if "variants" in candidate:
                    proposed_variants = candidate["variants"]
                    current_variants = _row_variants(current)
                    current_by_id = {item["id"]: item for item in current_variants}
                    active_current = [item for item in current_variants if item.get("active", True)]
                    if not isinstance(proposed_variants, list):
                        db.rollback()
                        raise SecurityError(400, "Enter valid size inventory rows.", "invalid_product_change")
                    normalized_active: list[dict[str, Any]] = []
                    retained_ids: set[str] = set()
                    for item in proposed_variants:
                        if not isinstance(item, dict) or set(item) - {"id", "size", "inventory"}:
                            db.rollback()
                            raise SecurityError(400, "Enter valid size inventory rows.", "invalid_product_change")
                        variant_id = item.get("id")
                        if variant_id is None:
                            normalized_active.append({"size": item.get("size"), "inventory": item.get("inventory")})
                            continue
                        existing = current_by_id.get(variant_id) if isinstance(variant_id, str) else None
                        if existing is None or not existing.get("active", True) or variant_id in retained_ids:
                            db.rollback()
                            raise SecurityError(400, "Invalid published size selection.", "invalid_product_change")
                        requested_size = clean_text(item.get("size"), "size", 1, 40)
                        if requested_size != existing["size"]:
                            db.rollback()
                            raise SecurityError(
                                409,
                                "Published size labels cannot be renamed in place. Set its stock to 0, remove that size, then add the corrected size.",
                                "published_variant_rename_blocked",
                            )
                        retained_ids.add(variant_id)
                        stock = (live_inventory or {}).get(variant_id, existing["inventory"])
                        normalized_active.append({"id": variant_id, "size": existing["size"], "inventory": stock, "active": True})
                    retired: list[dict[str, Any]] = []
                    for existing in active_current:
                        if existing["id"] in retained_ids:
                            continue
                        stock = (live_inventory or {}).get(existing["id"], existing["inventory"])
                        if stock != 0:
                            db.rollback()
                            raise SecurityError(
                                409,
                                f"Set stock for size {existing['size']} to 0 before removing it.",
                                "published_variant_has_stock",
                            )
                        retired.append({"id": existing["id"], "size": existing["size"], "inventory": 0, "active": False})
                    retired.extend(
                        {"id": item["id"], "size": item["size"], "inventory": 0, "active": False}
                        for item in current_variants if not item.get("active", True)
                    )
                    candidate["variants"] = normalized_active + retired
                values = self._product_payload(candidate, current, trusted_variant_metadata="variants" in candidate)
                if not json.loads(values["image_urls_json"]):
                    db.rollback()
                    raise SecurityError(
                        400,
                        "A product image is required for a published listing.",
                        "product_image_required",
                    )
                proposed = self._product_values_to_change_payload(values)
                compare_payload: dict[str, Any] = {}
                if "variants" in candidate:
                    compare_payload["variants"] = [
                        {
                            "id": item["id"],
                            "size": item["size"],
                            "inventory": (live_inventory or {}).get(item["id"], item["inventory"]) if item.get("active", True) else 0,
                            "active": item.get("active", True),
                        }
                        for item in _row_variants(current)
                    ]
                current_values = self._product_values_to_change_payload(
                    self._product_payload(
                        compare_payload,
                        current,
                        allow_legacy_current_images=True,
                        trusted_variant_metadata=bool(compare_payload),
                    )
                )
                if proposed == current_values:
                    db.rollback()
                    raise SecurityError(
                        409,
                        "No catalogue changes were provided.",
                        "no_product_changes",
                    )
                payload_json = json.dumps(
                    proposed, separators=(",", ":"), sort_keys=True
                )
            elif action == "UNPUBLISH":
                if payload not in (None, {}):
                    db.rollback()
                    raise SecurityError(
                        400,
                        "Unpublish requests do not accept product fields.",
                        "invalid_product_change",
                    )
                payload_json = None
            else:
                db.rollback()
                raise SecurityError(
                    400, "Invalid product change action.", "invalid_product_change"
                )

            db.execute(
                """
                INSERT INTO shop_product_change_requests(
                  id,product_id,application_id,submitted_by_user_id,action,
                  payload_json,status,created_at,updated_at,submitted_at
                ) VALUES(?,?,?,?,?,?,'SUBMITTED',?,?,?)
                """,
                (
                    request_id,
                    product_id,
                    current["application_id"],
                    user_id,
                    action,
                    payload_json,
                    now,
                    now,
                    now,
                ),
            )
            db.commit()
            row = db.execute(
                "SELECT r.*,p.name AS product_name "
                "FROM shop_product_change_requests r "
                "JOIN shop_product_submissions p ON p.id=r.product_id "
                "WHERE r.id=?",
                (request_id,),
            ).fetchone()
        return self._serialize_change_request(row)

    def create_product_edit_request(
        self,
        user_id: str,
        product_id: str,
        payload: dict[str, Any],
        live_inventory: dict[str, int] | None = None,
    ) -> dict[str, Any]:
        return self._create_product_change_request(
            user_id, product_id, "EDIT", payload, live_inventory
        )

    def create_product_unpublish_request(
        self, user_id: str, product_id: str
    ) -> dict[str, Any]:
        return self._create_product_change_request(
            user_id, product_id, "UNPUBLISH"
        )

    def admin_list_product_change_requests(
        self, admin_id: str
    ) -> list[dict[str, Any]]:
        with self.connect() as db:
            self._require_admin(db, admin_id)
            rows = db.execute(
                """
                SELECT r.*,p.name AS product_name,a.shop_name AS shop_name
                  FROM shop_product_change_requests r
                  JOIN shop_product_submissions p ON p.id=r.product_id
                  JOIN vendor_applications a ON a.id=r.application_id
                 ORDER BY
                   CASE r.status
                     WHEN 'SUBMITTED' THEN 0
                     WHEN 'UNDER_REVIEW' THEN 1
                     ELSE 2
                   END,
                   r.updated_at DESC
                 LIMIT 1000
                """
            ).fetchall()
        return [self._serialize_change_request(row, admin=True) for row in rows]

    def admin_transition_product_change_request(
        self,
        admin_id: str,
        request_id: str,
        target_status: Any,
        reason: Any = None,
    ) -> dict[str, Any]:
        if not isinstance(target_status, str):
            raise SecurityError(
                400, "Invalid product change status.", "invalid_product_change_status"
            )
        target = target_status.strip().upper()
        clean_reason = _optional_text(reason, "review reason", 1000)
        if target == "REJECTED" and clean_reason is None:
            raise SecurityError(
                400, "A rejection reason is required.", "rejection_reason_required"
            )

        now = iso(utc_now())
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._require_admin(db, admin_id)
            request = db.execute(
                "SELECT * FROM shop_product_change_requests WHERE id=?",
                (request_id,),
            ).fetchone()
            if request is None:
                db.rollback()
                raise SecurityError(
                    404, "Product change request not found.", "product_change_not_found"
                )
            if target not in PRODUCT_CHANGE_ADMIN_TRANSITIONS.get(
                request["status"], set()
            ):
                db.rollback()
                raise SecurityError(
                    409,
                    "Product change transition is not allowed.",
                    "invalid_product_change_transition",
                )

            if target == "APPROVED":
                current = db.execute(
                    "SELECT * FROM shop_product_submissions WHERE id=?",
                    (request["product_id"],),
                ).fetchone()
                if current is None or current["status"] != "PUBLISHED":
                    db.rollback()
                    raise SecurityError(
                        409,
                        "The product is no longer published.",
                        "published_product_required",
                    )
                if request["action"] == "EDIT":
                    proposed = json.loads(request["payload_json"] or "{}")
                    candidate = dict(proposed)
                    values = self._product_payload(
                        candidate, current, trusted_variant_metadata="variants" in candidate
                    )
                    if not json.loads(values["image_urls_json"]):
                        db.rollback()
                        raise SecurityError(
                            409,
                            "A product image is required before applying changes.",
                            "product_image_required",
                        )
                    db.execute(
                        """
                        UPDATE shop_product_submissions
                           SET name=?,description=?,brand=?,department=?,category=?,
                               price_paise=?,original_price_paise=?,inventory=?,size=?,variants_json=?,
                               colour_name=?,colour_hex=?,image_urls_json=?,attributes_json=?,
                               reviewed_by=?,reviewed_at=?,updated_at=?
                         WHERE id=?
                        """,
                        (
                            values["name"],
                            values["description"],
                            values["brand"],
                            values["department"],
                            values["category"],
                            values["price_paise"],
                            values["original_price_paise"],
                            values["inventory"],
                            values["size"],
                            values["variants_json"],
                            values["colour_name"],
                            values["colour_hex"],
                            values["image_urls_json"],
                            values["attributes_json"],
                            admin_id,
                            now,
                            now,
                            current["id"],
                        ),
                    )
                elif request["action"] == "UNPUBLISH":
                    db.execute(
                        """
                        UPDATE shop_product_submissions
                           SET status='APPROVED',published_at=NULL,
                               reviewed_by=?,reviewed_at=?,updated_at=?
                         WHERE id=?
                        """,
                        (admin_id, now, now, current["id"]),
                    )

            db.execute(
                """
                UPDATE shop_product_change_requests
                   SET status=?,rejection_reason=?,reviewed_by=?,reviewed_at=?,updated_at=?
                 WHERE id=?
                """,
                (
                    target,
                    clean_reason if target == "REJECTED" else None,
                    admin_id,
                    now,
                    now,
                    request_id,
                ),
            )
            self._audit_if_available(
                db,
                admin_id,
                f"shop_product_change_{target.casefold()}",
                "shop_product_change_request",
                request_id,
                {
                    "action": request["action"],
                    "productId": request["product_id"],
                    "from": request["status"],
                    "to": target,
                },
            )
            db.commit()
            row = db.execute(
                """
                SELECT r.*,p.name AS product_name,a.shop_name AS shop_name
                  FROM shop_product_change_requests r
                  JOIN shop_product_submissions p ON p.id=r.product_id
                  JOIN vendor_applications a ON a.id=r.application_id
                 WHERE r.id=?
                """,
                (request_id,),
            ).fetchone()
        return self._serialize_change_request(row, admin=True)

    def list_active_stores(self, limit: int = 200) -> list[dict[str, Any]]:
        """Return public-safe storefront metadata for ACTIVE shops only."""
        safe_limit = max(1, min(limit, 200))
        with self.connect() as db:
            rows = db.execute(
                """
                SELECT a.id,a.shop_name,a.category,a.description,a.address,a.city,a.pincode,
                       a.created_at,a.updated_at,
                       (SELECT p.image_urls_json FROM shop_product_submissions p
                         WHERE p.application_id=a.id AND p.status='PUBLISHED'
                         ORDER BY p.published_at DESC LIMIT 1) AS image_urls_json
                  FROM vendor_applications a
                 WHERE a.status='ACTIVE'
                 ORDER BY a.activated_at DESC,a.updated_at DESC
                 LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()
        stores: list[dict[str, Any]] = []
        for row in rows:
            images = json.loads(row["image_urls_json"]) if row["image_urls_json"] else []
            image = images[0] if images else None
            stores.append({
                "id": row["id"], "slug": _store_slug(row["id"]),
                "storeName": row["shop_name"], "category": row["category"],
                "description": row["description"], "address": row["address"],
                "city": row["city"], "pincode": row["pincode"],
                "deliveryMinutes": 60, "bannerImage": image, "logoImage": image,
                "active": True, "approved": True, "createdAt": row["created_at"],
            })
        return stores

    def _published_rows(self, limit: int) -> list[sqlite3.Row]:
        safe_limit = max(1, min(limit, 200))
        with self.connect() as db:
            rows = db.execute(
                """
                SELECT p.*,a.shop_name
                  FROM shop_product_submissions p
                  JOIN vendor_applications a ON a.id=p.application_id
                 WHERE p.status='PUBLISHED' AND a.status='ACTIVE'
                 ORDER BY p.published_at DESC
                 LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()
        return rows

    @staticmethod
    def _public_product(row: sqlite3.Row) -> dict[str, Any]:
        images = json.loads(row["image_urls_json"])
        attributes = json.loads(row["attributes_json"])
        price = row["price_paise"] / 100
        original_price = row["original_price_paise"] / 100
        discount = (
            round((original_price - price) * 100 / original_price)
            if original_price > price
            else 0
        )
        store_slug = _store_slug(row['application_id'])
        variants = []
        for index, item in enumerate(item for item in _row_variants(row) if item.get("active", True)):
            variant = {
                "id": item["id"],
                "sku": f"SD-SHOP-{row['id'][-12:].upper()}" if index == 0 else f"SD-SHOP-{row['id'][-12:].upper()}-{index + 1}",
                "size": item["size"],
                "colourName": row["colour_name"],
                "stock": item["inventory"],
                "available": False,
                "price": price,
                "images": images,
            }
            if row["colour_hex"]:
                variant["colourHex"] = row["colour_hex"]
            variants.append(variant)
        return {
            "id": row["id"],
            "slug": row["slug"],
            "name": row["name"],
            "brand": row["brand"] or row["shop_name"],
            "department": row["department"],
            "category": row["category"],
            "shortDescription": row["description"][:180],
            "description": row["description"],
            "material": attributes.get("material", "Not specified"),
            "careInstructions": [],
            "price": price,
            "originalPrice": original_price,
            "discount": discount,
            "images": images,
            "thumbnail": images[0],
            "rating": 0,
            "reviewCount": 0,
            "variants": variants,
            "tags": ["local-shop"],
            "badge": "Local Shop",
            "newArrival": True,
            "trending": False,
            "featured": False,
            "expressDelivery": False,
            "returnWindowDays": 0,
            "exchangeAvailable": False,
            "vendorId": row["application_id"],
            "storeName": row["shop_name"],
            "storeSlug": store_slug,
            "active": True,
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
        }

    def list_published_products(self, limit: int = 100) -> list[dict[str, Any]]:
        """Return customer-safe Product DTOs, never review/contact metadata."""
        return [self._public_product(row) for row in self._published_rows(limit)]

    def payment_catalog_products(self, limit: int = 5000) -> list[dict[str, Any]]:
        """Return minimal records compatible with PaymentService.products.

        The public server owns the atomic refresh into its in-memory catalogue;
        this method never writes catalogue JSON or payment state.
        """
        safe_limit = max(1, min(limit, 10_000))
        with self.connect() as db:
            rows = db.execute(
                """
                SELECT p.*,a.status AS shop_status
                  FROM shop_product_submissions p
                  JOIN vendor_applications a ON a.id=p.application_id
                 ORDER BY p.created_at
                 LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()
        products = []
        for row in rows:
            price = row["price_paise"] / 100
            products.append(
                {
                    "id": row["id"],
                    "name": row["name"],
                    "slug": row["slug"],
                    "vendorId": row["application_id"],
                    "active": row["status"] == "PUBLISHED" and row["shop_status"] == "ACTIVE",
                    "price": price,
                    "variants": [
                        {
                            "id": item["id"],
                            "sku": f"SD-SHOP-{row['id'][-12:].upper()}" if index == 0 else f"SD-SHOP-{row['id'][-12:].upper()}-{index + 1}",
                            "size": item["size"],
                            "colourName": row["colour_name"],
                            "stock": item["inventory"],
                            "price": price,
                            "active": item.get("active", True),
                        }
                        for index, item in enumerate(_row_variants(row))
                    ],
                }
            )
        return products

    @staticmethod
    def _require_admin(db: sqlite3.Connection, admin_id: str) -> None:
        has_admins = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='admin_users'"
        ).fetchone()
        if has_admins is None:
            raise SecurityError(
                403, "Administrator authorization required.", "admin_authorization_required"
            )
        admin = db.execute(
            "SELECT is_active FROM admin_users WHERE id=?", (admin_id,)
        ).fetchone()
        if admin is None or not admin["is_active"]:
            raise SecurityError(
                403, "Administrator authorization required.", "admin_authorization_required"
            )

    @staticmethod
    def _audit_if_available(
        db: sqlite3.Connection,
        admin_id: str,
        action: str,
        target_type: str,
        target_id: str,
        metadata: dict[str, Any],
    ) -> None:
        if db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='local_admin_audit_log'"
        ).fetchone() is None:
            return
        db.execute(
            """
            INSERT INTO local_admin_audit_log(
              admin_user_id,action,target_type,target_id,result,metadata_json,created_at
            ) VALUES(?,?,?,?,?,?,?)
            """,
            (
                admin_id,
                action,
                target_type,
                target_id,
                "success",
                json.dumps(metadata, separators=(",", ":"), sort_keys=True),
                iso(utc_now()),
            ),
        )
