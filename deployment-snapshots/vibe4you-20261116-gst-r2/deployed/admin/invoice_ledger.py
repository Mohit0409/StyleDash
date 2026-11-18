"""Local, transactional GST invoice ledger for Vibe4You (not wired to live APIs).

Activation explicitly requires registration, address, tax classification, IRN
applicability and lawful electronic-issuance approvals. Old orders are never
silently converted or re-invoiced.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

try:
    from gst_invoice_draft import InvoiceDraftError, calculate_gst_inclusive_draft
    from invoice_order_adapter import order_to_tax_draft_input
except ModuleNotFoundError:
    from scripts.gst_invoice_draft import InvoiceDraftError, calculate_gst_inclusive_draft
    from scripts.invoice_order_adapter import order_to_tax_draft_input


def _json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=str, ensure_ascii=True)


def _financial_year(day: date) -> str:
    start = day.year if day.month >= 4 else day.year - 1
    return f"{start % 100:02d}-{(start+1) % 100:02d}"


def _validate_approval(approval: dict[str, Any], profile: dict[str, Any]) -> None:
    for key in (
        "invoice_issuance_enabled",
        "gst_registration_confirmed",
        "seller_address_confirmed",
        "classifications_verified",
        "place_of_supply_verified",
        "shipping_tax_policy_verified",
        "einvoice_applicability_reviewed",
        "lawful_issuance_procedure_approved",
    ):
        if approval.get(key) is not True:
            raise InvoiceDraftError(f"Invoice issuance blocked: {key}")
    if approval.get("einvoice_required") is not False:
        # IRN/QR issuance is NOT implemented; absence of explicit exemption
        # must block rather than producing a potentially invalid invoice.
        raise InvoiceDraftError("IRN e-invoice applicability unresolved or required")
    if not re.fullmatch(r"[0-9]{6}", str(profile.get("pincode") or "")):
        raise InvoiceDraftError("Verified 6-digit registered seller PIN missing")
    if not str(profile.get("address") or "").strip():
        raise InvoiceDraftError("GST-verified seller address missing")
    if profile.get("gstin") != "23JVZPM8734E1ZT" or profile.get("legal_name") != "Manorama":
        raise InvoiceDraftError("Invoice seller must be Vibe4You legal GST registrant")


class InvoiceLedger:
    """SQLite immutable issued-invoice/credit-note snapshots, atomically numbered."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as con:
            con.executescript("""
                CREATE TABLE IF NOT EXISTS sequence (
                    fiscal TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    serial INTEGER NOT NULL,
                    PRIMARY KEY (fiscal, kind)
                );
                CREATE TABLE IF NOT EXISTS documents (
                    number TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    fiscal TEXT NOT NULL,
                    order_id TEXT NOT NULL,
                    linked_invoice TEXT,
                    issue_date TEXT NOT NULL,
                    snapshot_json TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );
                CREATE UNIQUE INDEX IF NOT EXISTS one_tax_invoice_per_order
                    ON documents(order_id) WHERE kind='TAX_INVOICE';
                CREATE INDEX IF NOT EXISTS linked_credit_notes
                    ON documents(linked_invoice) WHERE kind='CREDIT_NOTE';
            """)

    @contextmanager
    def _conn(self):
        con=sqlite3.connect(str(self.path), timeout=20, isolation_level=None)
        try:
            con.execute("PRAGMA busy_timeout=20000")
            con.execute("PRAGMA journal_mode=WAL")
            con.row_factory=sqlite3.Row
            yield con
        finally:
            con.close()

    @staticmethod
    def _serial(con: sqlite3.Connection, fiscal: str, kind: str) -> str:
        con.execute(
            "INSERT INTO sequence(fiscal,kind,serial) VALUES(?,?,0) "
            "ON CONFLICT(fiscal,kind) DO NOTHING", (fiscal,kind))
        con.execute("UPDATE sequence SET serial=serial+1 WHERE fiscal=? AND kind=?",
                    (fiscal,kind))
        n=con.execute("SELECT serial FROM sequence WHERE fiscal=? AND kind=?",
                      (fiscal,kind)).fetchone()[0]
        if n > 999999:
            raise InvoiceDraftError("Annual document series exhausted")
        prefix = "V4Y" if kind=="TAX_INVOICE" else "VCN"
        result=f"{prefix}/{fiscal}/{n:06d}"
        if len(result) > 16:
            raise InvoiceDraftError("Invalid GST serial format")
        return result

    @staticmethod
    def _insert(con: sqlite3.Connection, number: str, kind: str,
                order_id: str, fiscal: str, issue_date: str,
                data: dict[str, Any], *, linked: str | None = None) -> None:
        body=_json(data)
        digest=hashlib.sha256(body.encode("utf-8")).hexdigest()
        con.execute(
            "INSERT INTO documents(number,kind,fiscal,order_id,linked_invoice,"
            "issue_date,snapshot_json,sha256,recorded_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (number,kind,fiscal,order_id,linked,issue_date,body,digest,
             datetime.now(timezone.utc).isoformat())
        )

    def fetch(self, number: str) -> dict[str, Any] | None:
        with self._conn() as con:
            row=con.execute("SELECT * FROM documents WHERE number=?", (number,)).fetchone()
            if row is None: return None
            if hashlib.sha256(row["snapshot_json"].encode("utf-8")).hexdigest()!=row["sha256"]:
                raise InvoiceDraftError("Stored invoice integrity check failed")
            return json.loads(row["snapshot_json"])

    def fetch_for_order(self, order_id: str) -> dict[str, Any] | None:
        with self._conn() as con:
            row=con.execute(
                "SELECT number FROM documents WHERE kind='TAX_INVOICE' AND order_id=?",
                (order_id,)
            ).fetchone()
        return self.fetch(row["number"]) if row else None

    def issue(self, order: dict[str, Any], *, issue_date: str,
              policy: dict[str, Any], profile: dict[str, Any],
              approval: dict[str, Any]) -> dict[str, Any]:
        _validate_approval(approval, profile)
        if order.get("status") not in ("packed","shipped","out_for_delivery","delivered"):
            raise InvoiceDraftError("Invoice must be issued for an eligible dispatch/order status")
        if order.get("isPaymentTestOrder") is True or order.get("fulfillmentRequired") is False:
            raise InvoiceDraftError("Cannot invoice payment test order")
        try:
            day=date.fromisoformat(issue_date)
        except ValueError as exc:
            raise InvoiceDraftError("Invoice date is invalid") from exc
        if day > datetime.now(timezone(timedelta(hours=5, minutes=30))).date():
            raise InvoiceDraftError("Cannot issue a future-dated invoice")
        fiscal=_financial_year(day)
        omission_requested = policy.get("b2c_hsn_omission_approved") is True
        if omission_requested and approval.get("preceding_fy_aato_up_to_5cr") is not True:
            raise InvoiceDraftError(
                "HSN omission requires verified preceding-financial-year AATO up to INR 5 crore"
            )
        # HSN may be omitted ONLY for unregistered (B2C) recipients and
        # taxpayers with a verified prior-year AATO of at most INR 5 crore.
        tax_policy=dict(policy)
        tax_policy["hsn_optional_for_b2c"]=(
            omission_requested and not bool(str(order.get("recipientGstin") or "").strip())
        )
        order_id=str(order.get("id") or "")
        if not order_id:
            raise InvoiceDraftError("Order ID is required")

        with self._conn() as con:
            con.execute("BEGIN IMMEDIATE")
            try:
                existing=con.execute(
                    "SELECT number,snapshot_json,sha256 FROM documents "
                    "WHERE order_id=? AND kind='TAX_INVOICE'", (order_id,)
                ).fetchone()
                if existing:
                    if hashlib.sha256(existing["snapshot_json"].encode("utf-8")).hexdigest()!=existing["sha256"]:
                        raise InvoiceDraftError("Existing invoice integrity check failed")
                    # Idempotent: NEVER recalculate from a subsequently edited order.
                    con.commit()
                    return json.loads(existing["snapshot_json"])
                number=self._serial(con,fiscal,"TAX_INVOICE")
                raw=order_to_tax_draft_input(
                    order, invoice_number=number, issue_date=issue_date, tax_policy=tax_policy
                )
                draft=calculate_gst_inclusive_draft(raw)
                draft.update({
                    "status":"ISSUED","address_pending_verification":False,
                    "seller":{
                        "legal_name":profile["legal_name"],"trade_name":"Vibe4You",
                        "gstin":profile["gstin"],"address":profile["address"],
                        "pincode":str(profile["pincode"])
                    },
                    "reverse_charge":False,
                    "recipient_gstin":str(order.get("recipientGstin") or ""),
                    "payment_status":str(order.get("paymentStatus") or ""),
                    "payment_method":str(order.get("paymentMethod") or ""),
                    "cod_advance_amount":str(order.get("codAdvanceAmount") or "0"),
                    "cod_advance_paid":order.get("codAdvancePaid") is True,
                    "authorised_signatory":str(profile.get("authorised_signatory") or ""),
                    "electronic_issuance_approved":True,
                    "document_kind":"TAX_INVOICE",
                    "source_order_status":order["status"],
                    "classification_approved_at":str(approval.get("approved_at") or ""),
                })
                if not draft["authorised_signatory"]:
                    raise InvoiceDraftError("Authorised signatory must be configured")
                self._insert(con,number,"TAX_INVOICE",order_id,fiscal,issue_date,draft)
                con.commit()
                return json.loads(_json(draft))
            except Exception:
                con.rollback()
                raise

    def credit_note(
        self, invoice_number: str, *, issue_date: str,
        credited_gross_by_row: dict[int, str], reason: str,
        approved: bool = False,
    ) -> dict[str, Any]:
        """Create an immutable note for explicitly authorised refunded gross per row.

        Each row's tax is reversed at its original GST rate. Partial notes
        cannot exceed original quantities/value or earlier credit notes.
        No payment/refund is initiated by this method.
        """
        if approved is not True:
            raise InvoiceDraftError("Credit note requires refund/return approval")
        if not reason or len(reason.strip())<3:
            raise InvoiceDraftError("Credit note reason required")
        if not credited_gross_by_row:
            raise InvoiceDraftError("Choose at least one refunded component")
        try:
            day=date.fromisoformat(issue_date)
        except ValueError as exc:
            raise InvoiceDraftError("Invalid credit note issue date") from exc
        fiscal=_financial_year(day)

        with self._conn() as con:
            con.execute("BEGIN IMMEDIATE")
            try:
                orig=con.execute(
                    "SELECT * FROM documents WHERE number=? AND kind='TAX_INVOICE'",
                    (invoice_number,)
                ).fetchone()
                if orig is None:
                    raise InvoiceDraftError("Original issued invoice not found")
                source=json.loads(orig["snapshot_json"])
                if hashlib.sha256(orig["snapshot_json"].encode()).hexdigest()!=orig["sha256"]:
                    raise InvoiceDraftError("Source invoice integrity failure")
                if day < date.fromisoformat(source["issue_date"]):
                    raise InvoiceDraftError("Credit note cannot predate invoice")
                used=[Decimal("0.00") for _ in source["items"]]
                credited_tax=[Decimal("0.00") for _ in source["items"]]
                for prev in con.execute(
                    "SELECT snapshot_json,sha256 FROM documents "
                    "WHERE linked_invoice=? AND kind='CREDIT_NOTE'", (invoice_number,)
                ):
                    if hashlib.sha256(prev["snapshot_json"].encode()).hexdigest()!=prev["sha256"]:
                        raise InvoiceDraftError("Prior credit note integrity failure")
                    note=json.loads(prev["snapshot_json"])
                    for line in note["credited_lines"]:
                        used[int(line["source_index"])] += Decimal(str(line["gross"]))
                        credited_tax[int(line["source_index"])] += Decimal(str(line["tax"]))
                output=[]
                for index, amount in sorted(credited_gross_by_row.items()):
                    if isinstance(index,bool) or not isinstance(index,int) or index < 0 or index >= len(used):
                        raise InvoiceDraftError("Invalid refunded row index")
                    value=Decimal(str(amount))
                    if not value.is_finite() or value<=0 or value!=value.quantize(Decimal("0.01")):
                        raise InvoiceDraftError("Credit amount must be positive paise")
                    available=Decimal(source["items"][index]["gross"])-used[index]
                    if value>available:
                        raise InvoiceDraftError("Credit would exceed uncredited invoice value")
                    item=source["items"][index]
                    rate=Decimal(item["gst_rate"])
                    original_tax=Decimal(str(item["tax"]))
                    tax_remaining=original_tax-credited_tax[index]
                    if tax_remaining < 0:
                        raise InvoiceDraftError("Existing credits exceed original item tax")
                    if value==available:
                        # The last credit removes any per-credit rounding difference.
                        gst=tax_remaining
                    else:
                        gst=min(tax_remaining,(value*rate/(Decimal("100")+rate)).quantize(Decimal("0.01")))
                    if gst>value:
                        raise InvoiceDraftError("Invalid GST credit allocation")
                    output.append({
                        "source_index":index,"product_name":item["product_name"],
                        "hsn":item["hsn"],"gst_rate":str(rate),
                        "gross":str(value),"taxable":str(value-gst),"tax":str(gst),
                    })
                number=self._serial(con,fiscal,"CREDIT_NOTE")
                total=sum((Decimal(line["gross"]) for line in output),Decimal("0"))
                tax=sum((Decimal(line["tax"]) for line in output),Decimal("0"))
                note={
                    "status":"ISSUED","document_kind":"CREDIT_NOTE","number":number,
                    "issue_date":issue_date,"reason":reason.strip(),
                    "linked_invoice":invoice_number,
                    "linked_invoice_date":source["issue_date"],
                    "order_id":source["order_id"],"seller":source["seller"],
                    "customer_address":source["customer_address"],
                    "place_of_supply_state":source["place_of_supply_state"],
                    "place_of_supply_state_code":source["place_of_supply_state_code"],
                    "interstate":source["interstate"],
                    "credited_lines":output,
                    "gross_total":str(total),"taxable_total":str(total-tax),"gst_total":str(tax),
                    "authorised_signatory":source["authorised_signatory"],
                    "hsn_optional_for_b2c":source.get("hsn_optional_for_b2c") is True,
                    "recipient_gstin":source.get("recipient_gstin") or "",
                    "recording_only_no_refund_execution":True,
                }
                self._insert(con,number,"CREDIT_NOTE",source["order_id"],
                             fiscal,issue_date,note,linked=invoice_number)
                con.commit()
                return note
            except Exception:
                con.rollback()
                raise
