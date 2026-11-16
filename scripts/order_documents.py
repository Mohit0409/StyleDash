"""Seller bills for delivered orders, and the month-end document pack (admin-only archive).

What this module does
* stores the files an administrator attaches to a delivered order (PDF / JPEG / PNG, <= 5 MiB, <= 5 per order);
* lists the successful orders of a month with their bills;
* builds ONE ZIP per month: an order summary (CSV), every customer invoice, every seller bill, a checksum list.

What it deliberately does not do
* it never writes to orders.json, never touches an existing table, never changes an order;
* it computes no tax, issues no invoice, approves nothing and is not an accounting report;
* it creates exactly one NEW table (order_seller_bills) inside styledash.db, only on the first upload, so the
  existing nightly SQLite backup covers the bills without any change to the backup system.

"Successful order" uses the same definition as the existing billing preview: status delivered, not a payment
test, and the delivered date (India time) falls in the month.
"""
from __future__ import annotations

import base64
import binascii
import csv
import hashlib
import io
import re
import secrets
import sqlite3
import tempfile
import threading
import unicodedata
import zipfile
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable

try:
    from billing_audit import ALLOWED_DOCUMENTS, INDIA_TZ, _delivered_at, _stores_for_order
except ModuleNotFoundError:  # deployed scripts directory imports directly
    from scripts.billing_audit import ALLOWED_DOCUMENTS, INDIA_TZ, _delivered_at, _stores_for_order

TABLE = "order_seller_bills"
MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_BILLS_PER_ORDER = 5
MAX_EXPORT_ORDERS = 1000
MAX_EXPORT_BYTES = 300 * 1024 * 1024
# base64 of 5 MiB is ~6.99 MB; the handler allows this much JSON for one upload
UPLOAD_REQUEST_MAX_BYTES = 8 * 1024 * 1024
MONTH_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
BILL_ID_PATTERN = re.compile(r"^osb_[0-9a-f]{16}$")
_UNSAFE_NAME = re.compile(r"[^A-Za-z0-9._ -]+")
_COLUMNS = (
    "id", "order_id", "store_id", "store_name", "file_name", "content_type", "size_bytes", "sha256",
    "document", "bill_number", "note", "uploaded_by", "uploaded_at", "voided_at", "voided_by", "void_reason",
)
_CREATE = f"""
CREATE TABLE IF NOT EXISTS {TABLE} (
    id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL,
    store_id TEXT NOT NULL DEFAULT '',
    store_name TEXT NOT NULL DEFAULT '',
    file_name TEXT NOT NULL,
    content_type TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    document BLOB NOT NULL,
    bill_number TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '',
    uploaded_by TEXT NOT NULL,
    uploaded_at TEXT NOT NULL,
    voided_at TEXT,
    voided_by TEXT,
    void_reason TEXT
)"""
_PUBLIC = ("id", "store_id", "store_name", "file_name", "content_type", "size_bytes", "sha256",
           "bill_number", "note", "uploaded_at")
_UPLOAD_KEYS = {"fileName", "contentType", "contentBase64", "storeId", "billNumber", "note"}
_write_lock = threading.Lock()


class OrderDocumentError(ValueError):
    def __init__(self, message: str, code: str, status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status


def _text(value: Any, label: str, maximum: int, *, required: bool = False, minimum: int = 0) -> str:
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise OrderDocumentError(f"{label} must be text.", "invalid_order_document")
    cleaned = " ".join(
        "".join(ch for ch in unicodedata.normalize("NFKC", value) if ch == " " or unicodedata.category(ch)[0] != "C").split()
    )
    if (required and not cleaned) or len(cleaned) < minimum or len(cleaned) > maximum:
        raise OrderDocumentError(f"Enter {label} ({minimum or 1}-{maximum} characters).", "invalid_order_document")
    return cleaned


def _safe_filename(name: str, extension: str, fallback: str) -> str:
    base = unicodedata.normalize("NFKC", name).replace("\\", "/").rsplit("/", 1)[-1]
    base = _UNSAFE_NAME.sub("-", base).strip(" .-_")
    stem = base.rsplit(".", 1)[0] if "." in base else base
    stem = stem.strip(" .-_")[:80] or fallback
    return f"{stem}{extension}"


def _safe_part(value: str, fallback: str, limit: int = 60) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "-", value).strip("-")[:limit] or fallback


def _csv_cell(value: Any) -> str:
    """Neutralise spreadsheet formulas (CSV injection) in any text that came from a user."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def _money(value: Any) -> str:
    try:
        return str(Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    except (InvalidOperation, ValueError):
        return "0.00"


def validate_month(value: Any) -> str:
    month = str(value or "").strip()
    if not MONTH_PATTERN.fullmatch(month):
        raise OrderDocumentError("Choose a month in YYYY-MM format.", "invalid_billing_month")
    return month


class OrderDocuments:
    """orders(): {order_id: order}; customer_invoice(order_id): (kind, pdf_bytes), raising when unavailable."""

    def __init__(
        self,
        database: Path,
        orders: Callable[[], dict[str, dict[str, Any]]],
        customer_invoice: Callable[[str], tuple[str, bytes]],
        record_action: Callable[..., Any],
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.database = Path(database)
        self._orders = orders
        self._customer_invoice = customer_invoice
        self._record_action = record_action
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    # ---- database -------------------------------------------------------
    def _open(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.database), timeout=20, isolation_level=None)
        connection.execute("PRAGMA busy_timeout=20000")
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _table_exists(connection: sqlite3.Connection) -> bool:
        return connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (TABLE,)
        ).fetchone() is not None

    @staticmethod
    def _check_schema(connection: sqlite3.Connection) -> None:
        columns = tuple(row[1] for row in connection.execute(f"PRAGMA table_info({TABLE})"))
        if columns != _COLUMNS:
            raise OrderDocumentError("Seller bill storage has an unexpected layout.", "order_document_storage_error", 500)

    def _ensure_table(self, connection: sqlite3.Connection) -> None:
        """Additive and idempotent: creates only this module's own table and index."""
        if self._table_exists(connection):
            self._check_schema(connection)
            return
        connection.execute("BEGIN IMMEDIATE")
        try:
            connection.execute(_CREATE)
            connection.execute(f"CREATE INDEX IF NOT EXISTS {TABLE}_order ON {TABLE}(order_id)")
            self._check_schema(connection)
            connection.execute("COMMIT")
        except BaseException:
            connection.execute("ROLLBACK")
            raise

    def _active_bills(self, order_ids: set[str] | None = None) -> dict[str, list[dict[str, Any]]]:
        """Metadata only (never the document bytes), grouped by order, oldest first."""
        if not self.database.is_file():
            return {}
        connection = self._open()
        try:
            if not self._table_exists(connection):
                return {}
            self._check_schema(connection)
            rows = connection.execute(
                f"SELECT {', '.join(_PUBLIC)}, order_id FROM {TABLE} WHERE voided_at IS NULL "
                "ORDER BY order_id, uploaded_at, id"
            ).fetchall()
        finally:
            connection.close()
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            if order_ids is not None and row["order_id"] not in order_ids:
                continue
            grouped.setdefault(row["order_id"], []).append({key: row[key] for key in _PUBLIC})
        return grouped

    @staticmethod
    def _public_bill(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"], "storeId": row["store_id"], "storeName": row["store_name"],
            "fileName": row["file_name"], "contentType": row["content_type"], "sizeBytes": row["size_bytes"],
            "sha256": row["sha256"], "billNumber": row["bill_number"], "note": row["note"],
            "uploadedAt": row["uploaded_at"],
        }

    # ---- orders ---------------------------------------------------------
    def _successful_orders(self, month: str | None) -> list[tuple[str, dict[str, Any], datetime]]:
        selected = []
        for order_id, order in self._orders().items():
            if (
                not isinstance(order, dict)
                or order.get("status") != "delivered"
                or order.get("isPaymentTestOrder") is True
                or order.get("fulfillmentRequired") is False
            ):
                continue
            delivered = _delivered_at(order)
            if delivered is None:
                continue
            local = delivered.astimezone(INDIA_TZ)
            if month is not None and local.strftime("%Y-%m") != month:
                continue
            selected.append((str(order_id), order, local))
        selected.sort(key=lambda row: (row[2], row[0]))
        return selected

    def _successful_order(self, order_id: str) -> dict[str, Any]:
        order = self._orders().get(order_id)
        if not isinstance(order, dict):
            raise OrderDocumentError("Order not found.", "order_not_found", 404)
        if (
            order.get("status") != "delivered"
            or order.get("isPaymentTestOrder") is True
            or order.get("fulfillmentRequired") is False
        ):
            raise OrderDocumentError(
                "Seller bills can only be attached to delivered orders.", "order_not_successful", 409
            )
        return order

    @staticmethod
    def _order_row(order_id: str, order: dict[str, Any], local: datetime) -> dict[str, Any]:
        address = order.get("address") if isinstance(order.get("address"), dict) else {}
        items = [item for item in order.get("items") or [] if isinstance(item, dict)]
        units = 0
        for item in items:
            try:
                units += max(0, int(item.get("quantity") or 0))
            except (TypeError, ValueError):
                pass
        return {
            "orderId": order_id,
            "deliveredAt": local.isoformat(),
            "deliveredDate": local.strftime("%Y-%m-%d"),
            "customerName": " ".join(str(address.get("name") or "").split())[:80],
            "stores": _stores_for_order(order),
            "units": units,
            "orderTotal": _money(order.get("grandTotal")),
            "paymentMethod": " ".join(str(order.get("paymentMethod") or "online").split())[:30],
        }

    # ---- month overview -------------------------------------------------
    def month_overview(self, month: Any) -> dict[str, Any]:
        month = validate_month(month)
        selected = self._successful_orders(month)
        bills = self._active_bills({order_id for order_id, _o, _l in selected})
        rows = []
        total = Decimal("0")
        with_bill = 0
        bill_count = 0
        for order_id, order, local in selected:
            row = self._order_row(order_id, order, local)
            row["bills"] = [self._public_bill(bill) for bill in bills.get(order_id, [])]
            if row["bills"]:
                with_bill += 1
            bill_count += len(row["bills"])
            total += Decimal(row["orderTotal"])
            rows.append(row)
        return {
            "month": month,
            "definition": "Successful order = delivered, not a payment test, delivered date (India time) in this month.",
            "summary": {
                "orders": len(rows), "ordersWithSellerBill": with_bill,
                "ordersMissingSellerBill": len(rows) - with_bill, "sellerBills": bill_count,
                "orderTotal": str(total.quantize(Decimal("0.01"))),
            },
            "limits": {
                "maxFileBytes": MAX_FILE_BYTES, "maxBillsPerOrder": MAX_BILLS_PER_ORDER,
                "maxExportOrders": MAX_EXPORT_ORDERS, "types": sorted(ALLOWED_DOCUMENTS),
            },
            "orders": rows,
        }

    # ---- upload / void / download ---------------------------------------
    def upload(self, admin_id: str, order_id: str, payload: Any) -> dict[str, Any]:
        if not admin_id:
            raise OrderDocumentError("Administrator required.", "admin_authentication_required", 403)
        if not isinstance(payload, dict) or set(payload) - _UPLOAD_KEYS:
            raise OrderDocumentError("Unexpected fields in the seller bill request.", "invalid_order_document")
        order = self._successful_order(order_id)
        content_type = payload.get("contentType")
        if content_type not in ALLOWED_DOCUMENTS:
            raise OrderDocumentError("Upload a PDF, JPEG or PNG file.", "invalid_order_document")
        extension, magic = ALLOWED_DOCUMENTS[content_type]
        encoded = payload.get("contentBase64")
        if not isinstance(encoded, str) or not encoded:
            raise OrderDocumentError("Choose a file to upload.", "invalid_order_document")
        if len(encoded) > (MAX_FILE_BYTES * 4) // 3 + 8:
            raise OrderDocumentError("The file is larger than 5 MB.", "order_document_too_large", 413)
        try:
            document = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError):
            raise OrderDocumentError("The file could not be read.", "invalid_order_document") from None
        if not document:
            raise OrderDocumentError("The file is empty.", "invalid_order_document")
        if len(document) > MAX_FILE_BYTES:
            raise OrderDocumentError("The file is larger than 5 MB.", "order_document_too_large", 413)
        if not document.startswith(magic):
            raise OrderDocumentError("The file content does not match its type.", "invalid_order_document")
        file_name = _safe_filename(_text(payload.get("fileName"), "a file name", 255, required=True), extension, "seller-bill")
        bill_number = _text(payload.get("billNumber"), "the bill number", 40)
        note = _text(payload.get("note"), "the note", 200)
        stores = _stores_for_order(order)
        requested = _text(payload.get("storeId"), "the store", 128)
        if requested:
            store = next((row for row in stores if row["storeId"] and row["storeId"] == requested), None)
            if store is None:
                raise OrderDocumentError("That store is not part of this order.", "invalid_order_document")
        elif len(stores) == 1:
            store = stores[0]
        else:
            raise OrderDocumentError("Choose which store this bill is from.", "invalid_order_document")
        digest = hashlib.sha256(document).hexdigest()
        bill_id = "osb_" + secrets.token_hex(8)
        now = self._clock().astimezone(INDIA_TZ).isoformat()
        with _write_lock:
            connection = self._open()
            try:
                self._ensure_table(connection)
                connection.execute("BEGIN IMMEDIATE")
                try:
                    active = connection.execute(
                        f"SELECT sha256 FROM {TABLE} WHERE order_id=? AND voided_at IS NULL", (order_id,)
                    ).fetchall()
                    if len(active) >= MAX_BILLS_PER_ORDER:
                        raise OrderDocumentError(
                            f"This order already has {MAX_BILLS_PER_ORDER} seller bills.", "order_document_limit", 409
                        )
                    if any(row[0] == digest for row in active):
                        raise OrderDocumentError("This exact file is already attached to the order.", "duplicate_order_document", 409)
                    connection.execute(
                        f"INSERT INTO {TABLE} (id, order_id, store_id, store_name, file_name, content_type, size_bytes, "
                        "sha256, document, bill_number, note, uploaded_by, uploaded_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (bill_id, order_id, store["storeId"], store["storeName"], file_name, content_type,
                         len(document), digest, document, bill_number, note, admin_id, now),
                    )
                    connection.execute("COMMIT")
                except BaseException:
                    connection.execute("ROLLBACK")
                    raise
            finally:
                connection.close()
        self._record_action(admin_id, "seller_bill_uploaded", "order", order_id, "success", {
            "billId": bill_id, "fileName": file_name, "sizeBytes": len(document), "sha256": digest,
        })
        return self._public_bill({
            "id": bill_id, "store_id": store["storeId"], "store_name": store["storeName"], "file_name": file_name,
            "content_type": content_type, "size_bytes": len(document), "sha256": digest,
            "bill_number": bill_number, "note": note, "uploaded_at": now,
        })

    def void(self, admin_id: str, order_id: str, bill_id: str, payload: Any) -> dict[str, Any]:
        if not admin_id:
            raise OrderDocumentError("Administrator required.", "admin_authentication_required", 403)
        if not isinstance(payload, dict) or set(payload) - {"reason"}:
            raise OrderDocumentError("Unexpected fields in the request.", "invalid_order_document")
        reason = _text(payload.get("reason"), "a reason", 200, required=True, minimum=3)
        if not BILL_ID_PATTERN.fullmatch(bill_id):
            raise OrderDocumentError("Seller bill not found.", "order_document_not_found", 404)
        now = self._clock().astimezone(INDIA_TZ).isoformat()
        with _write_lock:
            connection = self._open()
            try:
                if not self._table_exists(connection):
                    raise OrderDocumentError("Seller bill not found.", "order_document_not_found", 404)
                self._check_schema(connection)
                connection.execute("BEGIN IMMEDIATE")
                try:
                    changed = connection.execute(
                        f"UPDATE {TABLE} SET voided_at=?, voided_by=?, void_reason=? "
                        "WHERE id=? AND order_id=? AND voided_at IS NULL",
                        (now, admin_id, reason, bill_id, order_id),
                    ).rowcount
                    if changed != 1:
                        raise OrderDocumentError("Seller bill not found.", "order_document_not_found", 404)
                    connection.execute("COMMIT")
                except BaseException:
                    connection.execute("ROLLBACK")
                    raise
            finally:
                connection.close()
        self._record_action(admin_id, "seller_bill_voided", "order", order_id, "success", {"billId": bill_id, "reason": reason})
        return {"id": bill_id, "voided": True}

    def _read_document(self, order_id: str, bill_id: str) -> tuple[bytes, dict[str, Any]]:
        if not BILL_ID_PATTERN.fullmatch(bill_id) or not self.database.is_file():
            raise OrderDocumentError("Seller bill not found.", "order_document_not_found", 404)
        connection = self._open()
        try:
            if not self._table_exists(connection):
                raise OrderDocumentError("Seller bill not found.", "order_document_not_found", 404)
            self._check_schema(connection)
            row = connection.execute(
                f"SELECT {', '.join(_PUBLIC)}, document FROM {TABLE} WHERE id=? AND order_id=? AND voided_at IS NULL",
                (bill_id, order_id),
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            raise OrderDocumentError("Seller bill not found.", "order_document_not_found", 404)
        document = bytes(row["document"])
        if hashlib.sha256(document).hexdigest() != row["sha256"] or len(document) != row["size_bytes"]:
            raise OrderDocumentError("Seller bill failed its integrity check.", "order_document_integrity_error", 500)
        return document, {key: row[key] for key in _PUBLIC}

    def document(self, order_id: str, bill_id: str) -> tuple[bytes, str, str]:
        document, meta = self._read_document(order_id, bill_id)
        return document, meta["content_type"], meta["file_name"]

    # ---- month-end pack -------------------------------------------------
    def export_month(self, admin_id: str, month: Any) -> tuple[Any, int, str, dict[str, Any]]:
        if not admin_id:
            raise OrderDocumentError("Administrator required.", "admin_authentication_required", 403)
        month = validate_month(month)
        selected = self._successful_orders(month)
        if not selected:
            raise OrderDocumentError("There are no successful orders in that month.", "no_orders_in_month", 409)
        if len(selected) > MAX_EXPORT_ORDERS:
            raise OrderDocumentError(
                f"More than {MAX_EXPORT_ORDERS} orders in one month; contact support to split the export.",
                "export_too_large", 413,
            )
        bills = self._active_bills({order_id for order_id, _o, _l in selected})
        root = f"vibe4you-month-end-{month}"
        spooled = tempfile.SpooledTemporaryFile(max_size=16 * 1024 * 1024)
        names: set[str] = set()
        manifest: list[tuple[str, str]] = []
        csv_rows: list[list[str]] = []
        counters = {"invoices": 0, "unavailable": 0, "bills": 0, "missing": 0, "bytes": 0}
        generated = self._clock().astimezone(INDIA_TZ)

        def add(archive: zipfile.ZipFile, relative: str, data: bytes) -> str:
            if relative in names or ".." in relative.split("/") or relative.startswith("/"):
                raise OrderDocumentError("Export file name collision.", "export_error", 500)
            counters["bytes"] += len(data)
            if counters["bytes"] > MAX_EXPORT_BYTES:
                raise OrderDocumentError("The month is too large for one download.", "export_too_large", 413)
            names.add(relative)
            info = zipfile.ZipInfo(f"{root}/{relative}", date_time=generated.timetuple()[:6])
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            archive.writestr(info, data)
            manifest.append((hashlib.sha256(data).hexdigest(), relative))
            return relative

        try:
            with zipfile.ZipFile(spooled, "w", zipfile.ZIP_DEFLATED) as archive:
                used_ids: set[str] = set()
                for order_id, order, local in selected:
                    row = self._order_row(order_id, order, local)
                    safe_id = _safe_part(order_id, "order", 70)
                    if safe_id in used_ids:
                        safe_id = f"{safe_id}-{hashlib.sha256(order_id.encode()).hexdigest()[:6]}"
                    used_ids.add(safe_id)
                    invoice_kind, invoice_file, invoice_note = "unavailable", "", ""
                    try:
                        invoice_kind, invoice_pdf = self._customer_invoice(order_id)
                        invoice_kind = "tax_invoice" if invoice_kind == "tax_invoice" else "receipt"
                        invoice_file = add(archive, f"customer-invoices/{safe_id}-{invoice_kind.replace('_', '-')}.pdf", invoice_pdf)
                        counters["invoices"] += 1
                    except OrderDocumentError:
                        raise
                    except Exception as error:  # one unreadable order must not stop the whole month
                        invoice_kind, invoice_file = "unavailable", ""
                        invoice_note = f"customer invoice could not be produced ({type(error).__name__})"
                        counters["unavailable"] += 1
                    files, numbers = [], []
                    for index, bill in enumerate(bills.get(order_id, []), start=1):
                        document, meta = self._read_document(order_id, bill["id"])
                        extension = ALLOWED_DOCUMENTS[meta["content_type"]][0]
                        store_part = _safe_part(meta["store_name"], "store", 30)
                        name = _safe_filename(meta["file_name"], extension, "seller-bill")
                        files.append(add(archive, f"seller-bills/{safe_id}/{index:02d}-{store_part}-{name}", document))
                        if meta["bill_number"]:
                            numbers.append(meta["bill_number"])
                        counters["bills"] += 1
                    if not files:
                        counters["missing"] += 1
                    csv_rows.append([
                        order_id, row["deliveredDate"], row["customerName"],
                        "; ".join(store["storeName"] for store in row["stores"]), str(row["units"]),
                        row["orderTotal"], row["paymentMethod"], invoice_kind, invoice_file,
                        str(len(files)), "; ".join(files), "; ".join(numbers),
                        "attached" if files else "MISSING", invoice_note,
                    ])
                buffer = io.StringIO(newline="")
                writer = csv.writer(buffer)
                writer.writerow([
                    "order_id", "delivered_date", "customer_name", "stores", "units", "order_total_inr",
                    "payment_method", "customer_invoice_type", "customer_invoice_file", "seller_bill_count",
                    "seller_bill_files", "seller_bill_numbers", "seller_bill_status", "note",
                ])
                for row in csv_rows:
                    writer.writerow([_csv_cell(cell) for cell in row])
                add(archive, "orders-summary.csv", b"\xef\xbb\xbf" + buffer.getvalue().encode("utf-8"))
                add(archive, "README.txt", self._readme(month, generated, len(selected), counters).encode("utf-8"))
                lines = "".join(f"{digest}  {relative}\n" for digest, relative in sorted(manifest, key=lambda row: row[1]))
                info = zipfile.ZipInfo(f"{root}/MANIFEST.sha256", date_time=generated.timetuple()[:6])
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o600 << 16
                archive.writestr(info, lines.encode("utf-8"))
        except BaseException:
            spooled.close()
            raise
        size = spooled.seek(0, 2)
        spooled.seek(0)
        digest = hashlib.sha256()
        for chunk in iter(lambda: spooled.read(1024 * 1024), b""):
            digest.update(chunk)
        spooled.seek(0)
        summary = {
            "month": month, "orders": len(selected), "customerInvoices": counters["invoices"],
            "customerInvoicesUnavailable": counters["unavailable"], "sellerBills": counters["bills"],
            "ordersMissingSellerBill": counters["missing"], "sizeBytes": size, "zipSha256": digest.hexdigest(),
        }
        self._record_action(admin_id, "month_end_exported", "month", month, "success", summary)
        return spooled, size, f"{root}.zip", summary

    @staticmethod
    def _readme(month: str, generated: datetime, orders: int, counters: dict[str, int]) -> str:
        return (
            f"Vibe4You month-end document pack, {month}\n"
            f"Generated: {generated.isoformat()} (India time)\n\n"
            "Successful order = status delivered, not a payment test, delivered date (India time) in this month.\n"
            "Cancelled, refunded or undelivered orders are not included.\n\n"
            f"Orders: {orders}\n"
            f"Customer invoices: {counters['invoices']} (GST tax invoice when one was issued, otherwise the payment receipt)\n"
            f"Customer invoices that could not be produced: {counters['unavailable']} (see the note column)\n"
            f"Seller bills attached by administrators: {counters['bills']}\n"
            f"Orders with no seller bill (status MISSING in the summary): {counters['missing']}\n\n"
            "Files\n"
            "  orders-summary.csv   one row per order\n"
            "  customer-invoices/   one PDF per order\n"
            "  seller-bills/        the files attached to each order, as uploaded\n"
            "  MANIFEST.sha256      SHA-256 of every other file; check with: sha256sum -c MANIFEST.sha256 (run inside this folder)\n\n"
            "This pack is an archive of documents. The seller bills are exactly what was uploaded and have not been\n"
            "verified. It is not a GST return, tax computation or accounting report.\n"
        )
