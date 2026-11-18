from __future__ import annotations

import base64
import binascii
import hashlib
import os
import re
import secrets
import unicodedata
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any

try:
    from receipt_pdf import CONTENT_WIDTH, MARGIN, PAGE_HEIGHT, PAGE_WIDTH, PdfDocument, money, wrap_text
except ModuleNotFoundError:
    from scripts.receipt_pdf import CONTENT_WIDTH, MARGIN, PAGE_HEIGHT, PAGE_WIDTH, PdfDocument, money, wrap_text


INDIA_TZ = timezone(timedelta(hours=5, minutes=30))
MONTH_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MAX_BILL_BYTES = 6 * 1024 * 1024
ALLOWED_DOCUMENTS = {
    "application/pdf": (".pdf", b"%PDF-"),
    "image/jpeg": (".jpg", b"\xff\xd8\xff"),
    "image/png": (".png", b"\x89PNG\r\n\x1a\n"),
}


class BillingAuditError(ValueError):
    def __init__(self, message: str, code: str, status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status


def _decimal(value: Any, field: str, *, maximum: Decimal = Decimal("100000000")) -> Decimal:
    if isinstance(value, bool):
        raise BillingAuditError(f"Enter a valid {field}.", "invalid_supplier_bill")
    try:
        result = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        raise BillingAuditError(f"Enter a valid {field}.", "invalid_supplier_bill") from None
    if not result.is_finite() or result < 0 or result > maximum:
        raise BillingAuditError(f"Enter a valid {field}.", "invalid_supplier_bill")
    return result


def _money_number(value: Any) -> float:
    try:
        return float(Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    except (InvalidOperation, TypeError, ValueError):
        return 0.0


def _clean(value: Any, field: str, minimum: int, maximum: int) -> str:
    if not isinstance(value, str):
        raise BillingAuditError(f"Enter a valid {field}.", "invalid_supplier_bill")
    result = " ".join(value.split())
    if not minimum <= len(result) <= maximum:
        raise BillingAuditError(f"Enter a valid {field}.", "invalid_supplier_bill")
    return result


def _invoice_number_key(value: Any) -> str:
    # NFKC makes full-width forms comparable.  Keeping only alphanumeric
    # characters also removes zero-width format controls and separators
    # that can be trivially changed when relabeling a supplier invoice.
    normalized = unicodedata.normalize("NFKC", str(value or ""))
    key = "".join(char for char in normalized.casefold() if char.isalnum())
    # NFKC handles fullwidth forms but cannot reliably equate different
    # scripts' lookalike letters.  Reject non-ASCII alphanumeric identifiers
    # until the supplier-tax-identity workflow supports native-script numbers.
    if not key or not key.isascii():
        raise BillingAuditError(
            "Use English letters and digits in the supplier invoice number.",
            "invalid_supplier_bill",
        )
    return key


def _supplier_name_key(value: Any) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or ""))
    visible = "".join(char for char in normalized if unicodedata.category(char) != "Cf")
    return " ".join(visible.split()).casefold()


def _parse_instant(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _delivered_at(order: dict[str, Any]) -> datetime | None:
    history = order.get("statusHistory") if isinstance(order.get("statusHistory"), list) else []
    for entry in reversed(history):
        if isinstance(entry, dict) and entry.get("status") == "delivered":
            parsed = _parse_instant(entry.get("timestamp"))
            if parsed is not None:
                return parsed
    return _parse_instant(order.get("deliveredAt") or order.get("updatedAt") or order.get("createdAt"))


def _public_bill(bill: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in bill.items() if key not in {"storageName", "uploadedBy", "documentSha256"}}


def _line_classification(item: dict[str, Any], products: dict[str, dict[str, Any]]) -> tuple[str, str]:
    product = products.get(str(item.get("productId") or "")) or {}
    category = str(item.get("category") or product.get("category") or product.get("department") or "Uncategorised")
    brand = str(item.get("brand") or product.get("brand") or item.get("storeName") or product.get("storeName") or "Unbranded")
    return category, brand


def _stores_for_order(order: dict[str, Any]) -> list[dict[str, str]]:
    stores: dict[str, dict[str, str]] = {}
    for item in order.get("items") or []:
        if not isinstance(item, dict):
            continue
        name = " ".join(str(item.get("storeName") or "").split())
        store_id = " ".join(str(item.get("storeId") or "").split())
        if name or store_id:
            key = store_id or name.casefold()
            stores[key] = {"storeId": store_id, "storeName": name or store_id}
    return list(stores.values()) or [{"storeId": "", "storeName": "Primary supplier"}]


class BillingAuditService:
    def __init__(self, payments: Any, data_directory: Path, *, enable_storage: bool = True) -> None:
        self.payments = payments
        self.directory = data_directory / "supplier-bills"
        self.storage_enabled = enable_storage
        if enable_storage:
            self.directory.mkdir(parents=True, exist_ok=True)
            if not self.directory.is_dir():
                raise BillingAuditError("Supplier bill storage is unavailable.", "supplier_bill_storage_error", 500)
            # Supplier invoices are private financial records; existing
            # directory permissions must be tightened when storage is enabled.
            os.chmod(self.directory, 0o700)
    def _require_financial_storage(self) -> None:
        if not self.storage_enabled:
            raise BillingAuditError(
                "Financial billing features are unavailable in preview.",
                "billing_preview_restricted", 403,
            )
    @staticmethod
    def public_bills(order: dict[str, Any]) -> list[dict[str, Any]]:
        return [_public_bill(row) for row in order.get("supplierBills") or [] if isinstance(row, dict)]

    @staticmethod
    def validate_month(value: Any) -> str:
        month = str(value or "").strip()
        if not MONTH_PATTERN.fullmatch(month):
            raise BillingAuditError("Choose a month in YYYY-MM format.", "invalid_billing_month")
        return month

    def upload_supplier_bill(self, order_id: str, payload: dict[str, Any], admin_id: str) -> dict[str, Any]:
        self._require_financial_storage()
        if not isinstance(payload, dict):
            raise BillingAuditError("Supplier bill details are required.", "invalid_supplier_bill")
        bill_number = _clean(payload.get("billNumber"), "bill number", 1, 80)
        invoice_key = _invoice_number_key(bill_number)
        bill_date = str(payload.get("billDate") or "").strip()
        try:
            datetime.strptime(bill_date, "%Y-%m-%d")
        except ValueError:
            raise BillingAuditError("Enter a valid bill date.", "invalid_supplier_bill") from None
        if not DATE_PATTERN.fullmatch(bill_date):
            raise BillingAuditError("Enter a valid bill date.", "invalid_supplier_bill")
        store_id = " ".join(str(payload.get("storeId") or "").split())[:120]
        store_name = _clean(payload.get("storeName"), "shop name", 2, 120)
        taxable = _decimal(payload.get("taxableAmount"), "taxable amount")
        gst = _decimal(payload.get("gstAmount"), "GST amount")
        total = _decimal(payload.get("totalAmount"), "bill total")
        if abs((taxable + gst) - total) > Decimal("1.00"):
            raise BillingAuditError("Bill total must equal taxable amount plus GST (within INR 1 rounding).", "supplier_bill_total_mismatch")
        content_type = str(payload.get("contentType") or "").strip().casefold()
        expected = ALLOWED_DOCUMENTS.get(content_type)
        if expected is None:
            raise BillingAuditError("Upload a PDF, JPG or PNG supplier bill.", "unsupported_supplier_bill")
        try:
            document = base64.b64decode(str(payload.get("dataBase64") or ""), validate=True)
        except (binascii.Error, ValueError):
            raise BillingAuditError("The supplier bill file is invalid.", "invalid_supplier_bill_file") from None
        if not document or len(document) > MAX_BILL_BYTES or not document.startswith(expected[1]):
            raise BillingAuditError("The supplier bill file is invalid or exceeds 6 MB.", "invalid_supplier_bill_file")
        document_hash = hashlib.sha256(document).hexdigest()
        original_name = _clean(payload.get("fileName"), "file name", 1, 160)
        bill_id = "bill_" + secrets.token_hex(10)
        storage_name = bill_id + expected[0]
        target = self.directory / storage_name
        temporary = self.directory / (storage_name + ".tmp")
        metadata = {
            "id": bill_id,
            "storeId": store_id,
            "storeName": store_name,
            "billNumber": bill_number,
            "billDate": bill_date,
            "taxableAmount": _money_number(taxable),
            "gstAmount": _money_number(gst),
            "totalAmount": _money_number(total),
            "fileName": original_name,
            "contentType": content_type,
            "storageName": storage_name,
            "documentSha256": document_hash,
            "uploadedAt": datetime.now(timezone.utc).isoformat(),
            "uploadedBy": admin_id,
        }
        with self.payments.store.lock:
            order = self.payments.store.state["orders"].get(order_id)
            if order is None:
                raise BillingAuditError("Order not found.", "order_not_found", 404)
            if order.get("status") != "delivered":
                raise BillingAuditError("Shop bills can be uploaded only after delivery.", "supplier_bill_not_ready", 409)
            if order.get("isPaymentTestOrder") is True or order.get("fulfillmentRequired") is False:
                raise BillingAuditError("Payment test orders cannot have supplier bills.", "supplier_bill_not_ready", 409)
            stores = _stores_for_order(order)
            # When an ID is supplied, never accept a different shop's ID
            # merely because its user-supplied name matches a real shop.
            # Store canonical order-snapshot values so name-only uploads
            # also count towards the right supplier's bill coverage.
            if store_id:
                selected_store = next(
                    (row for row in stores if row["storeId"] == store_id), None
                )
            else:
                # Display names are not unique shop identifiers.  An ambiguous
                # name-only bill could silently belong to another supplier;
                # require the real store ID whenever more than one matches.
                matching_stores = [
                    row for row in stores
                    if row["storeName"].casefold() == store_name.casefold()
                ]
                selected_store = matching_stores[0] if len(matching_stores) == 1 else None
                # A legacy order with the placeholder "Primary supplier"
                # has no verified supplier identity.  Do not silently attach
                # a financial invoice to that placeholder.
            if selected_store is None:
                raise BillingAuditError("Choose a shop that supplied this order.", "supplier_bill_store_mismatch")
            store_id = selected_store["storeId"]
            store_name = selected_store["storeName"]
            if not store_id and store_name == "Primary supplier":
                raise BillingAuditError(
                    "Link this order to a verified supplier before uploading its bill.",
                    "supplier_bill_store_mismatch", 409,
                )
            metadata["storeId"] = store_id
            metadata["storeName"] = store_name
            bills = order.setdefault("supplierBills", [])
            if not isinstance(bills, list):
                raise BillingAuditError("Stored supplier bill data is invalid.", "supplier_bill_storage_error", 500)
            if len(bills) >= 25:
                raise BillingAuditError("This order already has the maximum number of supplier bills.", "supplier_bill_limit", 409)
            def same_supplier(row: dict[str, Any], *, cross_order: bool = False) -> bool:
                existing_id = str(row.get("storeId") or "").strip()
                if store_id and existing_id and store_id == existing_id:
                    return True
                current_name = _supplier_name_key(store_name)
                existing_name = _supplier_name_key(row.get("storeName"))
                # Two different IDs may genuinely share a shop name within
                # one order, so keep per-order ID separation.  Across orders,
                # a supplier may have been assigned a replacement store ID;
                # in that ambiguous case fail closed for the same invoice.
                if store_id and existing_id and not cross_order:
                    return False
                return bool(current_name and current_name == existing_name)

            if any(
                _invoice_number_key(row.get("billNumber")) == invoice_key
                and same_supplier(row)
                for row in bills if isinstance(row, dict)
            ):
                raise BillingAuditError("This shop bill number is already attached to the order.", "supplier_bill_duplicate", 409)
            # One supplier invoice must not create multiple purchases or
            # input-GST credits across different customer orders.  A shared
            # supplier invoice requires an explicit allocation workflow before
            # it can be attached to multiple orders.
            for existing_order_id, existing_order in self.payments.store.state["orders"].items():
                if existing_order_id == order_id or not isinstance(existing_order, dict):
                    continue
                existing_bills = existing_order.get("supplierBills")
                if not isinstance(existing_bills, list):
                    continue
                if any(
                    isinstance(row, dict)
                    and _invoice_number_key(row.get("billNumber")) == invoice_key
                    and same_supplier(row, cross_order=True)
                    for row in existing_bills
                ):
                    raise BillingAuditError(
                        "This supplier invoice is already attached to another order. "
                        "A shared supplier invoice needs an approved allocation first.",
                        "supplier_bill_already_used", 409,
                    )
            # The same actual document may be labelled with a different
            # invoice number or store alias.  A byte-identical financial bill
            # must not be counted twice even when its label is changed.
            for existing_order in self.payments.store.state["orders"].values():
                if not isinstance(existing_order, dict):
                    continue
                existing_bills = existing_order.get("supplierBills")
                if isinstance(existing_bills, list) and any(
                    isinstance(row, dict)
                    and row.get("documentSha256") == document_hash
                    for row in existing_bills
                ):
                    raise BillingAuditError(
                        "This supplier bill document is already attached to an order.",
                        "supplier_bill_document_reused", 409,
                    )
            try:
                # O_EXCL prevents following or replacing an existing path and
                # the explicit mode avoids a transient world-readable upload
                # on hosts whose umask is less restrictive than expected.
                descriptor = os.open(
                    temporary,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                    0o600,
                )
                with os.fdopen(descriptor, "wb") as handle:
                    handle.write(document)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, target)
                os.chmod(target, 0o600)
                bills.append(metadata)
                self.payments.store.save()
            except Exception:
                temporary.unlink(missing_ok=True)
                target.unlink(missing_ok=True)
                if metadata in bills:
                    bills.remove(metadata)
                raise
        return _public_bill(metadata)

    def document(self, order_id: str, bill_id: str) -> tuple[bytes, str, str]:
        self._require_financial_storage()
        with self.payments.store.lock:
            order = self.payments.store.state["orders"].get(order_id)
            if order is None:
                raise BillingAuditError("Order not found.", "order_not_found", 404)
            bill = next((row for row in order.get("supplierBills") or [] if isinstance(row, dict) and row.get("id") == bill_id), None)
            if bill is None:
                raise BillingAuditError("Supplier bill not found.", "supplier_bill_not_found", 404)
            storage_name = str(bill.get("storageName") or "")
            content_type = str(bill.get("contentType") or "")
            file_name = str(bill.get("fileName") or storage_name)
            expected_hash = str(bill.get("documentSha256") or "")
        target = (self.directory / storage_name).resolve()
        if target.parent != self.directory.resolve() or not target.is_file() or content_type not in ALLOWED_DOCUMENTS:
            raise BillingAuditError("Supplier bill file is unavailable.", "supplier_bill_not_found", 404)
        content = target.read_bytes()
        if expected_hash and hashlib.sha256(content).hexdigest() != expected_hash:
            raise BillingAuditError("Supplier bill file failed its integrity check.", "supplier_bill_integrity_error", 500)
        return content, content_type, file_name

    def _orders_for_month(self, month: str) -> list[dict[str, Any]]:
        self.validate_month(month)
        with self.payments.store.lock:
            orders = [dict(order) for order in self.payments.store.state["orders"].values()]
        selected = []
        for order in orders:
            delivered = _delivered_at(order)
            if (
                order.get("status") == "delivered"
                and order.get("isPaymentTestOrder") is not True
                and order.get("fulfillmentRequired") is not False
                and delivered is not None
                and delivered.astimezone(INDIA_TZ).strftime("%Y-%m") == month
            ):
                order["_deliveredAt"] = delivered.astimezone(INDIA_TZ).isoformat()
                selected.append(order)
        return sorted(selected, key=lambda row: row.get("_deliveredAt", ""))

    def preview(self, month: str) -> dict[str, Any]:
        # Deliberately read-only. This method does not read supplier bill
        # amounts, GST credits, profit or authoritative purchase registers.
        month = self.validate_month(month)
        orders = self._orders_for_month(month)
        units = sum(
            max(0, int(item.get("quantity") or 0))
            for order in orders
            for item in order.get("items") or []
            if isinstance(item, dict)
        )
        total = sum(
            (_decimal(order.get("grandTotal") or 0, "order total") for order in orders),
            Decimal("0"),
        )
        return {
            "month": month,
            "mode": "read_only_preview",
            "financialReportApproved": False,
            "supplierBillUploadEnabled": False,
            "financialPdfExportsEnabled": False,
            "notice": "Operational estimate only, not a tax or accounting report.",
            "summary": {
                "deliveredOrders": len(orders),
                "itemsSold": units,
                "deliveredOrderValueEstimate": _money_number(total),
            },
        }

    def report(self, month: str) -> dict[str, Any]:
        self._require_financial_storage()
        month = self.validate_month(month)
        self.payments.refresh_shop_products()
        products = self.payments.product_snapshot()
        orders = self._orders_for_month(month)
        daily: dict[str, dict[str, float]] = defaultdict(lambda: {"sales": 0.0, "profit": 0.0})
        categories: dict[str, dict[str, float]] = defaultdict(lambda: {"quantity": 0, "sales": 0.0, "profit": 0.0})
        brands: dict[str, dict[str, float]] = defaultdict(lambda: {"quantity": 0, "sales": 0.0, "profit": 0.0})
        regions: dict[str, dict[str, float]] = defaultdict(lambda: {"orders": 0, "sales": 0.0, "profit": 0.0})
        products_sold: dict[str, dict[str, Any]] = {}
        order_rows: list[dict[str, Any]] = []
        purchase_rows: list[dict[str, Any]] = []
        totals = defaultdict(float)
        complete_orders = 0
        missing_orders = 0

        for order in orders:
            grand_total = _money_number(order.get("grandTotal"))
            discount = _money_number(order.get("discount"))
            merchandise_gross = sum(_money_number(item.get("lineTotal")) for item in order.get("items") or [] if isinstance(item, dict))
            merchandise_net = max(0.0, merchandise_gross - discount)
            bills = [_public_bill(row) for row in order.get("supplierBills") or [] if isinstance(row, dict)]
            purchase_total = sum(_money_number(row.get("totalAmount")) for row in bills)
            purchase_taxable = sum(_money_number(row.get("taxableAmount")) for row in bills)
            input_tax = sum(_money_number(row.get("gstAmount")) for row in bills)
            # GST has to come from the frozen checkout snapshot where it is
            # available.  The legacy ``taxes`` field is only a compatibility
            # fallback for orders created before the snapshot existed.
            gst_snapshot = order.get("gstSnapshot") if isinstance(order.get("gstSnapshot"), dict) else {}
            output_tax = _money_number(gst_snapshot.get("includedTaxTotal", order.get("taxes")))
            profit = grand_total - purchase_total
            required_stores = _stores_for_order(order)

            # A single order may contain purchases from multiple shops.
            # Allocate each supplier's bill only to that shop's item lines,
            # rather than spreading the total purchase cost across all shops.
            # A name-only bill is resolved to the order's canonical store ID
            # when the order snapshot has one.
            name_to_store = {
                row["storeName"].casefold(): row["storeId"] or row["storeName"].casefold()
                for row in required_stores
            }

            def store_cost_key(row: dict[str, Any]) -> str:
                store_id = str(row.get("storeId") or "").strip()
                if store_id:
                    return store_id
                store_name = " ".join(str(row.get("storeName") or "").split()).casefold()
                return name_to_store.get(store_name, store_name or "primary supplier")

            supplier_cost_by_store: dict[str, float] = defaultdict(float)
            for bill in bills:
                supplier_cost_by_store[store_cost_key(bill)] += _money_number(bill.get("totalAmount"))

            item_gross_by_store: dict[str, float] = defaultdict(float)
            for item in order.get("items") or []:
                if isinstance(item, dict):
                    item_gross_by_store[store_cost_key(item)] += _money_number(item.get("lineTotal"))

            matched = {store_cost_key(row) for row in bills}
            complete = all(store_cost_key(row) in matched for row in required_stores)
            if complete:
                complete_orders += 1
            else:
                missing_orders += 1
            delivered_day = str(order.get("_deliveredAt") or "")[:10]
            daily[delivered_day]["sales"] += grand_total
            daily[delivered_day]["profit"] += profit
            address = order.get("address") if isinstance(order.get("address"), dict) else {}
            region = ", ".join(part for part in [str(address.get("city") or "").strip(), str(address.get("pincode") or "").strip()] if part) or "Unknown region"
            regions[region]["orders"] += 1
            regions[region]["sales"] += grand_total
            regions[region]["profit"] += profit
            order_rows.append({
                "orderId": order.get("id"), "deliveredAt": order.get("_deliveredAt"),
                "customer": address.get("name") or "-", "region": region,
                "sales": grand_total, "outputTax": output_tax, "purchaseTotal": purchase_total,
                "inputTax": input_tax, "profit": profit, "billStatus": "complete" if complete else "missing",
                "supplierBills": bills,
            })
            for bill in bills:
                purchase_rows.append({"orderId": order.get("id"), **bill})
            totals["sales"] += grand_total
            totals["merchandiseSales"] += merchandise_net
            totals["outputTax"] += output_tax
            totals["purchaseTaxable"] += purchase_taxable
            totals["inputTax"] += input_tax
            totals["purchases"] += purchase_total
            totals["itemsSold"] += sum(int(item.get("quantity") or 0) for item in order.get("items") or [] if isinstance(item, dict))
            for item in order.get("items") or []:
                if not isinstance(item, dict):
                    continue
                quantity = max(0, int(item.get("quantity") or 0))
                gross_line = _money_number(item.get("lineTotal"))
                line_sales = gross_line if merchandise_gross <= 0 else merchandise_net * gross_line / merchandise_gross
                # Cost allocation is seller-specific.  Overall order profit
                # still includes delivery fees; product groups reflect only
                # product-line sales less their own shop's purchase bills.
                supplier_key = store_cost_key(item)
                supplier_gross = item_gross_by_store[supplier_key]
                line_cost = (
                    supplier_cost_by_store[supplier_key] * gross_line / supplier_gross
                    if supplier_gross > 0 else 0.0
                )
                line_profit = line_sales - line_cost
                category, brand = _line_classification(item, products)
                for group, key in ((categories, category), (brands, brand)):
                    group[key]["quantity"] += quantity
                    group[key]["sales"] += line_sales
                    group[key]["profit"] += line_profit
                product_id = str(item.get("productId") or item.get("sku") or item.get("productName") or "Unknown product")
                row = products_sold.setdefault(product_id, {"productId": item.get("productId") or "", "productName": item.get("productName") or product_id, "category": category, "brand": brand, "quantity": 0, "sales": 0.0, "profit": 0.0})
                row["quantity"] += quantity
                row["sales"] += line_sales
                row["profit"] += line_profit

        totals["grossProfit"] = totals["sales"] - totals["purchases"]
        totals["netTaxPayable"] = totals["outputTax"] - totals["inputTax"]
        # This is a GST settlement view, not an income-tax calculation.  A
        # valid input-GST credit reduces the settlement just as a payable GST
        # amount increases it; clamping negative payable GST would discard a
        # real credit and overstate this figure.
        totals["profitAfterTax"] = totals["grossProfit"] - totals["netTaxPayable"]

        def rows(source: dict[str, dict[str, float]], label: str) -> list[dict[str, Any]]:
            return [
                {label: key, **{metric: _money_number(value) if metric not in {"quantity", "orders"} else int(value) for metric, value in data.items()}}
                for key, data in sorted(source.items(), key=lambda pair: pair[1].get("sales", 0), reverse=True)
            ]

        return {
            "month": month,
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "deliveredOrders": len(orders), "itemsSold": int(totals["itemsSold"]),
                "uniqueProducts": len(products_sold), "billsComplete": complete_orders,
                "billsMissing": missing_orders,
                **{key: _money_number(totals[key]) for key in (
                    "sales", "merchandiseSales", "purchases", "purchaseTaxable", "grossProfit",
                    "outputTax", "inputTax", "netTaxPayable", "profitAfterTax",
                )},
            },
            "daily": [{"date": key, "sales": _money_number(value["sales"]), "profit": _money_number(value["profit"])} for key, value in sorted(daily.items())],
            "categories": rows(categories, "category"),
            "brands": rows(brands, "brand"),
            "regions": rows(regions, "region"),
            "products": sorted(({**row, "sales": _money_number(row["sales"]), "profit": _money_number(row["profit"])} for row in products_sold.values()), key=lambda row: (-row["quantity"], row["productName"])),
            "orders": order_rows,
            "purchases": purchase_rows,
        }

    def pdf(self, month: str, kind: str) -> bytes:
        self._require_financial_storage()
        report = self.report(month)
        if kind == "purchases":
            return _purchase_register_pdf(report)
        if kind == "sales":
            return _sales_register_pdf(report)
        raise BillingAuditError("Unsupported billing report.", "invalid_billing_report")


def _report_page(doc: PdfDocument, title: str, month: str, subtitle: str, *, continuation: bool = False) -> tuple[list[str], float]:
    page = doc.new_page()
    blue = (0.07, 0.49, 0.68)
    doc.rect(page, 0, PAGE_HEIGHT - 96, PAGE_WIDTH, 96, fill=(1, 1, 1))
    doc.rect(page, 0, PAGE_HEIGHT - 100, PAGE_WIDTH, 4, fill=blue)
    doc.text(page, MARGIN, PAGE_HEIGHT - 48, "Vibe4You", size=22, bold=True, color=(0.08, 0.12, 0.16))
    doc.text(page, MARGIN, PAGE_HEIGHT - 67, "Tax Billing Audit", size=8.5, color=(0.34, 0.40, 0.44))
    doc.text(page, 310, PAGE_HEIGHT - 45, title + (" - CONTINUED" if continuation else ""), size=11, bold=True, color=blue)
    doc.text(page, 310, PAGE_HEIGHT - 61, f"Period: {month}", size=8.5, bold=True)
    doc.text(page, 310, PAGE_HEIGHT - 76, subtitle, size=7.5, color=(0.34, 0.40, 0.44))
    return page, PAGE_HEIGHT - 126


def _summary_boxes(doc: PdfDocument, page: list[str], y: float, values: list[tuple[str, Any]]) -> float:
    gap = 8.0
    width = (CONTENT_WIDTH - (gap * (len(values) - 1))) / len(values)
    for index, (label, value) in enumerate(values):
        x = MARGIN + index * (width + gap)
        doc.rect(page, x, y - 52, width, 52, fill=(0.965, 0.975, 0.98), stroke=(0.82, 0.86, 0.88))
        doc.text(page, x + 9, y - 17, label.upper(), size=6.7, bold=True, color=(0.38, 0.43, 0.46))
        doc.text(page, x + 9, y - 37, value, size=9.5, bold=True)
    return y - 72


def _table_header(doc: PdfDocument, page: list[str], y: float, columns: list[tuple[str, float]]) -> float:
    doc.rect(page, MARGIN, y - 22, CONTENT_WIDTH, 22, fill=(0.08, 0.12, 0.16))
    x = MARGIN + 6
    for label, width in columns:
        doc.text(page, x, y - 15, label.upper(), size=6.4, bold=True, color=(1, 1, 1))
        x += width
    return y - 30


def _table_row(doc: PdfDocument, page: list[str], y: float, values: list[Any], columns: list[tuple[str, float]]) -> float:
    wrapped = [wrap_text(value, width - 10, 7.2)[:2] for value, (_label, width) in zip(values, columns)]
    height = max(24.0, 10.0 + max(len(lines) for lines in wrapped) * 9.0)
    doc.rect(page, MARGIN, y - height + 4, CONTENT_WIDTH, height, fill=(0.985, 0.985, 0.98), stroke=(0.90, 0.90, 0.88), line_width=0.4)
    x = MARGIN + 6
    for lines, (_label, width) in zip(wrapped, columns):
        text_y = y - 10
        for line in lines:
            doc.text(page, x, text_y, line, size=7.2)
            text_y -= 9
        x += width
    return y - height


def _purchase_register_pdf(report: dict[str, Any]) -> bytes:
    doc = PdfDocument()
    summary = report["summary"]
    page, y = _report_page(doc, "PURCHASE REGISTER", report["month"], "Uploaded shop-owner bills")
    y = _summary_boxes(doc, page, y, [("Bills", len(report["purchases"])), ("Taxable", money(summary["purchaseTaxable"])), ("Input GST", money(summary["inputTax"])), ("Purchases", money(summary["purchases"]))])
    columns = [("Date", 58), ("Shop / Bill", 145), ("Order", 96), ("Taxable", 65), ("GST", 55), ("Total", 76)]
    y = _table_header(doc, page, y, columns)
    for row in report["purchases"]:
        if y < 80:
            page, y = _report_page(doc, "PURCHASE REGISTER", report["month"], "Uploaded shop-owner bills", continuation=True)
            y = _table_header(doc, page, y, columns)
        y = _table_row(doc, page, y, [row.get("billDate"), f"{row.get('storeName')} / {row.get('billNumber')}", row.get("orderId"), money(row.get("taxableAmount")), money(row.get("gstAmount")), money(row.get("totalAmount"))], columns)
    if not report["purchases"]:
        doc.text(page, MARGIN, y - 15, "No supplier bills were uploaded for this month.", size=9, bold=True, color=(0.55, 0.20, 0.20))
    return doc.build()
def _sales_register_pdf(report: dict[str, Any]) -> bytes:
    doc = PdfDocument()
    summary = report["summary"]
    page, y = _report_page(doc, "SALES REGISTER", report["month"], "Delivered customer bills and products sold")
    y = _summary_boxes(doc, page, y, [("Orders", summary["deliveredOrders"]), ("Sales", money(summary["sales"])), ("Output GST", money(summary["outputTax"])), ("Gross profit", money(summary["grossProfit"]))])
    order_columns = [("Delivered", 69), ("Order / Customer", 176), ("Region", 100), ("Sales", 76), ("GST", 64)]
    y = _table_header(doc, page, y, order_columns)
    for row in report["orders"]:
        if y < 80:
            page, y = _report_page(doc, "SALES REGISTER", report["month"], "Delivered customer bills", continuation=True)
            y = _table_header(doc, page, y, order_columns)
        y = _table_row(doc, page, y, [str(row.get("deliveredAt") or "")[:10], f"{row.get('orderId')} / {row.get('customer')}", row.get("region"), money(row.get("sales")), money(row.get("outputTax"))], order_columns)
    page, y = _report_page(doc, "PRODUCTS SOLD", report["month"], "All products in delivered orders")
    product_columns = [("Product", 190), ("Category", 105), ("Brand", 90), ("Qty", 40), ("Sales", 70)]
    y = _table_header(doc, page, y, product_columns)
    for row in report["products"]:
        if y < 80:
            page, y = _report_page(doc, "PRODUCTS SOLD", report["month"], "All products in delivered orders", continuation=True)
            y = _table_header(doc, page, y, product_columns)
        y = _table_row(doc, page, y, [row.get("productName"), row.get("category"), row.get("brand"), row.get("quantity"), money(row.get("sales"))], product_columns)
    return doc.build()
