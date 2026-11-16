"""Authenticated admin/customer gateway for Vibe4You issued invoices.

No public endpoint may issue an invoice. Admin issuance reads ONLY a private
server-side activation policy; clients cannot choose GST rate or supplier address.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from scripts.invoice_ledger import InvoiceLedger
    from scripts.tax_document_pdf import render_issued_tax_document_pdf
    from scripts.gst_invoice_draft import InvoiceDraftError
except ModuleNotFoundError:  # deployed scripts directory imports directly
    from invoice_ledger import InvoiceLedger
    from tax_document_pdf import render_issued_tax_document_pdf
    from gst_invoice_draft import InvoiceDraftError


_STATE_CODES={
    "andhra pradesh":"37", "arunachal pradesh":"12", "assam":"18",
    "bihar":"10", "chandigarh":"04", "chhattisgarh":"22",
    "delhi":"07", "nct of delhi":"07", "goa":"30",
    "gujarat":"24", "haryana":"06", "himachal pradesh":"02",
    "jammu and kashmir":"01", "jharkhand":"20", "karnataka":"29",
    "kerala":"32", "ladakh":"38", "lakshadweep":"31",
    "madhya pradesh":"23", "m.p.":"23", "manipur":"14",
    "meghalaya":"17", "mizoram":"15", "nagaland":"13",
    "odisha":"21", "orissa":"21", "puducherry":"34", "punjab":"03",
    "rajasthan":"08", "sikkim":"11", "tamil nadu":"33",
    "telangana":"36", "tripura":"16", "uttar pradesh":"09",
    "uttarakhand":"05", "west bengal":"19",
    "andaman and nicobar islands":"35",
    "dadra and nagar haveli and daman and diu":"26",
    "maharashtra":"27",
}


class InvoiceGateway:
    """No changes to order/checkout/gateway. Separate accounting-ledger files."""

    def __init__(self, data_dir: Path):
        self.data_dir=Path(data_dir)
        self.activation=self.data_dir/"gst-invoice-activation.json"
        self.ledger_path=self.data_dir/"gst-invoice-ledger.sqlite3"

    def _ledger(self) -> InvoiceLedger:
        return InvoiceLedger(self.ledger_path)

    def configuration(self) -> dict[str, Any]:
        if not self.activation.is_file():
            raise InvoiceDraftError(
                "GST invoice issuance is not configured; registration address, "
                "rates and lawful issuance procedure must be verified"
            )
        try:
            content=json.loads(self.activation.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise InvoiceDraftError("GST activation policy is invalid") from exc
        if not isinstance(content,dict):
            raise InvoiceDraftError("GST activation must be an object")
        return content

    def issued_for_order(self, order_id: str) -> dict[str, Any] | None:
        if not self.ledger_path.is_file():
            return None
        return self._ledger().fetch_for_order(order_id)

    def download_issued(self, order_id: str) -> bytes:
        document=self.issued_for_order(order_id)
        if document is None:
            raise InvoiceDraftError(
                "GST invoice not issued for this order; download the payment receipt meanwhile"
            )
        return render_issued_tax_document_pdf(document)

    def issue_from_order(self, order: dict[str, Any], *, issue_date: str) -> dict[str, Any]:
        raise InvoiceDraftError("GST invoice issuance not yet activated")
        settings=self.configuration()
        tax_policy=dict(settings.get("tax_policy") or {})
        address=order.get("address") or {}
        state=str(address.get("state") or "").strip()
        code=_STATE_CODES.get(state.casefold())
        if code is None:
            raise InvoiceDraftError("Cannot verify customer's GST place of supply")
        tax_policy["place_of_supply_state"]=state
        tax_policy["place_of_supply_state_code"]=code
        # 'True' here indicates the registered official state-code mapping
        # was matched; other classification approvals are server-side settings.
        tax_policy["place_of_supply_verified"]=True
        return self._ledger().issue(
            order,issue_date=issue_date,tax_policy=tax_policy,
            profile=dict(settings.get("seller") or {}),
            approval=dict(settings.get("approval") or {})
        )
