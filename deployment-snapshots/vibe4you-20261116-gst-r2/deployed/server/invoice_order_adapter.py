"""Convert frozen checkout orders to GST-inclusive draft input, without mutation.

Only seller-approved, order-time GST classifications can be used. This module
does not infer HSN codes, delivery SAC, state codes, or tax rates.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_DOWN
from typing import Any

try:
    from gst_invoice_draft import InvoiceDraftError, _rupees
except ModuleNotFoundError:
    from scripts.gst_invoice_draft import InvoiceDraftError, _rupees


def _paise(value: Any, label: str) -> int:
    return int(_rupees(value, label) * 100)


def _apportion_discount(gross_paise: list[int], discount_paise: int) -> list[int]:
    """Exact largest-remainder allocation, deterministic by input index."""
    total = sum(gross_paise)
    if not 0 <= discount_paise <= total:
        raise InvoiceDraftError("Discount exceeds subtotal")
    if total == 0:
        if discount_paise:
            raise InvoiceDraftError("Cannot discount zero subtotal")
        return [0 for _ in gross_paise]
    precise = [Decimal(value * discount_paise) / Decimal(total) for value in gross_paise]
    whole = [int(q.to_integral_value(rounding=ROUND_DOWN)) for q in precise]
    extra = discount_paise - sum(whole)
    order = sorted(range(len(whole)), key=lambda i: (-(precise[i] - whole[i]), i))
    for index in order[:extra]:
        whole[index] += 1
    assert sum(whole) == discount_paise
    return whole


def order_to_tax_draft_input(
    order: dict[str, Any],
    *,
    invoice_number: str,
    issue_date: str,
    tax_policy: dict[str, Any],
) -> dict[str, Any]:
    """Produce exactly paid, post-discount gross per row.

    Explicit policy inputs:
      place_of_supply_state, place_of_supply_state_code;
      delivery_gst_rate, delivery_hsn_sac if delivery fee > 0;
      service_gst_rate, service_hsn_sac if try-at-home fee > 0.
    All item HSN/GST rates must be captured in the ORIGINAL immutable order,
    not discovered from today's mutable product catalogue.
    """
    if not isinstance(order, dict) or not isinstance(tax_policy, dict):
        raise InvoiceDraftError("Validated order and tax policy are required")
    if order.get("isPaymentTestOrder") is True or order.get("fulfillmentRequired") is False:
        raise InvoiceDraftError("Payment-test orders cannot generate tax invoices")
    if str(order.get("status") or "").lower() in ("cancelled", "payment_pending", "failed"):
        raise InvoiceDraftError("Unfulfilled/cancelled orders are not invoice-ready")
    lines = order.get("items")
    if not isinstance(lines, list) or not lines:
        raise InvoiceDraftError("Original order lines are required")

    gross_paise = []
    for n, line in enumerate(lines, 1):
        if not isinstance(line, dict):
            raise InvoiceDraftError("Invalid order item")
        qty = line.get("quantity")
        if isinstance(qty, bool) or not isinstance(qty, int) or qty < 1:
            raise InvoiceDraftError(f"Invalid original item {n} quantity")
        gross = _paise(line.get("lineTotal"), f"Item {n} gross")
        # The line total is frozen when an order is placed; fail on tampering.
        unit = _rupees(line.get("unitPrice"), f"Item {n} unit price")
        if unit * qty != Decimal(gross) / 100:
            raise InvoiceDraftError(f"Original item {n} price mismatch")
        gross_paise.append(gross)

    recorded_subtotal = _paise(order.get("subtotal"), "Order subtotal")
    if recorded_subtotal != sum(gross_paise):
        raise InvoiceDraftError("Order subtotal does not match product lines")
    discount = _paise(order.get("discount", 0), "Discount")
    allocations = _apportion_discount(gross_paise, discount)
    omit_hsn = tax_policy.get("hsn_optional_for_b2c") is True
    output = []
    for n, (line, gross, share) in enumerate(zip(lines, gross_paise, allocations), 1):
        if line.get("gstRate") in (None, ""):
            raise InvoiceDraftError(
                f"Original item {n} has no verified GST rate snapshot"
            )
        if not omit_hsn and line.get("hsnCode") in (None, ""):
            raise InvoiceDraftError(
                f"Original item {n} has no required HSN snapshot"
            )
        output.append({
            "product_name": line.get("productName"),
            "quantity": line["quantity"],
            "unit": line.get("unitCode") or "PCS",
            "hsn": str(line.get("hsnCode") or ""),
            "gst_rate": str(line["gstRate"]),
            "pre_discount_gross": str(Decimal(gross)/100),
            "discount_amount": str(Decimal(share)/100),
            "gross_amount": str(Decimal(gross-share)/100),
        })

    delivery_paise = _paise(order.get("deliveryFee", 0), "Delivery charge")
    extra_paise = _paise(order.get("tryAtHomeFee", 0), "Try at home fee")
    if extra_paise:
        if tax_policy.get("service_gst_rate") in (None, "") or (
            not omit_hsn and tax_policy.get("service_hsn_sac") in (None, "")
        ):
            raise InvoiceDraftError("Try-at-home fee rate and required SAC need verification")
        output.append({
            "product_name": "Try at home service",
            "quantity": 1, "unit": "SERVICE",
            "hsn": str(tax_policy.get("service_hsn_sac") or ""),
            "gst_rate": str(tax_policy["service_gst_rate"]),
            "gross_amount": str(Decimal(extra_paise)/100),
        })

    recorded_total = _paise(order.get("grandTotal"), "Customer order total")
    if sum(gross_paise)-discount+delivery_paise+extra_paise != recorded_total:
        raise InvoiceDraftError("Invoice cannot reconcile to the original checkout total")
    if not tax_policy.get("place_of_supply_verified"):
        raise InvoiceDraftError("Place of supply must be verified by billing admin")

    return {
        "hsn_optional_for_b2c": omit_hsn,
        "order_id": str(order.get("id") or ""),
        "invoice_number": invoice_number,
        "issue_date": issue_date,
        "customer_address": dict(order.get("address") or {}),
        "place_of_supply_state": tax_policy.get("place_of_supply_state"),
        "place_of_supply_state_code": tax_policy.get("place_of_supply_state_code"),
        "items": output,
        "delivery_gross": str(Decimal(delivery_paise)/100),
        "delivery_gst_rate": tax_policy.get("delivery_gst_rate"),
        "delivery_hsn_sac": tax_policy.get("delivery_hsn_sac"),
        "customer_paid_total": str(Decimal(recorded_total)/100),
    }
