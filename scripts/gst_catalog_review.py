"""Private, approval-gated Vibe4You GST catalogue review and CSV import.

Rates are NEVER inferred from names/categories. An approved CA review CSV
requires an explicit APPROVE marker per row, documentary evidence and a
verified GST effective date. This module never adjusts selling prices.
"""
from __future__ import annotations

import csv
import io
from collections import Counter
from datetime import date
from typing import Any

try:
    from gst_official_suggestions import suggest, customer_price
except ModuleNotFoundError:
    from scripts.gst_official_suggestions import suggest, customer_price

try:
    from gst_invoice_draft import InvoiceDraftError
except ModuleNotFoundError:
    from scripts.gst_invoice_draft import InvoiceDraftError

FIELDS=(
    "productId","productName","category","status","HSN","gstRate",
    "supplyType","effectiveFrom","evidence","approval","approvedAt",
    "suggestedGstRate","suggestionConfidence","suggestionSource",
    "suggestionRule","suggestionReviewReason","priceSensitive",
)
# Previously exported review sheets remain valid after suggestion columns.
REQUIRED_IMPORT_FIELDS=FIELDS[:11]
MAX_CSV_BYTES=2_000_000


def _safe_cell(value: Any) -> str:
    # Prevent formula execution when review CSV is opened in Excel/Sheets.
    text=str(value if value is not None else "").replace("\x00","").replace("\r"," ").replace("\n"," ")
    text=text[:1000]
    if text.lstrip().startswith(("=","+","-","@")):
        text="'"+text
    return text


def catalogue_rows(products: list[dict[str, Any]],
                   existing: list[dict[str, Any]]) -> list[dict[str,str]]:
    lookup={str(r["product_id"]):r for r in existing}
    rows=[]
    for product in products:
        if not isinstance(product,dict):
            continue
        pid=str(product.get("id") or "")
        if not pid:
            continue
        approved=lookup.get(pid) or {}
        proposal=suggest(product) if not approved else {"rate":None,"confidence":"ALREADY_APPROVED",
            "source":"","rule":"","reason":"","priceSensitive":False}
        clear=proposal.get("confidence")=="HIGH" and not approved
        source_note=(
            "Official GST rate: Notification 9/2025 Integrated Tax (Rate), "
            "Schedule II, HSN 9102, effective 22-09-2025. "
            +str(proposal.get("source") or "")
        ) if clear else ""
        row={
            "productId":pid,
            "productName":_safe_cell(product.get("name") or ""),
            "category":_safe_cell(product.get("category") or ""),
            "status":_safe_cell(product.get("status") or ""),
            "HSN":str(approved.get("hsn_code") or ""),
            "gstRate":str(approved.get("gst_rate") or (proposal["rate"] if clear else "")),
            "supplyType":str(approved.get("supply_type") or ("taxable" if clear else "")),
            "effectiveFrom":str(approved.get("effective_from") or (
                proposal["effectiveFrom"] if clear else ""
            )),
            "evidence":_safe_cell(approved.get("evidence") or source_note),
            "approval":"",   # Rate proposals are NEVER approved on download.
            "approvedAt":str(approved.get("approved_at") or ""),
            "suggestedGstRate":str(proposal.get("rate") or ""),
            "suggestionConfidence":str(proposal.get("confidence") or ""),
            "suggestionSource":str(proposal.get("source") or ""),
            "suggestionRule":_safe_cell(proposal.get("rule") or ""),
            "suggestionReviewReason":_safe_cell(proposal.get("reason") or ""),
            "priceSensitive":"YES" if proposal.get("priceSensitive") else "NO",
        }
        rows.append(row)
    return sorted(rows,key=lambda r:(r["category"].lower(),r["productName"].lower(),r["productId"]))


def review_csv(products: list[dict[str,Any]],
               existing: list[dict[str,Any]]) -> bytes:
    buf=io.StringIO(newline="")
    writer=csv.DictWriter(buf,fieldnames=list(FIELDS),lineterminator="\r\n")
    writer.writeheader()
    writer.writerows(catalogue_rows(products,existing))
    return ("\ufeff"+buf.getvalue()).encode("utf-8")


def coverage(products: list[dict[str,Any]], existing: list[dict[str,Any]]) -> dict[str,Any]:
    active=[p for p in products if isinstance(p,dict) and p.get("status")=="PUBLISHED"]
    lookup={str(r.get("product_id") or ""):r for r in existing}
    today=date.today().isoformat()
    valid={
        str(p.get("id")) for p in active
        if (entry:=lookup.get(str(p.get("id")))) and
        entry.get("effective_from","9999-12-31")<=today and
        entry.get("supply_type") in ("taxable","exempt","nil_rated","zero_rated")
    }
    pending=[p for p in active if str(p.get("id")) not in valid]
    groups=Counter(str(p.get("category") or "Other") for p in pending)
    return {
        "published":len(active),
        "approved":len(valid),
        "pending":len(pending),
        "categoriesPending":dict(sorted(groups.items())),
        "issuanceEnabled":False,
    }


def parse_approved_csv(raw: str, products: list[dict[str,Any]]) -> list[dict[str,str]]:
    if not isinstance(raw,str) or not raw:
        raise InvoiceDraftError("Upload a GST review CSV")
    if len(raw.encode("utf-8"))>MAX_CSV_BYTES:
        raise InvoiceDraftError("GST review CSV is too large")
    try:
        reader=csv.DictReader(io.StringIO(raw.lstrip("\ufeff"),newline=""))
    except csv.Error as exc:
        raise InvoiceDraftError("Invalid GST review CSV") from exc
    if not reader.fieldnames or set(REQUIRED_IMPORT_FIELDS)-set(reader.fieldnames):
        raise InvoiceDraftError("GST review CSV columns are missing")
    known={
        str(p.get("id")) for p in products
        if isinstance(p,dict) and p.get("status")=="PUBLISHED"
    }
    result=[]
    used=set()
    for index,row in enumerate(reader,2):
        if not isinstance(row,dict) or None in row:
            raise InvoiceDraftError(f"Malformed GST CSV row {index}")
        marker=str(row.get("approval") or "").strip()
        if not marker:
            continue
        if marker!="APPROVE":
            raise InvoiceDraftError(f"GST row {index} must use exact APPROVE marker")
        pid=str(row.get("productId") or "").strip()
        if pid not in known:
            raise InvoiceDraftError(f"GST row {index} refers to a missing/unpublished product")
        if pid in used:
            raise InvoiceDraftError(f"Duplicate approved product at row {index}")
        used.add(pid)
        result.append({
            "productId":pid,"hsnCode":str(row.get("HSN") or "").strip(),
            "gstRate":str(row.get("gstRate") or "").strip(),
            "supplyType":str(row.get("supplyType") or "").strip(),
            "effectiveFrom":str(row.get("effectiveFrom") or "").strip(),
            "evidence":str(row.get("evidence") or "").strip(),
        })
        if len(result)>100:
            raise InvoiceDraftError("Approve up to 100 products per CSV upload")
    if not result:
        raise InvoiceDraftError("No approved rows. Enter APPROVE for the verified products")
    return result
