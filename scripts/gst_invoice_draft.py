"""GST-inclusive Vibe4You invoice calculation and safe PDF DRAFT generator.

This is a prepare-only module: NOT connected to checkout, issuance, invoice
number allocation, or production. It never invents product/delivery GST rates.
Prices represent FINAL customer-paid amounts, inclusive of applicable GST.
"""
from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

try:
    from receipt_pdf import (
        CONTENT_WIDTH, MARGIN, PAGE_HEIGHT, PdfDocument, clean_pdf_text, money, wrap_text,
    )
except ModuleNotFoundError:
    from scripts.receipt_pdf import (
        CONTENT_WIDTH, MARGIN, PAGE_HEIGHT, PdfDocument, clean_pdf_text, money, wrap_text,
    )

GSTIN = "23JVZPM8734E1ZT"
SELLER_LEGAL_NAME = "Manorama"
TRADE_NAME = "Vibe4You"
REQUESTED_NEW_ADDRESS = (
    "Building No. 68, Shaktinagar Vistar, Neemuch, Madhya Pradesh - 458441"
)
# 19 October 2026: the proprietor confirmed that the GST registration
# certificate has been updated for this address with PIN 458441.
# This records an owner attestation, NOT an independently inspected REG-06.
# Issuance still requires the separate tax-classification and policy gates.
ADDRESS_AMENDMENT_VERIFIED = True
PENNY = Decimal("0.01")


class InvoiceDraftError(ValueError):
    """Invoice could not be calculated safely without verified tax inputs."""


def _decimal(value: Any, label: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise InvoiceDraftError(f"{label} is required")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise InvoiceDraftError(f"Invalid {label}") from exc
    if not result.is_finite():
        raise InvoiceDraftError(f"Invalid {label}")
    return result


def _rupees(value: Any, label: str) -> Decimal:
    amount = _decimal(value, label)
    if amount < 0 or amount != amount.quantize(PENNY):
        raise InvoiceDraftError(f"{label} must be nonnegative rupees/paise")
    return amount


def _gst_rate(value: Any, label: str) -> Decimal:
    rate = _decimal(value, label)
    if rate < 0 or rate > 100 or rate.as_tuple().exponent < -2:
        raise InvoiceDraftError(f"Invalid {label}")
    return rate


def _taxable_and_tax(gross: Decimal, rate: Decimal) -> tuple[Decimal, Decimal]:
    # Rule 35: GST is carved OUT of the paid price, not added on top.
    tax = (gross * rate / (Decimal("100") + rate)).quantize(
        PENNY, rounding=ROUND_HALF_UP
    )
    return gross - tax, tax


def calculate_gst_inclusive_draft(data: dict[str, Any]) -> dict[str, Any]:
    """Validate explicit tax metadata and return a balanced read-only draft.

    Each item gross_amount must be the FINAL, post-discount line payable price.
    Delivery GST rate must be supplied separately by verified tax policy.
    No inference from product names, HSN codes, or shop details is permitted.
    """
    if not isinstance(data, dict):
        raise InvoiceDraftError("Invoice input must be an object")
    order_id = str(data.get("order_id") or "").strip()
    invoice_number = str(data.get("invoice_number") or "").strip()
    issue_date = str(data.get("issue_date") or "").strip()
    if not order_id:
        raise InvoiceDraftError("Order reference required")
    if not re.fullmatch(r"[A-Za-z0-9/-]{1,16}", invoice_number):
        raise InvoiceDraftError("Invoice number must be 1-16 permitted characters")
    try:
        date.fromisoformat(issue_date)
    except ValueError as exc:
        raise InvoiceDraftError("Valid invoice issue date required (YYYY-MM-DD)") from exc

    address = data.get("customer_address")
    if not isinstance(address, dict) or not str(address.get("name") or "").strip():
        raise InvoiceDraftError("Customer name/address is required")
    state_code = str(data.get("place_of_supply_state_code") or "").strip()
    state_name = str(data.get("place_of_supply_state") or "").strip()
    if not re.fullmatch(r"[0-9]{2}", state_code) or not state_name:
        raise InvoiceDraftError("Verified place of supply state/name required")
    if not re.fullmatch(r"[0-9]{6}", str(address.get("pincode") or "")):
        raise InvoiceDraftError("Customer delivery PIN is required")

    raw_items = data.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        raise InvoiceDraftError("At least one product is required")

    omit_hsn = data.get("hsn_optional_for_b2c") is True
    rows = []
    for index, product in enumerate(raw_items, 1):
        if not isinstance(product, dict):
            raise InvoiceDraftError("Invalid product row")
        title = clean_pdf_text(product.get("product_name"))
        if not title:
            raise InvoiceDraftError(f"Item {index}: product name missing")
        qty = _decimal(product.get("quantity"), f"Item {index} quantity")
        if qty <= 0 or qty != qty.to_integral_value():
            raise InvoiceDraftError(f"Item {index}: positive whole quantity needed")
        unit = clean_pdf_text(product.get("unit") or "PCS")
        hsn = str(product.get("hsn") or "").strip()
        if (not hsn and not omit_hsn) or (hsn and not re.fullmatch(r"[0-9]{2,8}", hsn)):
            raise InvoiceDraftError(f"Item {index}: required HSN missing or invalid")
        gross = _rupees(product.get("gross_amount"), f"Item {index} gross amount")
        pre_discount_gross = _rupees(
            product.get("pre_discount_gross", gross), f"Item {index} pre-discount amount"
        )
        discount_amount = _rupees(
            product.get("discount_amount", "0.00"), f"Item {index} discount"
        )
        if pre_discount_gross != gross + discount_amount:
            raise InvoiceDraftError(f"Item {index}: discount does not reconcile to line total")
        rate = _gst_rate(product.get("gst_rate"), f"Item {index} GST rate")
        taxable, tax = _taxable_and_tax(gross, rate)
        rows.append({
            "product_name": title, "hsn": hsn, "quantity": int(qty), "unit": unit,
            "gst_rate": rate, "gross": gross, "taxable": taxable, "tax": tax,
            "pre_discount_gross": pre_discount_gross,
            "discount_amount": discount_amount,
        })

    delivery = _rupees(data.get("delivery_gross", 0), "Delivery gross")
    if delivery:
        delivery_rate = _gst_rate(
            data.get("delivery_gst_rate"), "Delivery GST rate"
        )
        delivery_code = str(data.get("delivery_hsn_sac") or "").strip()
        if (not delivery_code and not omit_hsn) or (
            delivery_code and not re.fullmatch(r"[0-9]{2,8}", delivery_code)
        ):
            raise InvoiceDraftError("Required delivery SAC missing or invalid")
        delivery_taxable, delivery_tax = _taxable_and_tax(delivery, delivery_rate)
        rows.append({
            "product_name": "Delivery / shipping", "hsn": delivery_code,
            "quantity": 1, "unit": "SERVICE", "gst_rate": delivery_rate,
            "gross": delivery, "taxable": delivery_taxable, "tax": delivery_tax,
            "pre_discount_gross": delivery, "discount_amount": Decimal("0.00"),
        })

    gross_total = sum((row["gross"] for row in rows), Decimal("0.00"))
    expected = _rupees(data.get("customer_paid_total"), "Customer paid total")
    if gross_total != expected:
        raise InvoiceDraftError(
            f"Customer total mismatch: invoice {gross_total} vs paid {expected}"
        )

    taxable_total = sum((row["taxable"] for row in rows), Decimal("0.00"))
    gst_total = sum((row["tax"] for row in rows), Decimal("0.00"))
    if taxable_total + gst_total != gross_total:
        raise InvoiceDraftError("Tax reconciliation failed")

    # Explicit per-rate reconciliation for mixed-rate taxable baskets.
    by_rate = {}
    for row in rows:
        key = str(row["gst_rate"])
        aggregate = by_rate.setdefault(
            key, {"rate": row["gst_rate"], "gross": Decimal("0.00"),
                  "taxable": Decimal("0.00"), "tax": Decimal("0.00")})
        for field in ("gross", "taxable", "tax"):
            aggregate[field] += row[field]

    interstate = state_code != GSTIN[:2]
    if interstate:
        cgst = sgst = Decimal("0.00")
        igst = gst_total
    else:
        # A one-paisa allocation adjustment preserves exact arithmetic on
        # odd-paisa aggregate taxes; accountants must review roundings.
        cgst = (gst_total / 2).quantize(PENNY, rounding=ROUND_HALF_UP)
        sgst = gst_total - cgst
        igst = Decimal("0.00")
    return {
        "order_id": order_id, "invoice_number": invoice_number,
        "issue_date": issue_date, "customer_address": address,
        "place_of_supply_state": state_name,
        "place_of_supply_state_code": state_code,
        "interstate": interstate, "items": rows,
        "hsn_optional_for_b2c": omit_hsn,
        "gst_rate_summary": [by_rate[k] for k in sorted(by_rate, key=Decimal)],
        "gross_total": gross_total,
        "taxable_total": taxable_total, "gst_total": gst_total,
        "cgst": cgst, "sgst": sgst, "igst": igst,
        "seller": {"legal_name": SELLER_LEGAL_NAME, "trade_name": TRADE_NAME,
                   "gstin": GSTIN, "requested_address": REQUESTED_NEW_ADDRESS},
        "address_pending_verification": not ADDRESS_AMENDMENT_VERIFIED,
        "status": "DRAFT_NOT_ISSUED",
    }


_COLS = [
    ("PRODUCT / SERVICE", 168), ("HSN", 50), ("QTY", 35),
    ("GST %", 42), ("TAXABLE", 78), ("GST", 65), ("TOTAL", 77),
]


def _table_header(doc: PdfDocument, page: list[str], y: float) -> float:
    doc.rect(page, MARGIN, y-25, CONTENT_WIDTH, 25, fill=(0.10, 0.10, 0.11))
    x = MARGIN + 4
    for label, width in _COLS:
        doc.text(page, x, y-16, label, size=6.5, bold=True, color=(1,1,1))
        x += width
    return y-25


def build_gst_invoice_draft_pdf(draft: dict[str, Any]) -> bytes:
    """Render a clearly watermarked PREVIEW; never represent it as issued."""
    if draft.get("status") != "DRAFT_NOT_ISSUED":
        raise InvoiceDraftError("Only validated draft data can be rendered")

    doc = PdfDocument()
    page = doc.new_page()
    def new_page() -> tuple[list[str], float]:
        p = doc.new_page()
        doc.text(p, MARGIN, PAGE_HEIGHT-45, "Vibe4You - DRAFT TAX INVOICE",
                 size=14, bold=True)
        doc.text(p, MARGIN, PAGE_HEIGHT-65, "NOT ISSUED - TAX SETTINGS & ISSUANCE PENDING", size=8)
        return p, _table_header(doc, p, PAGE_HEIGHT-100)

    doc.rect(page, 0, PAGE_HEIGHT-95, 595, 95, fill=(0.06,0.06,0.07))
    doc.text(page, MARGIN, PAGE_HEIGHT-43, "Vibe4You", size=22, bold=True, color=(1,1,1))
    doc.text(page, MARGIN, PAGE_HEIGHT-65, "DRAFT TAX INVOICE - NOT ISSUED",
             size=10.5, bold=True, color=(1,1,1))
    doc.text(page, 370, PAGE_HEIGHT-44, "GST-INCLUSIVE PRICES", size=8.5, color=(1,1,1))
    y = PAGE_HEIGHT-122
    doc.text(page, MARGIN, y, "SELLER: Vibe4You", size=9, bold=True); y -= 15
    doc.text(page, MARGIN, y, f"GSTIN: {GSTIN}", size=9); y -= 15
    doc.text(page, MARGIN, y, f"REGISTERED ADDRESS (OWNER CONFIRMED):", size=8, bold=True); y -= 13
    doc.text(page, MARGIN, y, REQUESTED_NEW_ADDRESS, size=8.1); y -= 20
    doc.text(page, MARGIN, y, f"Draft No: {draft['invoice_number']}  |  Date: {draft['issue_date']}", size=9); y -= 15
    doc.text(page, MARGIN, y, f"Order Ref: {draft['order_id']}", size=9); y -= 20
    customer=draft["customer_address"]
    doc.text(page, MARGIN, y, f"Bill/Ship to: {clean_pdf_text(customer['name'])}", size=9, bold=True); y -= 14
    addr=" ".join(clean_pdf_text(customer.get(k)) for k in ("street","city","state","pincode"))
    for line in wrap_text(addr, CONTENT_WIDTH, 8.5):
        doc.text(page, MARGIN, y, line, size=8.5); y -= 13
    doc.text(page, MARGIN, y, f"Place of Supply: {draft['place_of_supply_state']} ({draft['place_of_supply_state_code']})",
             size=8.5); y -= 23
    y = _table_header(doc, page, y)
    for entry in draft["items"]:
        cells=[
            entry["product_name"], "" if draft.get("hsn_optional_for_b2c") else entry["hsn"],
            f"{entry['quantity']} {entry['unit']}", f"{entry['gst_rate']:g}%",
            money(entry["taxable"]), money(entry["tax"]), money(entry["gross"])
        ]
        wrapped=[wrap_text(value, width-8, 7) for value, (_, width) in zip(cells, _COLS)]
        row_height=max(30, 11+max(len(lines) for lines in wrapped)*10)
        if y-row_height < 215:
            page,y=new_page()
        doc.rect(page, MARGIN, y-row_height, CONTENT_WIDTH, row_height,
                 stroke=(0.85,0.85,0.85))
        x=MARGIN+4
        for lines,(_,width) in zip(wrapped,_COLS):
            for n,line in enumerate(lines):
                doc.text(page,x,y-14-(n*10),line,size=7)
            x+=width
        y-=row_height
    if y < 205:
        page = doc.new_page(); y=PAGE_HEIGHT-55
        doc.text(page, MARGIN, y, "Vibe4You - DRAFT TAX INVOICE TOTALS", size=13, bold=True)
        y-=30
    y-=21
    for label, val in [
        ("Taxable value", draft["taxable_total"]),
        ("CGST (included)", draft["cgst"]),
        ("SGST (included)", draft["sgst"]),
        ("IGST (included)", draft["igst"]),
        ("Total GST included", draft["gst_total"]),
        ("Customer paid total", draft["gross_total"]),
    ]:
        if label.startswith(("CGST","SGST","IGST")) and val == 0:
            continue
        doc.text(page, 327, y, label, size=9, bold=label.startswith("Customer"))
        doc.text(page, 470, y, money(val), size=9, bold=label.startswith("Customer"))
        y-=16
    y-=12
    doc.text(page, MARGIN, y, "DRAFT ONLY - not an issued GST tax invoice.", size=8.5, bold=True)
    y-=16
    doc.text(page, MARGIN, y, "Activate only after GST rates, numbering and issuance workflow are approved.", size=7.7)
    return doc.build()


def require_issuance_prerequisites(*, registered_address_approved: bool,
                                   complete_pin_verified: bool,
                                   invoice_sequence_persisted: bool,
                                   authorised_signing_configured: bool) -> None:
    """Fail closed: issuance is not enabled by merely rendering this draft."""
    missing = [
        name for name, valid in (
            ("GST registered business address", registered_address_approved),
            ("seller address six-digit PIN", complete_pin_verified),
            ("atomic financial-year invoice numbering", invoice_sequence_persisted),
            ("authorised signing/issuance workflow", authorised_signing_configured),
        ) if valid is not True
    ]
    if missing:
        raise InvoiceDraftError("Cannot issue: " + ", ".join(missing))
    # Production issuer intentionally does not exist here.
    raise InvoiceDraftError("Issuance endpoint not implemented or deployed")
