"""Admin-only order profitability worksheet layered on R-OD1; not a GST return.

Seller amounts are explicitly entered in INR and are GST-INCLUSIVE. Nothing is
inferred from a photograph of a seller bill, and no order, invoice, price or
seller bill is modified. A separate additive SQLite table preserves the input.
"""
from __future__ import annotations
import csv
import hashlib
import io
import json
import re
import sqlite3
import threading
from contextlib import closing
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

try:
    from receipt_pdf import _verified_receipt_gst_breakdown
except ModuleNotFoundError:
    from scripts.receipt_pdf import _verified_receipt_gst_breakdown

try:
    from order_documents import validate_month, OrderDocumentError
except ModuleNotFoundError:
    from scripts.order_documents import validate_month, OrderDocumentError

TABLE = "order_profit_entries"
INPUT_KEYS = {"sellerTotal", "sellerGst", "deliveryCost"}
MONEY_RE = re.compile(r"^(?:0|[1-9][0-9]{0,7})(?:\.[0-9]{1,2})?$")
_LOCK = threading.Lock()


class OrderProfitError(ValueError):
    def __init__(self, message, code="invalid_profit_amount", status=400):
        super().__init__(message)
        self.message, self.code, self.status = message, code, status


def _paise(value, label, *, user_input=False):
    if user_input and (not isinstance(value, str) or not MONEY_RE.fullmatch(value)):
        raise OrderProfitError(f"{label} must be an amount in rupees with up to two decimals.")
    if value is None or isinstance(value, bool):
        return None
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount < 0 or amount > Decimal("99999999.99"):
            return None
        paise = amount * 100
        if paise != paise.to_integral_value():
            return None
        return int(paise)
    except (InvalidOperation, ValueError, TypeError):
        return None


def _rupees(value):
    if value is None:
        return None
    return format((Decimal(value) / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), ".2f")


def _safe_csv(value):
    s = "" if value is None else str(value)
    if re.fullmatch(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]{1,2})?", s):
        return s
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s


def _issued_invoice_gst(invoice_path, order_id, order_total):
    """Read immutable issued-invoice tax from SQLite without creating/updating anything."""
    if not invoice_path.is_file():
        return None, None
    try:
        con = sqlite3.connect(invoice_path.resolve().as_uri() + "?mode=ro", uri=True, timeout=3)
        try:
            row = con.execute(
                "SELECT snapshot_json, sha256 FROM documents "
                "WHERE kind='TAX_INVOICE' AND order_id=?", (order_id,)
            ).fetchone()
        finally:
            con.close()
    except (sqlite3.Error, OSError, ValueError):
        return None, "invoice_ledger_unreadable"
    if row is None:
        return None, None
    raw, digest = row
    if not isinstance(raw, str) or hashlib.sha256(raw.encode("utf-8")).hexdigest() != digest:
        return None, "issued_invoice_integrity_error"
    try:
        invoice = json.loads(raw)
    except (TypeError, ValueError):
        return None, "issued_invoice_integrity_error"
    if not isinstance(invoice, dict) or invoice.get("document_kind") != "TAX_INVOICE" or invoice.get("status") != "ISSUED":
        return None, "issued_invoice_inconsistent"
    gst = _paise(invoice.get("gst_total"), "issued invoice GST")
    invoice_total = _paise(invoice.get("customer_paid_total"), "issued invoice total")
    if gst is None or invoice_total is None or invoice_total != order_total or gst > invoice_total:
        return None, "issued_invoice_inconsistent"
    return gst, "issued_tax_invoice"


def _customer_gst(order, *, order_id, total, invoice_path, registry_path, service_policy_path):
    # A signed, issued tax invoice takes precedence. Never recompute its tax.
    issued_gst, issued_source = _issued_invoice_gst(invoice_path, order_id, total)
    if issued_source:
        return issued_gst, issued_source

    snapshot = order.get("gstSnapshot")
    if isinstance(snapshot, dict) and "includedTaxTotal" in snapshot:
        amount = _paise(snapshot["includedTaxTotal"], "customer GST")
        if amount is None:
            return None, "invalid_checkout_snapshot"
        return amount, "checkout_snapshot"

    # Match the actual customer receipt's GST breakdown, including the product
    # registry, historical approvals, discounts, and separately approved fees.
    # A receipt without a verified GST breakdown does NOT establish a zero rate.
    try:
        receipt = _verified_receipt_gst_breakdown(
            order, registry_path=registry_path, service_policy_path=service_policy_path
        )
    except (ValueError, TypeError, KeyError, ArithmeticError):
        receipt = None
    if isinstance(receipt, dict):
        amount = _paise(receipt.get("gst"), "verified receipt GST")
        if amount is not None:
            return amount, "verified_receipt_breakdown"

    legacy = _paise(order.get("taxes"), "legacy GST")
    if legacy is not None and legacy > 0:
        return legacy, "legacy_order_field"
    return None, "unverified_legacy_zero" if legacy == 0 else "unknown"


def _customer_delivery(order, *, order_id, order_total, invoice_path):
    """Prefer immutable issued customer invoice; otherwise receipt checkout fee.

    Do not silently fall back to checkout values if an issued invoice exists
    but its SHA-256, identity, status, total or delivery line is inconsistent.
    """
    fallback=_paise(order.get("deliveryFee",0),"customer delivery charge")
    if not invoice_path.is_file():
        return fallback
    try:
        with closing(sqlite3.connect(invoice_path.resolve().as_uri()+"?mode=ro",uri=True,timeout=3)) as con:
            row=con.execute(
                "SELECT snapshot_json, sha256 FROM documents "
                "WHERE kind='TAX_INVOICE' AND order_id=?", (order_id,)
            ).fetchone()
    except (sqlite3.Error,OSError,ValueError):
        return None
    if row is None:
        return fallback
    raw,digest=row
    if not isinstance(raw,str) or hashlib.sha256(raw.encode("utf-8")).hexdigest()!=digest:
        return None
    try:
        invoice=json.loads(raw)
    except (TypeError,ValueError):
        return None
    if (not isinstance(invoice,dict) or invoice.get("document_kind")!="TAX_INVOICE"
            or invoice.get("status")!="ISSUED"
            or _paise(invoice.get("customer_paid_total"),"issued invoice total")!=order_total):
        return None
    items=invoice.get("items")
    if not isinstance(items,list):
        return None
    lines=[item for item in items if isinstance(item,dict)
           and item.get("product_name")=="Delivery / shipping"
           and item.get("unit")=="SERVICE"]
    if not lines:
        return 0 if fallback==0 else None
    if len(lines)!=1:
        return None
    amount=_paise(lines[0].get("gross"),"issued invoice delivery")
    return amount if amount is not None and order_total is not None and amount<=order_total else None


class OrderProfitLedger:
    def __init__(self, database, order_documents, orders, record_action, clock=None, *, tax_data_dir=None):
        self.database = Path(database)
        self.order_documents = order_documents
        self.orders = orders
        self.record_action = record_action
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        data_dir = Path(tax_data_dir) if tax_data_dir is not None else self.database.parent
        self.invoice_path = data_dir / "gst-invoice-ledger.sqlite3"
        self.registry_path = data_dir / "vibe4you-tax-classifications.sqlite3"
        self.service_policy_path = data_dir / "vibe4you-receipt-service-tax-policy.json"

    def _open(self):
        con = sqlite3.connect(str(self.database), isolation_level=None, timeout=20)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA busy_timeout=20000")
        return con

    def _has_table(self, con):
        exists = con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (TABLE,)
        ).fetchone()
        if not exists:
            return None
        columns = tuple(r["name"] for r in con.execute(f"PRAGMA table_info({TABLE})"))
        legacy = ("order_id", "seller_total_paise", "seller_gst_paise", "updated_at", "updated_by")
        if columns not in (legacy, legacy + ("delivery_cost_paise",)):
            raise OrderProfitError("Profit entry storage layout changed.", "profit_storage_error", 500)
        return "delivery_cost_paise" in columns

    def _values(self, order_ids):
        if not self.database.is_file() or not order_ids:
            return {}
        con = self._open()
        try:
            has_delivery_cost = self._has_table(con)
            if has_delivery_cost is None:
                return {}
            # bounded, no arbitrary SQL from order IDs; no BLOBs loaded
            delivery_column = "delivery_cost_paise" if has_delivery_cost else "NULL AS delivery_cost_paise"
            return {r["order_id"]: dict(r) for r in con.execute(
                f"SELECT order_id,seller_total_paise,seller_gst_paise,{delivery_column},updated_at,updated_by FROM {TABLE}"
            ) if r["order_id"] in order_ids}
        finally:
            con.close()

    def save(self, admin_id, order_id, payload):
        if not admin_id:
            raise OrderProfitError("Administrator required.", "admin_authentication_required", 403)
        if not isinstance(payload, dict) or not {"sellerTotal", "sellerGst"} <= set(payload) or set(payload) - INPUT_KEYS:
            raise OrderProfitError("Enter both seller total and seller GST.")
        self.order_documents._successful_order(order_id)  # identical delivered-order gate as seller bill upload
        total = _paise(payload["sellerTotal"], "Seller total", user_input=True)
        gst = _paise(payload["sellerGst"], "Seller GST", user_input=True)
        delivery_input = payload.get("deliveryCost")
        delivery_cost = None if delivery_input in (None, "") else _paise(delivery_input, "Delivery cost", user_input=True)
        if total is None or gst is None or gst > total:
            raise OrderProfitError("Seller GST must not exceed the seller total.")
        if delivery_input not in (None, "") and delivery_cost is None:
            raise OrderProfitError("Delivery cost must be an amount in rupees with up to two decimals.")
        now = self.clock().isoformat()
        with _LOCK:
            con = self._open()
            try:
                con.execute("BEGIN IMMEDIATE")
                try:
                    con.execute(f"""CREATE TABLE IF NOT EXISTS {TABLE} (
                        order_id TEXT PRIMARY KEY,
                        seller_total_paise INTEGER NOT NULL CHECK(seller_total_paise >= 0),
                        seller_gst_paise INTEGER NOT NULL CHECK(seller_gst_paise >= 0 AND seller_gst_paise <= seller_total_paise),
                        updated_at TEXT NOT NULL,
                        updated_by TEXT NOT NULL,
                        delivery_cost_paise INTEGER CHECK(delivery_cost_paise >= 0))""")
                    if not self._has_table(con):
                        con.execute(f"ALTER TABLE {TABLE} ADD COLUMN delivery_cost_paise INTEGER CHECK(delivery_cost_paise >= 0)")
                    previous = con.execute(f"SELECT seller_total_paise,seller_gst_paise,delivery_cost_paise FROM {TABLE} WHERE order_id=?",
                                           (order_id,)).fetchone()
                    if "deliveryCost" not in payload and previous:
                        delivery_cost = previous[2]
                    con.execute(f"""INSERT INTO {TABLE} (order_id,seller_total_paise,seller_gst_paise,updated_at,updated_by,delivery_cost_paise)
                        VALUES(?,?,?,?,?,?) ON CONFLICT(order_id) DO UPDATE SET
                        seller_total_paise=excluded.seller_total_paise,
                        seller_gst_paise=excluded.seller_gst_paise,
                        updated_at=excluded.updated_at,updated_by=excluded.updated_by,
                        delivery_cost_paise=excluded.delivery_cost_paise""",
                        (order_id,total,gst,now,admin_id,delivery_cost))
                    con.execute("COMMIT")
                except BaseException:
                    con.execute("ROLLBACK")
                    raise
            finally:
                con.close()
        self.record_action(admin_id, "order_profit_updated", "order", order_id, "success", {
            "sellerTotal": _rupees(total), "sellerGst": _rupees(gst), "deliveryCost": _rupees(delivery_cost),
            "previousSellerTotal": _rupees(previous[0]) if previous else None,
            "previousSellerGst": _rupees(previous[1]) if previous else None,
            "previousDeliveryCost": _rupees(previous[2]) if previous else None,
        })
        return {"orderId": order_id, "sellerTotal": _rupees(total), "sellerGst": _rupees(gst),
                "deliveryCost": _rupees(delivery_cost), "updatedAt": now}

    def overview(self, month):
        base = self.order_documents.month_overview(month)
        rows = base["orders"]
        saved = self._values({r["orderId"] for r in rows})
        snapshots = self.orders()
        gross_paise = net_paise = 0
        gross_count = net_count = 0
        customer_gst_count = 0
        for row in rows:
            order_id = row["orderId"]
            order = snapshots.get(order_id, {})
            c_total = _paise(row["orderTotal"], "customer total")
            customer_delivery = _customer_delivery(
                order, order_id=order_id, order_total=c_total, invoice_path=self.invoice_path
            )
            if customer_delivery is not None and c_total is not None and customer_delivery > c_total:
                customer_delivery = None
            c_gst, source = _customer_gst(
                order, order_id=order_id, total=c_total,
                invoice_path=self.invoice_path, registry_path=self.registry_path,
                service_policy_path=self.service_policy_path,
            )
            if c_gst is not None and c_total is not None and c_gst > c_total:
                c_gst, source = None, "inconsistent"
            rec = saved.get(order_id)
            s_total, s_gst = (rec["seller_total_paise"], rec["seller_gst_paise"]) if rec else (None,None)
            delivery_cost = rec["delivery_cost_paise"] if rec else None
            gross = (c_total - s_total - delivery_cost) if (
                c_total is not None and s_total is not None and delivery_cost is not None
            ) else None
            net = (gross - c_gst + s_gst) if gross is not None and c_gst is not None else None
            row.update({
                "customerGst": _rupees(c_gst), "customerGstSource": source,
                "sellerTotal": _rupees(s_total), "sellerGst": _rupees(s_gst),
                "customerDeliveryCharge": _rupees(customer_delivery),
                "deliveryCost": _rupees(delivery_cost),
                "profitWithGst": _rupees(gross), "profitAfterGst": _rupees(net),
                "profitUpdatedAt": rec["updated_at"] if rec else None,
            })
            if c_gst is not None:
                customer_gst_count += 1
            if gross is not None:
                gross_count += 1; gross_paise += gross
            if net is not None:
                net_count += 1; net_paise += net
        base["summary"].update({
            "monthProfitWithGst": _rupees(gross_paise) if gross_count else None,
            "monthProfitAfterGst": _rupees(net_paise) if net_count else None,
            "sellerTotalsEntered": sum(r["sellerTotal"] is not None for r in rows),
            "deliveryCostsEntered": sum(r["deliveryCost"] is not None for r in rows),
            "profitRowsComplete": gross_count,
            "afterGstOrdersComplete": net_count,
            "customerGstAvailable": customer_gst_count,
            "profitOrdersTotal": len(rows),
            "profitWithGstComplete": gross_count == len(rows) and bool(rows),
            "profitAfterGstComplete": net_count == len(rows) and bool(rows),
        })
        return base

    def export_csv(self, month):
        data = self.overview(validate_month(month))
        out = io.StringIO(newline="")
        writer = csv.writer(out)
        writer.writerow(("order_id", "delivered_date", "customer", "stores",
                         "customer_total_inr", "customer_gst_inr", "gst_source",
                         "seller_total_inr", "seller_gst_inr", "customer_delivery_charge_inr", "delivery_cost_inr",
                         "profit_with_gst_inr", "profit_after_gst_inr", "seller_bill_count"))
        for row in data["orders"]:
            writer.writerow([_safe_csv(v) for v in (
                row["orderId"],row["deliveredDate"],row["customerName"],
                "; ".join(store["storeName"] for store in row["stores"]),
                row["orderTotal"], row["customerGst"],row["customerGstSource"],
                row["sellerTotal"],row["sellerGst"],row["customerDeliveryCharge"],row["deliveryCost"],
                row["profitWithGst"],row["profitAfterGst"],
                len(row["bills"]))])
        summary = data["summary"]
        writer.writerow([])
        writer.writerow(["MONTH TOTAL (known entries only)", "", "", "", summary["orderTotal"], "", "", "", "", "", "",
                         summary["monthProfitWithGst"],summary["monthProfitAfterGst"],""])
        writer.writerow(["Completed orders", "", "", "", "", "", "",
                         str(summary["sellerTotalsEntered"]) + "/" + str(summary["profitOrdersTotal"]), "", "",
                         str(summary["deliveryCostsEntered"]) + "/" + str(summary["profitOrdersTotal"]),
                         str(summary["profitRowsComplete"]) + "/" + str(summary["profitOrdersTotal"]),
                         str(summary["afterGstOrdersComplete"]) + "/" + str(summary["profitOrdersTotal"]), ""])
        writer.writerow(["NOTICE: Customer delivery charge is included in customer total and is not added again. Profit excludes missing seller or delivery cost entries; GST credit eligibility and other expenses are not verified. Not a GST return."])
        return b"\xef\xbb\xbf" + out.getvalue().encode("utf-8")
