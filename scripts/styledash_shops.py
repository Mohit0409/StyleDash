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
FULFILLMENT_STATUSES = ("NEW", "PROCESSING", "READY", "SHIPPED", "DELIVERED")
FULFILLMENT_TRANSITIONS = {
    "NEW": ("PROCESSING",),
    "PROCESSING": ("READY",),
    "READY": ("SHIPPED",),
    "SHIPPED": ("DELIVERED",),
    "DELIVERED": (),
}
RETURN_REQUEST_TYPES = ("SIZE_EXCHANGE", "ISSUE_RETURN")
RETURN_REQUEST_STATUSES = (
    "REQUESTED", "UNDER_REVIEW", "APPROVED", "REJECTED",
    "PICKUP_PENDING", "RECEIVED", "REFUND_PENDING", "REFUNDED",
    "EXCHANGED", "CANCELLED",
)
RETURN_REQUEST_REASONS = (
    "CUSTOMER_REQUEST", "ORDERED_BY_MISTAKE", "SIZE_ISSUE",
    "WRONG_ITEM", "DAMAGED", "DEFECTIVE", "MISSING_ITEM", "OTHER",
)
CARRIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9&().,'\/+ -]{1,79}$")
TRACKING_NUMBER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/# -]{1,119}$")
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
}
DEPARTMENTS = {"men", "women", "kids", "unisex", "footwear", "accessories"}
COLOUR_HEX_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _optional_text(value: Any, label: str, maximum: int) -> str | None:
    if value is None or value == "":
        return None
    return clean_text(value, label, 1, maximum)


def _row_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def _store_slug(application_id: str) -> str:
    return f"local-shop-{application_id[-12:]}"


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
            self._migrate_fulfillments(db)
            self._migrate_shipping_tracking(db)
            self._migrate_return_requests(db)
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
    def _migrate_fulfillments(db: sqlite3.Connection) -> None:
        now = iso(utc_now())
        statuses = ",".join(f"'{status}'" for status in FULFILLMENT_STATUSES)
        db.execute("BEGIN IMMEDIATE")
        try:
            if db.execute(
                "SELECT 1 FROM shop_schema_migrations WHERE version=4"
            ).fetchone() is not None:
                db.commit()
                return
            db.execute(
                f"""
                CREATE TABLE IF NOT EXISTS shop_order_fulfillments(
                  order_id TEXT NOT NULL,
                  application_id TEXT NOT NULL REFERENCES vendor_applications(id) ON DELETE CASCADE,
                  status TEXT NOT NULL DEFAULT 'NEW' CHECK(status IN ({statuses})),
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  PRIMARY KEY(order_id,application_id)
                )
                """
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS shop_fulfillment_application_idx "
                "ON shop_order_fulfillments(application_id,updated_at)"
            )
            db.execute(
                "INSERT INTO shop_schema_migrations(version,applied_at) VALUES(4,?)",
                (now,),
            )
            db.commit()
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def _migrate_shipping_tracking(db: sqlite3.Connection) -> None:
        now = iso(utc_now())
        db.execute("BEGIN IMMEDIATE")
        try:
            if db.execute(
                "SELECT 1 FROM shop_schema_migrations WHERE version=5"
            ).fetchone() is not None:
                db.commit()
                return
            columns = {
                row[1] for row in db.execute("PRAGMA table_info(shop_order_fulfillments)").fetchall()
            }
            if "carrier" not in columns:
                db.execute("ALTER TABLE shop_order_fulfillments ADD COLUMN carrier TEXT")
            if "tracking_number" not in columns:
                db.execute("ALTER TABLE shop_order_fulfillments ADD COLUMN tracking_number TEXT")
            db.execute(
                "INSERT INTO shop_schema_migrations(version,applied_at) VALUES(5,?)",
                (now,),
            )
            db.commit()
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def _migrate_return_requests(db: sqlite3.Connection) -> None:
        now = iso(utc_now())
        db.execute("BEGIN IMMEDIATE")
        try:
            if db.execute(
                "SELECT 1 FROM shop_schema_migrations WHERE version=6"
            ).fetchone() is not None:
                db.commit()
                return
            request_types = ",".join(f"'{value}'" for value in RETURN_REQUEST_TYPES)
            statuses = ",".join(f"'{value}'" for value in RETURN_REQUEST_STATUSES)
            db.execute(f"""
                CREATE TABLE IF NOT EXISTS shop_return_requests(
                  id TEXT PRIMARY KEY,
                  order_id TEXT NOT NULL,
                  customer_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                  application_id TEXT REFERENCES vendor_applications(id) ON DELETE SET NULL,
                  shop_name TEXT NOT NULL,
                  product_id TEXT NOT NULL,
                  product_name TEXT NOT NULL,
                  variant_id TEXT NOT NULL,
                  request_type TEXT NOT NULL CHECK(request_type IN ({request_types})),
                  reason TEXT NOT NULL,
                  details TEXT,
                  quantity INTEGER NOT NULL CHECK(quantity > 0),
                  unit_price INTEGER NOT NULL CHECK(unit_price >= 0),
                  item_subtotal INTEGER NOT NULL CHECK(item_subtotal >= 0),
                  status TEXT NOT NULL DEFAULT 'REQUESTED' CHECK(status IN ({statuses})),
                  seller_note TEXT,
                  seller_noted_at TEXT,
                  admin_note TEXT,
                  resolution_reference TEXT,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  reviewed_at TEXT,
                  resolved_at TEXT
                )
            """)
            db.execute(
                "CREATE INDEX IF NOT EXISTS shop_returns_customer_idx "
                "ON shop_return_requests(customer_user_id,created_at)"
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS shop_returns_seller_idx "
                "ON shop_return_requests(application_id,status,updated_at)"
            )
            db.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS shop_returns_active_line_idx "
                "ON shop_return_requests(order_id,customer_user_id,product_id,variant_id) "
                "WHERE status NOT IN ('REJECTED','REFUNDED','EXCHANGED','CANCELLED')"
            )
            db.execute(
                "INSERT INTO shop_schema_migrations(version,applied_at) VALUES(6,?)",
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
        payload: dict[str, Any], current: sqlite3.Row | None = None
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
        inventory = supplied("inventory", "inventory")
        if isinstance(price, bool) or not isinstance(price, int) or not 100 <= price <= 100_000_000:
            raise SecurityError(400, "Enter a valid product price.", "invalid_product")
        if isinstance(inventory, bool) or not isinstance(inventory, int) or not 0 <= inventory <= 100_000:
            raise SecurityError(400, "Enter valid product inventory.", "invalid_product")
        if (
            isinstance(original_price, bool)
            or not isinstance(original_price, int)
            or not price <= original_price <= 100_000_000
        ):
            raise SecurityError(400, "Enter a valid original price.", "invalid_product")

        raw_colour_hex = supplied("colourHex", "colour_hex")
        colour_hex = _optional_text(raw_colour_hex, "colour", 7)
        if colour_hex is not None and not COLOUR_HEX_PATTERN.fullmatch(colour_hex):
            raise SecurityError(400, "Enter a valid colour.", "invalid_product")

        image_value = payload.get("imageUrls") if "imageUrls" in payload else None
        if image_value is None and current is not None:
            image_urls = json.loads(current["image_urls_json"])
        else:
            image_urls = image_value
        if not isinstance(image_urls, list) or len(image_urls) > 8:
            raise SecurityError(400, "Enter valid product images.", "invalid_product")
        clean_images: list[str] = []
        for value in image_urls:
            if not isinstance(value, str) or len(value) > 500:
                raise SecurityError(400, "Enter valid product images.", "invalid_product")
            parsed = urlsplit(value)
            if parsed.scheme != "https" or not parsed.netloc:
                raise SecurityError(400, "Product images must use HTTPS.", "invalid_product")
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
            "inventory": inventory,
            "size": clean_text(supplied("size", "size"), "size", 1, 40),
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
            "inventory": row["inventory"],
            "size": row["size"],
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

    def seller_product_ids(self, user_id: str) -> set[str]:
        with self.connect() as db:
            self._seller_application(db, user_id)
            rows = db.execute(
                "SELECT id FROM shop_product_submissions WHERE submitted_by_user_id=?",
                (user_id,),
            ).fetchall()
        return {row["id"] for row in rows}

    @staticmethod
    def _serialize_fulfillment(
        status: str,
        updated_at: str | None,
        carrier: str | None = None,
        tracking_number: str | None = None,
    ) -> dict[str, Any]:
        shipping = None
        if carrier and tracking_number:
            shipping = {"carrier": carrier, "trackingNumber": tracking_number}
        return {
            "status": status,
            "updatedAt": updated_at,
            "allowedNextStatuses": list(FULFILLMENT_TRANSITIONS[status]),
            "shipping": shipping,
        }

    @staticmethod
    def _shipping_payload(
        payload: dict[str, Any], status: str
    ) -> tuple[str, str] | None:
        has_carrier = "carrier" in payload
        has_tracking = "trackingNumber" in payload
        if has_carrier != has_tracking:
            raise SecurityError(400, "Carrier and tracking number must be supplied together.", "invalid_shipping_details")
        if not has_carrier:
            return None
        if status != "SHIPPED":
            raise SecurityError(400, "Shipping details can only be attached to a shipped order.", "invalid_shipping_details")
        carrier = clean_text(payload.get("carrier"), "carrier", 2, 80)
        if not CARRIER_PATTERN.fullmatch(carrier):
            raise SecurityError(400, "Enter a valid carrier.", "invalid_shipping_details")
        tracking_number = clean_text(payload.get("trackingNumber"), "tracking number", 2, 120)
        if not TRACKING_NUMBER_PATTERN.fullmatch(tracking_number):
            raise SecurityError(400, "Enter a valid tracking number.", "invalid_shipping_details")
        return carrier, tracking_number

    def seller_fulfillment(self, user_id: str, order_id: str) -> dict[str, Any]:
        safe_order_id = clean_text(order_id, "Order ID", 1, 128)
        with self.connect() as db:
            application = self._seller_application(db, user_id)
            row = db.execute(
                "SELECT status,updated_at,carrier,tracking_number FROM shop_order_fulfillments "
                "WHERE order_id=? AND application_id=?",
                (safe_order_id, application["id"]),
            ).fetchone()
        if row is None:
            return self._serialize_fulfillment("NEW", None)
        return self._serialize_fulfillment(
            row["status"], row["updated_at"], row["carrier"], row["tracking_number"]
        )

    def update_seller_fulfillment(
        self, user_id: str, order_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        allowed_fields = {"status", "carrier", "trackingNumber"}
        if not isinstance(payload, dict) or "status" not in payload or set(payload) - allowed_fields:
            raise SecurityError(400, "A fulfillment status is required.", "invalid_fulfillment")
        safe_order_id = clean_text(order_id, "Order ID", 1, 128)
        status = clean_text(payload.get("status"), "Fulfillment status", 1, 20)
        if status not in FULFILLMENT_STATUSES:
            raise SecurityError(400, "Invalid fulfillment status.", "invalid_fulfillment")
        shipping = self._shipping_payload(payload, status)
        now = iso(utc_now())
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            application = self._seller_application(db, user_id)
            row = db.execute(
                "SELECT status,updated_at,carrier,tracking_number FROM shop_order_fulfillments "
                "WHERE order_id=? AND application_id=?",
                (safe_order_id, application["id"]),
            ).fetchone()
            current = row["status"] if row is not None else "NEW"
            carrier = row["carrier"] if row is not None else None
            tracking_number = row["tracking_number"] if row is not None else None
            if status == current:
                shipping_changed = False
                if shipping is not None and shipping != (carrier, tracking_number):
                    carrier, tracking_number = shipping
                    db.execute(
                        "UPDATE shop_order_fulfillments SET carrier=?,tracking_number=?,updated_at=? "
                        "WHERE order_id=? AND application_id=?",
                        (carrier, tracking_number, now, safe_order_id, application["id"]),
                    )
                    shipping_changed = True
                db.commit()
                result = self._serialize_fulfillment(
                    current,
                    now if shipping_changed else (row["updated_at"] if row else None),
                    carrier,
                    tracking_number,
                )
                result["changed"] = False
                result["shippingChanged"] = shipping_changed
                return result
            if status not in FULFILLMENT_TRANSITIONS[current]:
                db.rollback()
                raise SecurityError(
                    409,
                    f"Fulfillment cannot move from {current} to {status}.",
                    "invalid_fulfillment_transition",
                )
            if shipping is not None:
                carrier, tracking_number = shipping
            if row is None:
                db.execute(
                    "INSERT INTO shop_order_fulfillments("
                    "order_id,application_id,status,created_at,updated_at,carrier,tracking_number"
                    ") VALUES(?,?,?,?,?,?,?)",
                    (safe_order_id, application["id"], status, now, now, carrier, tracking_number),
                )
            else:
                db.execute(
                    "UPDATE shop_order_fulfillments "
                    "SET status=?,carrier=?,tracking_number=?,updated_at=? "
                    "WHERE order_id=? AND application_id=?",
                    (
                        status,
                        carrier,
                        tracking_number,
                        now,
                        safe_order_id,
                        application["id"],
                    ),
                )
            db.commit()
        result = self._serialize_fulfillment(status, now, carrier, tracking_number)
        result["changed"] = True
        result["shippingChanged"] = shipping is not None
        return result

    def order_fulfillments(self, order_id: str, product_ids: list[str]) -> list[dict[str, Any]]:
        safe_order_id = clean_text(order_id, "Order ID", 1, 128)
        ids = [value for value in dict.fromkeys(product_ids) if isinstance(value, str) and value]
        if not ids:
            return []
        placeholders = ",".join("?" for _ in ids)
        with self.connect() as db:
            rows = db.execute(
                f"""
                SELECT DISTINCT a.id,a.shop_name,f.status,f.updated_at,f.carrier,f.tracking_number
                  FROM shop_product_submissions p
                  JOIN vendor_applications a ON a.id=p.application_id
                  LEFT JOIN shop_order_fulfillments f
                    ON f.application_id=a.id AND f.order_id=?
                 WHERE p.id IN ({placeholders})
                 ORDER BY a.shop_name
                """,
                (safe_order_id, *ids),
            ).fetchall()
        return [
            {
                "shopName": row["shop_name"],
                "status": row["status"] or "NEW",
                "updatedAt": row["updated_at"],
                "shipping": (
                    {"carrier": row["carrier"], "trackingNumber": row["tracking_number"]}
                    if row["carrier"] and row["tracking_number"]
                    else None
                ),
            }
            for row in rows
        ]

    def admin_order_fulfillments(
        self, admin_id: str, order_id: str, product_ids: list[str]
    ) -> list[dict[str, Any]]:
        safe_order_id = clean_text(order_id, "Order ID", 1, 128)
        ids = [value for value in dict.fromkeys(product_ids) if isinstance(value, str) and value]
        if not ids:
            return []
        placeholders = ",".join("?" for _ in ids)
        with self.connect() as db:
            self._require_admin(db, admin_id)
            rows = db.execute(
                f"""
                SELECT DISTINCT a.id,a.shop_name,f.status,f.updated_at,f.carrier,f.tracking_number
                  FROM shop_product_submissions p
                  JOIN vendor_applications a ON a.id=p.application_id
                  LEFT JOIN shop_order_fulfillments f
                    ON f.application_id=a.id AND f.order_id=?
                 WHERE p.id IN ({placeholders})
                 ORDER BY a.shop_name
                """,
                (safe_order_id, *ids),
            ).fetchall()
        return [
            {
                "applicationId": row["id"],
                "shopName": row["shop_name"],
                "status": row["status"] or "NEW",
                "updatedAt": row["updated_at"],
                "shipping": (
                    {"carrier": row["carrier"], "trackingNumber": row["tracking_number"]}
                    if row["carrier"] and row["tracking_number"]
                    else None
                ),
            }
            for row in rows
        ]

    def admin_override_fulfillment(
        self,
        admin_id: str,
        order_id: str,
        application_id: str,
        product_ids: list[str],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise SecurityError(400, "A JSON object is required.", "invalid_fulfillment_override")
        allowed = {"status", "carrier", "trackingNumber", "reason"}
        if "status" not in payload or "reason" not in payload or set(payload) - allowed:
            raise SecurityError(400, "Status and override reason are required.", "invalid_fulfillment_override")
        safe_order_id = clean_text(order_id, "Order ID", 1, 128)
        safe_application_id = clean_text(application_id, "application ID", 1, 128)
        status = clean_text(payload.get("status"), "Fulfillment status", 1, 20).upper()
        if status not in FULFILLMENT_STATUSES:
            raise SecurityError(400, "Invalid fulfillment status.", "invalid_fulfillment_override")
        reason = clean_text(payload.get("reason"), "override reason", 5, 500)
        shipping = self._shipping_payload(payload, status)
        ids = [value for value in dict.fromkeys(product_ids) if isinstance(value, str) and value]
        if not ids:
            raise SecurityError(404, "Shop segment not found for this order.", "order_shop_segment_not_found")
        placeholders = ",".join("?" for _ in ids)
        now = iso(utc_now())
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._require_admin(db, admin_id)
            application = db.execute(
                "SELECT id,shop_name FROM vendor_applications WHERE id=?",
                (safe_application_id,),
            ).fetchone()
            if application is None:
                db.rollback()
                raise SecurityError(404, "Shop segment not found for this order.", "order_shop_segment_not_found")
            involved = db.execute(
                f"SELECT 1 FROM shop_product_submissions WHERE application_id=? AND id IN ({placeholders}) LIMIT 1",
                (safe_application_id, *ids),
            ).fetchone()
            if involved is None:
                db.rollback()
                raise SecurityError(404, "Shop segment not found for this order.", "order_shop_segment_not_found")
            row = db.execute(
                "SELECT status,updated_at,carrier,tracking_number FROM shop_order_fulfillments "
                "WHERE order_id=? AND application_id=?",
                (safe_order_id, safe_application_id),
            ).fetchone()
            before_status = row["status"] if row is not None else "NEW"
            before_shipping = (
                {"carrier": row["carrier"], "trackingNumber": row["tracking_number"]}
                if row is not None and row["carrier"] and row["tracking_number"]
                else None
            )
            carrier = tracking_number = None
            if status == "SHIPPED":
                if shipping is not None:
                    carrier, tracking_number = shipping
                elif row is not None and before_status == "SHIPPED":
                    carrier, tracking_number = row["carrier"], row["tracking_number"]
            if row is None:
                db.execute(
                    "INSERT INTO shop_order_fulfillments("
                    "order_id,application_id,status,created_at,updated_at,carrier,tracking_number"
                    ") VALUES(?,?,?,?,?,?,?)",
                    (safe_order_id, safe_application_id, status, now, now, carrier, tracking_number),
                )
            else:
                db.execute(
                    "UPDATE shop_order_fulfillments SET status=?,carrier=?,tracking_number=?,updated_at=? "
                    "WHERE order_id=? AND application_id=?",
                    (status, carrier, tracking_number, now, safe_order_id, safe_application_id),
                )
            after_shipping = (
                {"carrier": carrier, "trackingNumber": tracking_number}
                if carrier and tracking_number
                else None
            )
            self._audit_if_available(
                db,
                admin_id,
                "shop_fulfillment_override",
                "order_shop_fulfillment",
                f"{safe_order_id}:{safe_application_id}",
                {
                    "orderId": safe_order_id,
                    "applicationId": safe_application_id,
                    "shopName": application["shop_name"],
                    "from": before_status,
                    "to": status,
                    "beforeShipping": before_shipping,
                    "afterShipping": after_shipping,
                    "reason": reason,
                },
            )
            db.commit()
        result = self._serialize_fulfillment(status, now, carrier, tracking_number)
        result["applicationId"] = safe_application_id
        result["shopName"] = application["shop_name"]
        return result

    @staticmethod
    def _serialize_return_request(row: sqlite3.Row, *, admin: bool = False) -> dict[str, Any]:
        payload = {
            "id": row["id"],
            "orderId": row["order_id"],
            "shopName": row["shop_name"],
            "productId": row["product_id"],
            "productName": row["product_name"],
            "variantId": row["variant_id"],
            "requestType": row["request_type"],
            "reason": row["reason"],
            "details": row["details"],
            "quantity": row["quantity"],
            "unitPrice": row["unit_price"],
            "itemSubtotal": row["item_subtotal"],
            "status": row["status"],
            "sellerNote": row["seller_note"],
            "adminNote": row["admin_note"],
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
        }
        if row["seller_noted_at"]:
            payload["sellerNotedAt"] = row["seller_noted_at"]
        if row["reviewed_at"]:
            payload["reviewedAt"] = row["reviewed_at"]
        if row["resolved_at"]:
            payload["resolvedAt"] = row["resolved_at"]
        if admin:
            payload["applicationId"] = row["application_id"]
            payload["customerUserId"] = row["customer_user_id"]
            payload["resolutionReference"] = row["resolution_reference"]
        return payload

    @staticmethod
    def _return_rows_sql(where: str) -> str:
        return f"""
            SELECT r.* FROM shop_return_requests r
             WHERE {where}
             ORDER BY r.created_at DESC
        """

    def return_context(self, order_id: str, product_id: str) -> dict[str, Any] | None:
        safe_order_id = clean_text(order_id, "Order ID", 1, 128)
        safe_product_id = clean_text(product_id, "Product ID", 1, 128)
        with self.connect() as db:
            row = db.execute(
                """
                SELECT p.application_id,a.shop_name,
                       f.status AS fulfillment_status,f.updated_at AS fulfillment_updated_at
                  FROM shop_product_submissions p
                  JOIN vendor_applications a ON a.id=p.application_id
                  LEFT JOIN shop_order_fulfillments f
                    ON f.application_id=p.application_id AND f.order_id=?
                 WHERE p.id=?
                """,
                (safe_order_id, safe_product_id),
            ).fetchone()
        if row is None:
            return None
        return {
            "applicationId": row["application_id"],
            "shopName": row["shop_name"],
            "fulfillmentStatus": row["fulfillment_status"] or "NEW",
            "fulfillmentUpdatedAt": row["fulfillment_updated_at"],
        }

    def create_return_request(
        self,
        customer_user_id: str,
        order_id: str,
        item: dict[str, Any],
        context: dict[str, Any],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise SecurityError(400, "A return request is required.", "invalid_return_request")
        allowed = {"requestType", "reason", "details", "quantity"}
        if set(payload) - allowed:
            raise SecurityError(400, "Unsupported return request field.", "invalid_return_request")
        request_type = clean_text(payload.get("requestType"), "request type", 3, 32).upper()
        reason = clean_text(payload.get("reason"), "return reason", 3, 40).upper()
        if request_type not in RETURN_REQUEST_TYPES or reason not in RETURN_REQUEST_REASONS:
            raise SecurityError(400, "Invalid return request.", "invalid_return_request")
        allowed_reasons = {
            "SIZE_EXCHANGE": {"SIZE_ISSUE"},
            "ISSUE_RETURN": {"WRONG_ITEM", "DAMAGED", "DEFECTIVE", "MISSING_ITEM"},
        }
        if reason not in allowed_reasons[request_type]:
            raise SecurityError(400, "This reason is not valid for the selected request type.", "invalid_return_reason")
        details_value = payload.get("details")
        details = None if details_value in (None, "") else clean_text(details_value, "return details", 5, 1000)
        product_id = clean_text(item.get("productId"), "Product ID", 1, 128)
        variant_id = clean_text(item.get("variantId"), "Variant ID", 1, 160)
        purchased_quantity = item.get("quantity")
        quantity = payload.get("quantity", purchased_quantity)
        unit_price = item.get("unitPrice")
        if (
            isinstance(purchased_quantity, bool) or not isinstance(purchased_quantity, int)
            or isinstance(quantity, bool) or not isinstance(quantity, int)
            or not 1 <= quantity <= purchased_quantity
            or isinstance(unit_price, bool) or not isinstance(unit_price, int) or unit_price < 0
        ):
            raise SecurityError(400, "Invalid return quantity.", "invalid_return_quantity")
        safe_order_id = clean_text(order_id, "Order ID", 1, 128)
        if not isinstance(context, dict):
            raise SecurityError(400, "Return context is required.", "invalid_return_request")
        application_id = context.get("applicationId")
        if application_id is not None:
            application_id = clean_text(application_id, "application ID", 1, 128)
        shop_name = clean_text(context.get("shopName") or "StyleDash", "shop name", 1, 120)
        product_name = clean_text(item.get("productName"), "product name", 1, 200)
        now = iso(utc_now())
        request_id = "ret_" + secrets.token_hex(12)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")

            if application_id is not None and db.execute(
                "SELECT 1 FROM vendor_applications WHERE id=?", (application_id,)
            ).fetchone() is None:
                db.rollback()
                raise SecurityError(400, "Invalid seller context.", "invalid_return_request")
            prior = db.execute(
                """
                SELECT status FROM shop_return_requests
                 WHERE order_id=? AND customer_user_id=? AND product_id=? AND variant_id=?
                 ORDER BY created_at DESC
                """,
                (safe_order_id, customer_user_id, product_id, variant_id),
            ).fetchall()
            if any(row["status"] not in {"REJECTED", "REFUNDED", "EXCHANGED", "CANCELLED"} for row in prior):
                db.rollback()
                raise SecurityError(409, "An active request already exists for this item.", "return_request_exists")
            if any(row["status"] in {"REFUNDED", "EXCHANGED", "CANCELLED"} for row in prior):
                db.rollback()
                raise SecurityError(409, "This item already has a completed request.", "return_already_resolved")
            db.execute(
                """
                INSERT INTO shop_return_requests(
                  id,order_id,customer_user_id,application_id,shop_name,
                  product_id,product_name,variant_id,request_type,reason,details,
                  quantity,unit_price,item_subtotal,status,created_at,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?, 'REQUESTED',?,?)
                """,
                (
                    request_id, safe_order_id, customer_user_id, application_id, shop_name,
                    product_id, product_name, variant_id, request_type, reason, details,
                    quantity, unit_price, unit_price * quantity, now, now,
                ),
            )
            db.commit()
            row = db.execute(
                self._return_rows_sql("r.id=?"), (request_id,)
            ).fetchone()
        return self._serialize_return_request(row)

    def customer_return_requests(self, user_id: str) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute(
                self._return_rows_sql("r.customer_user_id=?"), (user_id,)
            ).fetchall()
        return [self._serialize_return_request(row) for row in rows]


    def seller_return_requests(self, user_id: str) -> list[dict[str, Any]]:
        with self.connect() as db:
            application = self._seller_application(db, user_id)
            rows = db.execute(
                self._return_rows_sql("r.application_id=?"), (application["id"],)
            ).fetchall()
        return [self._serialize_return_request(row) for row in rows]

    def seller_note_return_request(
        self, user_id: str, request_id: str, note: Any
    ) -> dict[str, Any]:
        clean_note = clean_text(note, "seller note", 2, 1000)
        safe_id = clean_text(request_id, "request ID", 1, 128)
        now = iso(utc_now())
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            application = self._seller_application(db, user_id)
            row = db.execute(
                "SELECT status FROM shop_return_requests WHERE id=? AND application_id=?",
                (safe_id, application["id"]),
            ).fetchone()
            if row is None:
                db.rollback()
                raise SecurityError(404, "Return request not found.", "return_request_not_found")
            if row["status"] in {"REJECTED", "REFUNDED", "EXCHANGED", "CANCELLED"}:
                db.rollback()
                raise SecurityError(409, "This request is already closed.", "return_request_closed")
            db.execute(
                "UPDATE shop_return_requests SET seller_note=?,seller_noted_at=?,updated_at=? WHERE id=?",
                (clean_note, now, now, safe_id),
            )
            db.commit()
            result = db.execute(self._return_rows_sql("r.id=?"), (safe_id,)).fetchone()
        return self._serialize_return_request(result)

    def admin_return_requests(self, admin_id: str) -> list[dict[str, Any]]:
        with self.connect() as db:
            self._require_admin(db, admin_id)
            rows = db.execute(self._return_rows_sql("1=1")).fetchall()
        return [self._serialize_return_request(row, admin=True) for row in rows]

    @staticmethod
    def _return_admin_targets(request_type: str, status: str) -> set[str]:
        common = {
            "REQUESTED": {"UNDER_REVIEW", "REJECTED"},
            "UNDER_REVIEW": {"APPROVED", "REJECTED"},
        }
        if status in common:
            return common[status]
        if request_type == "SIZE_EXCHANGE":
            return {
                "APPROVED": {"PICKUP_PENDING"},
                "PICKUP_PENDING": {"RECEIVED"},
                "RECEIVED": {"EXCHANGED"},
            }.get(status, set())
        if request_type == "ISSUE_RETURN":
            return {
                "APPROVED": {"PICKUP_PENDING"},
                "PICKUP_PENDING": {"RECEIVED"},
                "RECEIVED": {"REFUND_PENDING"},
            }.get(status, set())
        return set()

    def admin_transition_return_request(
        self,
        admin_id: str,
        request_id: str,
        target_status: Any,
        note: Any = None,
        resolution_reference: Any = None,
    ) -> dict[str, Any]:
        safe_id = clean_text(request_id, "request ID", 1, 128)
        if not isinstance(target_status, str):
            raise SecurityError(400, "Invalid return status.", "invalid_return_status")
        target = target_status.strip().upper()
        if target not in RETURN_REQUEST_STATUSES or target == "REFUNDED":
            raise SecurityError(400, "Invalid return status.", "invalid_return_status")
        clean_note = None if note in (None, "") else clean_text(note, "admin note", 2, 1000)
        clean_reference = None if resolution_reference in (None, "") else clean_text(
            resolution_reference, "resolution reference", 2, 200
        )
        if target == "REJECTED" and clean_note is None:
            raise SecurityError(400, "A rejection note is required.", "return_note_required")
        now = iso(utc_now())
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._require_admin(db, admin_id)
            current = db.execute(
                "SELECT * FROM shop_return_requests WHERE id=?", (safe_id,)
            ).fetchone()
            if current is None:
                db.rollback()
                raise SecurityError(404, "Return request not found.", "return_request_not_found")
            if target not in self._return_admin_targets(current["request_type"], current["status"]):
                db.rollback()
                raise SecurityError(409, "Return request transition is not allowed.", "invalid_return_transition")
            resolved_at = now if target in {"REJECTED", "EXCHANGED", "CANCELLED"} else current["resolved_at"]
            reviewed_at = now if target in {"UNDER_REVIEW", "APPROVED", "REJECTED"} else current["reviewed_at"]
            db.execute(
                """
                UPDATE shop_return_requests
                   SET status=?,admin_note=COALESCE(?,admin_note),
                       resolution_reference=COALESCE(?,resolution_reference),
                       reviewed_at=?,resolved_at=?,updated_at=?
                 WHERE id=?
                """,
                (
                    target, clean_note, clean_reference, reviewed_at,
                    resolved_at, now, safe_id,
                ),
            )
            self._audit_if_available(
                db,
                admin_id,
                "return_request_status",
                "return_request",
                safe_id,
                {
                    "from": current["status"],
                    "to": target,
                    "requestType": current["request_type"],
                    "orderId": current["order_id"],
                    "productId": current["product_id"],
                },
            )
            db.commit()
            result = db.execute(self._return_rows_sql("r.id=?"), (safe_id,)).fetchone()
        return self._serialize_return_request(result, admin=True)

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
                  size,colour_name,colour_hex,image_urls_json,attributes_json,status,
                  created_at,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'DRAFT',?,?)
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
                       original_price_paise=?,inventory=?,size=?,colour_name=?,colour_hex=?,
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
        variant_id = f"{row['id']}-var-1"
        sku = f"SD-SHOP-{row['id'][-12:].upper()}"
        store_slug = _store_slug(row['application_id'])
        variant = {
            "id": variant_id,
            "sku": sku,
            "size": row["size"],
            "colourName": row["colour_name"],
            "stock": row["inventory"],
            # The existing inventory API overlays this value. Fail closed until
            # its server-authoritative response arrives.
            "available": False,
            "price": price,
            "images": images,
        }
        if row["colour_hex"]:
            variant["colourHex"] = row["colour_hex"]
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
            "variants": [variant],
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
                    "active": row["status"] == "PUBLISHED" and row["shop_status"] == "ACTIVE",
                    "price": price,
                    "variants": [
                        {
                            "id": f"{row['id']}-var-1",
                            "sku": f"SD-SHOP-{row['id'][-12:].upper()}",
                            "size": row["size"],
                            "colourName": row["colour_name"],
                            "stock": row["inventory"],
                            "price": price,
                        }
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
