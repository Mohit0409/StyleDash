#!/usr/bin/env python3
"""Loopback-only Vibe4You administrator UI/API. Never expose publicly."""

from __future__ import annotations

import argparse
import csv
import io
import importlib.util
import json
import math
import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, unquote, urlsplit
from urllib.request import Request, urlopen

try:
    from styledash_admin import ADMIN_COOKIE, CHALLENGE_COOKIE, AdminStore
    from styledash_security import SecurityError, iso, utc_now
except ModuleNotFoundError:
    from scripts.styledash_admin import ADMIN_COOKIE, CHALLENGE_COOKIE, AdminStore
    from scripts.styledash_security import SecurityError, iso, utc_now

try:
    from styledash_shops import PRODUCT_MEDIA_PATH_PATTERN, ShopWorkflow
except ModuleNotFoundError:
    from scripts.styledash_shops import PRODUCT_MEDIA_PATH_PATTERN, ShopWorkflow

try:
    from styledash_reviews import ReviewWorkflow
except ModuleNotFoundError:
    from scripts.styledash_reviews import ReviewWorkflow

try:
    from styledash_notify import owner_notifier
except ModuleNotFoundError:
    from scripts.styledash_notify import owner_notifier
try:
    from invoice_admin_gateway import InvoiceGateway, InvoiceDraftError
    from tax_classification_registry import TaxClassificationRegistry
except ModuleNotFoundError:
    from scripts.invoice_admin_gateway import InvoiceGateway, InvoiceDraftError
    from scripts.tax_classification_registry import TaxClassificationRegistry

try:
    from gst_catalog_review import review_csv, coverage, parse_approved_csv
except ModuleNotFoundError:
    from scripts.gst_catalog_review import review_csv, coverage, parse_approved_csv

try:
    from gst_official_suggestions import (
        high_confidence_records,suggestion_coverage,
    )
except ModuleNotFoundError:
    from scripts.gst_official_suggestions import (
        high_confidence_records,suggestion_coverage,
    )

try:
    from scripts.styledash_delivery_zone import DeliveryZoneConfigError
    from scripts.styledash_delivery_zone_store import DeliveryZoneStore
except ModuleNotFoundError:
    from styledash_delivery_zone import DeliveryZoneConfigError
    from styledash_delivery_zone_store import DeliveryZoneStore

try:
    from billing_audit import BillingAuditError, BillingAuditService
except ModuleNotFoundError:
    from scripts.billing_audit import BillingAuditError, BillingAuditService

try:
    from order_documents import OrderDocumentError, OrderDocuments, UPLOAD_REQUEST_MAX_BYTES as ORDER_DOCUMENT_REQUEST_MAX_BYTES
except ModuleNotFoundError:
    from scripts.order_documents import OrderDocumentError, OrderDocuments, UPLOAD_REQUEST_MAX_BYTES as ORDER_DOCUMENT_REQUEST_MAX_BYTES

try:
    from order_profit import OrderProfitLedger, OrderProfitError
except ModuleNotFoundError:
    from scripts.order_profit import OrderProfitLedger, OrderProfitError


MAX_BODY_BYTES = 64 * 1024
PRODUCT_IMAGE_REQUEST_MAX_BYTES = 700 * 1024
BULK_PRODUCT_REQUEST_MAX_BYTES = 1024 * 1024
SUPPLIER_BILL_REQUEST_MAX_BYTES = 9 * 1024 * 1024
PUBLIC_ADMIN_ORIGIN = "https://admin.vibe4you.in"
ALLOWED_HOSTS = {"127.0.0.1:8081", "localhost:8081"}
ALLOWED_ORIGINS = {"http://127.0.0.1:8081", "http://localhost:8081", PUBLIC_ADMIN_ORIGIN}
SECURITY_POLICY = (
    "default-src 'self'; base-uri 'none'; object-src 'none'; frame-ancestors 'none'; "
    "form-action 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: https:; "
    "connect-src 'self'"
)


def require_billing_preview_mode() -> None:
    """Only the approved read-only operational preview may be served."""
    if os.environ.get("V4Y_TAX_BILLING_RELEASE_MODE", "preview") != "preview":
        raise SecurityError(403, "Tax billing is not enabled.", "billing_release_disabled")


def deny_financial_billing() -> None:
    """Supplier documents and financial reports remain disabled in phase 1."""
    raise SecurityError(
        403,
        "Financial billing features are unavailable in preview.",
        "billing_preview_restricted",
    )

def _import_error(row_number: int, message: str) -> None:
    raise SecurityError(400, f"Row {row_number}: {message}", "invalid_product_import")


def require_existing_admin_product_media(payload: Any, product_image_directory: Path, row_number: int | None = None) -> None:
    if not isinstance(payload, dict):
        return
    image_urls = payload.get("imageUrls")
    if not isinstance(image_urls, list):
        return
    root = product_image_directory.resolve()
    for value in image_urls:
        if not isinstance(value, str) or not PRODUCT_MEDIA_PATH_PATTERN.fullmatch(value):
            continue
        target = (product_image_directory / Path(value).name).resolve()
        if target.parent != root or not target.is_file():
            prefix = f"Row {row_number}: " if row_number is not None else ""
            raise SecurityError(400, f"{prefix}Uploaded product image is unavailable.", "invalid_product_image")


def _bulk_variants(raw: str, row_number: int) -> list[dict[str, Any]]:
    variants: list[dict[str, Any]] = []
    for chunk in raw.split(","):
        value = chunk.strip()
        if not value:
            continue
        size, separator, stock_text = value.rpartition(":")
        if not separator or not size.strip():
            _import_error(row_number, "Use size:stock format, for example 6:5, 7:5.")
        try:
            stock = int(stock_text.strip())
        except ValueError:
            _import_error(row_number, "Each size needs a whole-number stock quantity.")
        if stock < 0 or stock > 100000:
            _import_error(row_number, "Each size needs a stock quantity between 0 and 100000.")
        variants.append({"size": size.strip(), "inventory": stock})
    if not variants:
        _import_error(row_number, "At least one size and stock value is required.")
    return variants


def parse_admin_product_csv(csv_text: Any, image_map: Any, product_image_directory: Path) -> list[dict[str, Any]]:
    if not isinstance(csv_text, str) or not csv_text.strip() or len(csv_text.encode("utf-8")) > 1024 * 1024:
        raise SecurityError(400, "CSV is missing or too large.", "invalid_product_import")
    if image_map is None:
        image_map = {}
    if not isinstance(image_map, dict) or len(image_map) > 800:
        raise SecurityError(400, "Invalid image selection map.", "invalid_product_import")
    stream = io.StringIO(csv_text, newline="")
    try:
        reader = csv.DictReader(stream)
    except csv.Error:
        raise SecurityError(400, "CSV could not be parsed.", "invalid_product_import") from None
    if reader.fieldnames is None:
        raise SecurityError(400, "CSV needs a header row.", "invalid_product_import")
    fieldnames = [(name or "").lstrip("\ufeff").strip() for name in reader.fieldnames]
    if len(fieldnames) != len(set(fieldnames)) or any(not name for name in fieldnames):
        raise SecurityError(400, "CSV headers must be unique and non-empty.", "invalid_product_import")
    reader.fieldnames = fieldnames
    required = {"name", "description", "department", "category", "price", "variants", "colourName"}
    missing = sorted(required - set(fieldnames))
    if missing:
        raise SecurityError(400, f"CSV is missing required column: {missing[0]}", "invalid_product_import")
    if "imageFile" not in fieldnames and "imageUrls" not in fieldnames:
        raise SecurityError(400, "CSV requires imageFile or imageUrls.", "invalid_product_import")
    products: list[dict[str, Any]] = []
    groups: dict[str, tuple[dict[str, Any], tuple[Any, ...], set[str]]] = {}
    image_root = product_image_directory.resolve()
    row_number = 0
    for row in reader:
        if row is None or not any(str(value or "").strip() for value in row.values()):
            continue
        row_number += 1
        if row_number > 100:
            raise SecurityError(400, "Upload a maximum of 100 products at a time.", "invalid_product_import")
        values = {key: str(value or "").strip() for key, value in row.items() if key is not None}
        name = values.get("name", "")
        if not name:
            _import_error(row_number, "Product name is required.")
        try:
            price = float(values.get("price", ""))
            original = float(values.get("originalPrice") or values.get("price", ""))
        except ValueError:
            _import_error(row_number, "Invalid price.")
        if not math.isfinite(price) or not math.isfinite(original) or price < 1 or original < price or price > 10000000 or original > 10000000:
            _import_error(row_number, "Invalid price.")
        image_urls = [value.strip() for value in values.get("imageUrls", "").split("|") if value.strip()]
        image_file_field = values.get("imageFile", "")
        local_images: list[str] = []
        if image_file_field:
            image_files = [part.strip() for part in image_file_field.split("|")]
            if any(not name for name in image_files):
                _import_error(row_number, "Image filenames must not be empty.")
            if len(set(image_files)) != len(image_files):
                _import_error(row_number, "The same local image is listed more than once.")
            for image_file in image_files:
                if len(image_file) > 120 or "/" in image_file or "\\" in image_file or any(ord(ch) < 32 for ch in image_file):
                    _import_error(row_number, f'Image file "{image_file}" is invalid.')
                mapped_path = image_map.get(image_file)
                if mapped_path is None:
                    _import_error(row_number, f'Image file "{image_file}" was not selected.')
                if not isinstance(mapped_path, str) or not PRODUCT_MEDIA_PATH_PATTERN.fullmatch(mapped_path):
                    _import_error(row_number, f'Image file "{image_file}" has an invalid uploaded path.')
                target = (product_image_directory / Path(mapped_path).name).resolve()
                if target.parent != image_root or not target.is_file():
                    _import_error(row_number, f'Image file "{image_file}" was not uploaded successfully.')
                local_images.append(mapped_path)
        image_urls = local_images + image_urls
        if not image_urls:
            _import_error(row_number, "At least one product image is required.")
        if len(image_urls) > 8:
            _import_error(row_number, "A product can have at most 8 images (local files and image URLs combined).")
        product = {
            "name": name, "description": values.get("description", ""), "brand": values.get("brand") or None,
            "department": values.get("department", ""), "category": values.get("category", ""),
            "subcategory": values.get("subcategory") or None, "deliveryType": values.get("deliveryType") or "normal",
            "pricePaise": round(price * 100), "originalPricePaise": round(original * 100),
            "variants": _bulk_variants(values.get("variants", ""), row_number),
            "colourName": values.get("colourName", ""), "colourHex": values.get("colourHex") or None,
            "imageUrls": image_urls, "attributes": {},
        }
        commission_text = values.get("commissionPercent", "")
        if commission_text:
            if not re.fullmatch(r"(?:100(?:\.0{1,2})?|\d{1,2}(?:\.\d{1,2})?)", commission_text):
                _import_error(row_number, "Commission must be a percentage from 0 to 100, with at most two decimals.")
            product["commissionBasisPoints"] = round(float(commission_text) * 100)
        require_existing_admin_product_media(product, product_image_directory, row_number)
        group_id = values.get("productGroup", "").strip()
        if not group_id:
            products.append(product)
            continue
        if len(group_id) > 100 or any(ord(ch) < 32 for ch in group_id):
            _import_error(row_number, "Invalid productGroup; use an identifier of 1-100 characters.")
        colour_name = product["colourName"].strip()
        if not colour_name:
            _import_error(row_number, "Grouped products need a colourName on every row.")
        shared_keys = (
            "name", "description", "brand", "department", "category", "subcategory",
            "deliveryType", "pricePaise", "originalPricePaise",
        )
        signature = tuple(product[key] for key in shared_keys) + (product.get("commissionBasisPoints"),)
        group_key = group_id.casefold()
        if group_key not in groups:
            grouped = {key: product[key] for key in shared_keys}
            grouped["colourVariants"] = []
            grouped["attributes"] = {"optionMode": "colour"}
            if "commissionBasisPoints" in product:
                grouped["commissionBasisPoints"] = product["commissionBasisPoints"]
            groups[group_key] = (grouped, signature, set())
            products.append(grouped)
        grouped, existing_signature, used_colours = groups[group_key]
        if signature != existing_signature:
            _import_error(row_number, f'productGroup "{group_id}" has inconsistent product details, prices or commission.')
        if colour_name.casefold() in used_colours:
            _import_error(row_number, f'productGroup "{group_id}" repeats colour "{colour_name}".')
        used_colours.add(colour_name.casefold())
        grouped["colourVariants"].append({
            "colourName": colour_name,
            "colourHex": product["colourHex"],
            "imageUrls": product["imageUrls"],
            "sizes": product["variants"],
        })
        all_sizes = [item["size"].casefold().strip() for variant in grouped["colourVariants"] for item in variant["sizes"]]
        grouped["attributes"]["optionMode"] = "colour" if all(size == "one size" for size in all_sizes) else "both"
    if not products:
        raise SecurityError(400, "CSV needs at least one product row.", "invalid_product_import")
    return products



def load_public_module():
    script = Path(__file__).resolve()
    candidates = (
        script.parent.parent / "server" / "serve.py",
        script.parent / "termux-spa-server.py",
    )
    source = next((path for path in candidates if path.exists()), None)
    if source is None:
        raise RuntimeError("Vibe4You public server module was not found")
    spec = importlib.util.spec_from_file_location("styledash_public_runtime", source)
    if spec is None or spec.loader is None:
        raise RuntimeError("Vibe4You public server module could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _notify_inventory_alerts(
    alerts: list[dict[str, Any]],
) -> None:
    """Send inventory alerts only after the admin mutation is durable."""

    for alert in alerts:
        try:
            kind = alert.get("kind")

            if kind == "out_of_stock":
                event = "inventory_out_of_stock"
                title = "Vibe4You Out of Stock"
                tags = ["rotating_light"]
            elif kind == "low_stock":
                event = "inventory_low_stock"
                title = "Vibe4You Low Stock"
                tags = ["warning"]
            else:
                continue

            product_name = " ".join(
                str(alert.get("productName") or "-").split()
            )[:120]

            size = " ".join(
                str(alert.get("size") or "-").split()
            )[:40]

            colour = " ".join(
                str(alert.get("colour") or "-").split()
            )[:80]

            owner_notifier().send(
                event=event,
                title=title,
                message=(
                    f"Product: {product_name}\n"
                    f"Variant: {size} / {colour}\n"
                    f"Remaining: {alert.get('remaining')}"
                ),
                priority=5,
                tags=tags,
            )

        except Exception:
            print(
                "Vibe4You notification preparation failed "
                "event=inventory",
                flush=True,
            )


class AdminApplication:
    def __init__(self, database: Path, encryption_key: str, catalog: Path, settings: Path, data_dir: Path) -> None:
        public = load_public_module()
        self.identity = AdminStore(database, encryption_key)
        self.delivery_zones = DeliveryZoneStore(database)
        probe = sqlite3.connect(database)
        try:
            has_customers = probe.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='users'"
            ).fetchone() is not None
        finally:
            probe.close()
        self.shops = ShopWorkflow(database) if has_customers else None
        self.reviews = ReviewWorkflow(database) if has_customers else None
        self._store_product_image_payload = public.store_product_image_payload
        self._public_security_error = public.SecurityError
        self._public_api_error = public.ApiError
        self._ensure_admin_refund_token = public.ensure_admin_refund_token
        self._refund_bridge_url = os.environ.get(
            "STYLEDASH_REFUND_BRIDGE_URL",
            "http://127.0.0.1:8080/api/internal-admin/refund-cancel",
        ).strip()
        self.product_image_directory = database.parent / "product-images"
        self.invoices = InvoiceGateway(data_dir)
        self.tax_classifications = TaxClassificationRegistry(data_dir)
        self.payments = public.PaymentService(
            catalog, settings, data_dir, webhook_secret="",
            mode=os.environ.get("RAZORPAY_MODE", "test"), gateway=None,
            shop_workflow=self.shops,
        )
        self.billing_audit = BillingAuditService(
            self.payments, data_dir, enable_storage=False
        )
        self.order_documents = OrderDocuments(
            database, self._order_snapshot, self._customer_invoice_for_export, self.identity.record_action
        )
        self.order_profit = OrderProfitLedger(
            database, self.order_documents, self._order_snapshot, self.identity.record_action,
            tax_data_dir=self.payments.store.path.parent
        )
        print(
            "Vibe4You admin refund transport="
            + ("direct-gateway" if self.payments.gateway is not None else "internal-bridge"),
            flush=True,
        )

    def store_product_image(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return self._store_product_image_payload(self.product_image_directory, payload)
        except self._public_security_error as exc:
            if isinstance(exc, SecurityError):
                raise
            raise SecurityError(exc.status, exc.message, exc.code) from None

    def delivery_zone_configuration(self) -> dict[str, Any]:
        config = self.delivery_zones.configuration()
        policy = self.delivery_zones.policy()
        return {"configuration": config, "activeZoneCount": len(policy.zones)}

    def list_product_reviews(self, admin_id: str) -> list[dict[str, Any]]:
        if self.reviews is None:
            raise SecurityError(503, "Reviews are unavailable.", "reviews_unavailable")
        return self.reviews.admin_list_product_reviews(admin_id)

    def moderate_product_review(self, admin_id: str, review_id: str, status: Any) -> dict[str, Any]:
        if self.reviews is None:
            raise SecurityError(503, "Reviews are unavailable.", "reviews_unavailable")
        result = self.reviews.moderate_product_review(admin_id, review_id, status)
        self.identity.record_action(
            admin_id, f"product_review_{result['status']}", "product_review",
            result["id"], "success",
            {"productId": result["productId"], "status": result["status"]},
        )
        return result

    def list_store_reviews(self, admin_id: str) -> list[dict[str, Any]]:
        if self.reviews is None:
            raise SecurityError(503, "Local-store reviews are unavailable until customer storage is initialized.", "reviews_unavailable")
        return self.reviews.admin_list_store_reviews(admin_id)

    def moderate_store_review(self, admin_id: str, review_id: str, status: Any) -> dict[str, Any]:
        if self.reviews is None:
            raise SecurityError(503, "Local-store reviews are unavailable until customer storage is initialized.", "reviews_unavailable")
        result = self.reviews.moderate_store_review(admin_id, review_id, status)
        self.identity.record_action(
            admin_id,
            f"store_review_{result['status']}",
            "store_review",
            result["id"],
            "success",
            {"storeId": result["storeId"], "status": result["status"]},
        )
        return result

    def replace_delivery_zone_configuration(self, admin_id: str, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise SecurityError(400, "Delivery-zone configuration must be an object.", "invalid_delivery_zone")
        try:
            self.delivery_zones.replace_configuration(payload, updated_by=admin_id)
            result = self.delivery_zone_configuration()
        except DeliveryZoneConfigError as exc:
            raise SecurityError(400, str(exc), "invalid_delivery_zone") from None
        config = result["configuration"]
        self.identity.record_action(admin_id, "delivery_zone_updated", "delivery_zone", "primary", "success", {
            "enforcementMode": config.get("enforcementMode"),
            "activeZoneCount": result["activeZoneCount"],
        })
        return result

    def list_orders(self, query: str = "") -> list[dict[str, Any]]:
        needle = query.strip().casefold()[:100]
        with self.payments.store.lock:
            orders = list(self.payments.store.state["orders"].values())
            if needle:
                orders = [order for order in orders if needle in str(order.get("id", "")).casefold()]
            selected = [dict(order) for order in sorted(orders, key=lambda item: item.get("createdAt", ""), reverse=True)[:250]]
        return [self._order_for_admin(order) for order in selected]

    def external_payment_report(self, month: str) -> dict[str, Any]:
        if not isinstance(month, str) or not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
            raise SecurityError(400, "Enter a valid year and month.", "invalid_month")
        with self.payments.store.lock:
            rows = []
            for order in self.payments.store.state["orders"].values():
                payment = order.get("externalPayment") if isinstance(order, dict) else None
                if not isinstance(payment, dict) or not str(payment.get("paymentDate") or "").startswith(month + "-"):
                    continue
                rows.append({
                    "orderId": order.get("id"), "deliveryRequestId": order.get("deliveryRequestId"),
                    "customer": (order.get("address") or {}).get("name"),
                    "method": payment.get("method"), "reference": payment.get("reference"),
                    "paymentDate": payment.get("paymentDate"), "amountPaise": payment.get("amountPaise"),
                    "verifiedAt": payment.get("verifiedAt"), "status": order.get("status"),
                })
        rows.sort(key=lambda item: (item["paymentDate"], item["orderId"] or ""), reverse=True)
        return {"month": month, "count": len(rows), "amountPaise": sum(int(row["amountPaise"] or 0) for row in rows), "payments": rows,
                "notice": "Operational payment reconciliation only; not a GST or profit report."}

    def _order_for_admin(self, order: dict[str, Any]) -> dict[str, Any]:
        result = self.payments.order_for_display(order)
        # Phase 1 exposes no supplier-document metadata through order reads.
        result.pop("supplierBills", None)
        return result

    def list_outside_delivery_requests(self) -> list[dict[str, Any]]:
        return self.payments.admin_list_delivery_requests()

    def create_manual_order(self, admin_id: str, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise SecurityError(400, "Manual order must be an object.", "invalid_manual_order")
        customer_id = payload.get("customerId")
        if customer_id is not None:
            if not isinstance(customer_id, str) or not customer_id.strip():
                raise SecurityError(400, "Enter a valid customer ID.", "invalid_manual_order")
            with self.identity.connect() as db:
                customer = db.execute("SELECT phone FROM users WHERE id=?", (customer_id,)).fetchone()
            if customer is None:
                raise SecurityError(404, "Customer account not found.", "profile_not_found")
            address = payload.get("address") or {}
            if not isinstance(address, dict) or re.sub(r"\D", "", str(customer["phone"] or ""))[-10:] != re.sub(r"\D", "", str(address.get("phone") or ""))[-10:]:
                raise SecurityError(409, "Customer account phone does not match the order phone.", "customer_mismatch")
        try:
            result = self.payments.create_manual_order(
                {key: value for key, value in payload.items() if key != "customerId"}, customer_id
            )
        except self._public_api_error as exc:
            raise SecurityError(exc.status, exc.message, exc.code) from None
        if not result["idempotent"]:
            self.identity.record_action(admin_id, "manual_order_created", "order", result["order"]["id"], "success", {
                "channel": payload["source"], "grandTotal": result["order"]["grandTotal"],
                "registeredCustomer": bool(customer_id),
            })
        return result

    def confirm_existing_order_payment(self, admin_id: str, order_id: str, payload: Any) -> dict[str, Any]:
        try:
            result = self.payments.confirm_external_delivery_payment(
                None, payload, admin_id, manual_order_id=order_id
            )
        except self._public_api_error as exc:
            raise SecurityError(exc.status, exc.message, exc.code) from None
        if not result["idempotent"]:
            self.identity.record_action(admin_id, "external_payment_verified", "order", order_id, "success", {
                "method": payload["method"], "amount": payload["amount"],
                "paymentDate": payload["paymentDate"], "reference": payload["reference"].strip().upper(),
            })
        return result

    def confirm_external_delivery_payment(self, admin_id: str, request_id: str, payload: Any) -> dict[str, Any]:
        try:
            result = self.payments.confirm_external_delivery_payment(request_id, payload, admin_id)
        except self._public_api_error as exc:
            raise SecurityError(exc.status, exc.message, exc.code) from None
        if not result["idempotent"]:
            payment = payload["reference"].strip().upper()
            self.identity.record_action(
                admin_id, "external_payment_verified", "order", result["order"]["id"], "success",
                {"deliveryRequestId": request_id, "method": payload["method"],
                 "amount": payload["amount"], "paymentDate": payload["paymentDate"],
                 "reference": payment},
            )
        return result

    def quote_outside_delivery_request(self, admin_id: str, request_id: str, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise SecurityError(400, "Delivery quote must be an object.", "invalid_delivery_quote")
        try:
            result = self.payments.quote_delivery_request(
                request_id,
                payload.get("deliveryFee"),
                payload.get("note"),
                payload.get("estimatedDelivery"),
                admin_id,
            )
        except self._public_api_error as exc:
            raise SecurityError(exc.status, exc.message, exc.code) from None
        self.identity.record_action(
            admin_id,
            "outside_delivery_quoted",
            "outside_delivery_request",
            request_id,
            "success",
            {
                "deliveryFee": (result.get("quote") or {}).get("deliveryFee"),
                "grandTotal": (result.get("quote") or {}).get("grandTotal"),
            },
        )
        return result

    def reject_outside_delivery_request(self, admin_id: str, request_id: str, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise SecurityError(400, "Rejection request must be an object.", "invalid_delivery_rejection")
        try:
            result = self.payments.reject_delivery_request(request_id, payload.get("reason"), admin_id)
        except self._public_api_error as exc:
            raise SecurityError(exc.status, exc.message, exc.code) from None
        self.identity.record_action(
            admin_id,
            "outside_delivery_rejected",
            "outside_delivery_request",
            request_id,
            "success",
            {"reason": result.get("rejectionReason")},
        )
        return result

    def payment_alerts(self) -> list[dict[str, Any]]:
        with self.payments.store.lock:
            alerts = self.payments.store.state["operationalAlerts"].values()
            return [
                dict(alert)
                for alert in sorted(alerts, key=lambda item: item.get("recordedAt", ""), reverse=True)[:250]
            ]

    def get_order(self, order_id: str) -> dict[str, Any]:
        with self.payments.store.lock:
            order = self.payments.store.state["orders"].get(order_id)
            if order is None:
                raise SecurityError(404, "Order not found.", "order_not_found")
            selected = dict(order)
        return self._order_for_admin(selected)

    @staticmethod
    def _billing_security_error(error: BillingAuditError) -> SecurityError:
        return SecurityError(error.status, error.message, error.code)

    def billing_preview(self, month: str) -> dict[str, Any]:
        require_billing_preview_mode()
        try:
            return self.billing_audit.preview(month)
        except BillingAuditError as error:
            raise self._billing_security_error(error) from None

    def upload_supplier_bill(
        self, admin_id: str, order_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        deny_financial_billing()

    def supplier_bill_document(
        self, order_id: str, bill_id: str
    ) -> tuple[bytes, str, str]:
        deny_financial_billing()

    def billing_report(self, month: str) -> dict[str, Any]:
        deny_financial_billing()

    def billing_report_pdf(self, month: str, kind: str) -> bytes:
        deny_financial_billing()

    def _order_snapshot(self) -> dict[str, dict[str, Any]]:
        """Read-only copy of the orders; the order store itself is never written by month-end documents."""
        with self.payments.store.lock:
            return {
                str(key): dict(value)
                for key, value in self.payments.store.state["orders"].items()
                if isinstance(value, dict)
            }

    def _customer_invoice_for_export(self, order_id: str) -> tuple[str, bytes]:
        """The issued GST tax invoice when one exists, otherwise the existing payment receipt."""
        try:
            issued = self.invoices.issued_for_order(order_id)
        except Exception:
            issued = None
        if issued is not None:
            return "tax_invoice", self.invoices.download_issued(order_id)
        return "receipt", self.receipt_pdf(order_id)

    @staticmethod
    def _document_error(error: OrderDocumentError) -> SecurityError:
        return SecurityError(error.status, error.message, error.code)

    def month_end_overview(self, month: str) -> dict[str, Any]:
        try:
            return self.order_profit.overview(month)
        except (OrderDocumentError, OrderProfitError) as error:
            raise self._document_error(error) from None

    def save_order_profit(self, admin_id: str, order_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return self.order_profit.save(admin_id, order_id, payload)
        except (OrderDocumentError, OrderProfitError) as error:
            raise self._document_error(error) from None

    def month_end_profit_csv(self, month: str) -> bytes:
        try:
            return self.order_profit.export_csv(month)
        except (OrderDocumentError, OrderProfitError) as error:
            raise self._document_error(error) from None

    def upload_seller_bill(self, admin_id: str, order_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return self.order_documents.upload(admin_id, order_id, payload)
        except OrderDocumentError as error:
            raise self._document_error(error) from None

    def void_seller_bill(self, admin_id: str, order_id: str, bill_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return self.order_documents.void(admin_id, order_id, bill_id, payload)
        except OrderDocumentError as error:
            raise self._document_error(error) from None

    def seller_bill_file(self, order_id: str, bill_id: str) -> tuple[bytes, str, str]:
        try:
            return self.order_documents.document(order_id, bill_id)
        except OrderDocumentError as error:
            raise self._document_error(error) from None

    def month_end_export(self, admin_id: str, month: str) -> tuple[Any, int, str, dict[str, Any]]:
        try:
            return self.order_documents.export_month(admin_id, month)
        except OrderDocumentError as error:
            raise self._document_error(error) from None

    def receipt_pdf(self, order_id: str) -> bytes:
        """Generate the existing delivered customer PDF without changing the order."""
        with self.payments.store.lock:
            order = self.payments.store.state["orders"].get(order_id)
            if order is None:
                raise SecurityError(404, "Order not found.", "order_not_found")
            selected = dict(order)
        if selected.get("isPaymentTestOrder") is True or selected.get("fulfillmentRequired") is False:
            raise SecurityError(409, "Payment test orders do not have a delivered invoice.", "receipt_not_ready")
        return self.payments.receipt_pdf(selected)

    def tax_classification_list(self) -> list[dict[str, str]]:
        return self.tax_classifications.list_recent()

    def approve_tax_classification(
        self, admin_id: str, payload: dict[str, Any]
    ) -> dict[str, str]:
        if not admin_id:
            raise SecurityError(403,"Administrator required","admin_authentication_required")
        self.payments.refresh_shop_products()
        product_id=payload.get("productId")
        if not isinstance(product_id,str) or product_id not in self.payments.product_snapshot():
            raise SecurityError(404,"Product not found","invalid_product")
        try:
            return self.tax_classifications.approve(
                product_id=product_id,
                hsn_code=payload.get("hsnCode"),
                gst_rate=payload.get("gstRate"),
                supply_type=payload.get("supplyType"),
                evidence=payload.get("evidence"),
                effective_from=payload.get("effectiveFrom"),
                approved_by=admin_id,
            )
        except InvoiceDraftError as exc:
            raise SecurityError(400,str(exc),"invalid_tax_classification") from None

    def approve_tax_csv(self, admin_id: str, payload: dict[str, Any],
                        products: list[dict[str, Any]]) -> dict[str, Any]:
        """Approve only explicitly marked and source-verified published SKUs."""
        if not admin_id:
            raise SecurityError(403,"Administrator required","admin_authentication_required")
        if payload.get("confirmation") != "APPROVE VERIFIED GST RATES":
            raise SecurityError(400,"Explicit GST classification approval is required",
                                "gst_approval_required")
        try:
            records=parse_approved_csv(payload.get("csvText"),products)
            approved=self.tax_classifications.approve_batch(
                records=records,approved_by=admin_id
            )
        except InvoiceDraftError as exc:
            raise SecurityError(400,str(exc),"invalid_tax_classification") from None
        return {"approved":len(approved),"productIds":[r["product_id"] for r in approved]}

    def approve_source_backed_watch_rates(self, admin_id: str,
                                           confirmation: str,
                                           products: list[dict[str,Any]]) -> dict[str,Any]:
        """Approve exact documented wristwatch rate; no CA and no price change."""
        if not admin_id:
            raise SecurityError(403,"Administrator required","admin_authentication_required")
        if confirmation!="APPLY VERIFIED WATCH RATES":
            raise SecurityError(400,"Explicit official GST rate confirmation is required",
                                "gst_approval_required")
        existing=self.tax_classifications.list_all()
        rows=high_confidence_records(products,existing)
        if len(rows)>100:
            raise SecurityError(409,"Too many watch matches; use the review CSV",
                                "gst_bulk_limit")
        if not rows:
            return {"approved":0,"productIds":[]}
        try:
            approved=self.tax_classifications.approve_batch(
                records=rows,approved_by=admin_id
            )
        except InvoiceDraftError as exc:
            raise SecurityError(400,str(exc),"invalid_tax_classification") from None
        return {"approved":len(approved),"productIds":[a["product_id"] for a in approved]}

    def invoice_readiness(self) -> dict[str, Any]:
        """Return only non-sensitive issuance readiness for the private admin UI."""
        try:
            config=self.invoices.configuration()
            approval=config.get("approval") or {}
            seller=config.get("seller") or {}
            approved_keys=(
                "invoice_issuance_enabled","gst_registration_confirmed",
                "seller_address_confirmed","classifications_verified",
                "place_of_supply_verified","shipping_tax_policy_verified",
                "einvoice_applicability_reviewed","lawful_issuance_procedure_approved",
            )
            enabled=(
                all(approval.get(k) is True for k in approved_keys)
                and approval.get("einvoice_required") is False
                and isinstance(seller.get("pincode"),str)
                and len(seller["pincode"])==6 and seller["pincode"].isdigit()
                and bool(seller.get("address"))
                and seller.get("gstin")=="23JVZPM8734E1ZT"
                and seller.get("legal_name")=="Manorama"
                and bool(str(seller.get("authorised_signatory") or "").strip())
                and isinstance(config.get("tax_policy"),dict)
            )
            return {"enabled":bool(enabled),"reason":"" if enabled else "GST invoice setup pending verification"}
        except InvoiceDraftError:
            return {"enabled":False,"reason":"GST invoice setup pending verification"}

    def issue_tax_invoice(self, admin_id: str, order_id: str) -> dict[str, Any]:
        """Idempotent administrator issuance. Server-side config only; CSRF required."""
        if not admin_id:
            raise SecurityError(403,"Administrator required.","admin_authentication_required")
        with self.payments.store.lock:
            source=self.payments.store.state["orders"].get(order_id)
            if not isinstance(source,dict):
                raise SecurityError(404,"Order not found.","order_not_found")
            original=json.loads(json.dumps(source))
        issue_date=datetime.now(timezone(timedelta(hours=5,minutes=30))).date().isoformat()
        try:
            result=self.invoices.issue_from_order(original,issue_date=issue_date)
        except InvoiceDraftError as exc:
            raise SecurityError(409,str(exc),"tax_invoice_not_ready") from None
        return {
            "invoiceNumber":result["invoice_number"],
            "issueDate":result["issue_date"],"orderId":order_id,
            "grandTotal":result["gross_total"],"gstIncluded":result["gst_total"],
        }

    def tax_invoice_pdf(self, order_id: str) -> bytes:
        """Read-only PDF download; never automatically issues a new invoice."""
        with self.payments.store.lock:
            if order_id not in self.payments.store.state["orders"]:
                raise SecurityError(404,"Order not found.","order_not_found")
        try:
            return self.invoices.download_issued(order_id)
        except InvoiceDraftError as exc:
            raise SecurityError(409,str(exc),"tax_invoice_not_ready") from None

    def _resolve_order_alerts(
        self,
        state: dict[str, Any],
        order: dict[str, Any],
        alert_types: set[str],
        now: str,
    ) -> None:
        order_id = order.get("id")
        for alert in state.get("operationalAlerts", {}).values():
            if (
                isinstance(alert, dict)
                and alert.get("styleDashOrderId") == order_id
                and alert.get("status") == "open"
                and alert.get("type") in alert_types
            ):
                alert["status"] = "resolved"
                alert["resolvedAt"] = now
        order["requiresAdminAttention"] = any(
            isinstance(alert, dict)
            and alert.get("styleDashOrderId") == order_id
            and alert.get("status") == "open"
            for alert in state.get("operationalAlerts", {}).values()
        )

    def mark_cod_paid(self, admin_id: str, order_id: str, collection_method: Any) -> dict[str, Any]:
        methods = {"cash": "cash", "upi_at_delivery": "upi_at_delivery"}
        if not isinstance(collection_method, str) or collection_method not in methods:
            raise SecurityError(400, "Choose Cash or UPI at delivery.", "invalid_cod_collection_method")
        with self.payments.store.lock:
            order = self.payments.store.state["orders"].get(order_id)
            if order is None:
                raise SecurityError(404, "Order not found.", "order_not_found")
            if order.get("fulfillmentRequired") is False:
                raise SecurityError(409, "Payment validation orders cannot be marked manually.", "manual_payment_forbidden")
            if order.get("paymentMethod") != "cod":
                raise SecurityError(409, "Razorpay payments cannot be marked paid manually.", "manual_payment_forbidden")
            if order.get("status") == "cancelled":
                raise SecurityError(409, "A cancelled order cannot be marked paid.", "cancelled_order")
            if order.get("paymentStatus") != "pending":
                raise SecurityError(409, "This COD payment is no longer pending.", "payment_not_pending")
            now = iso(utc_now())
            order["paymentStatus"] = "paid"
            order["paymentCollectionMethod"] = methods[collection_method]
            order["paymentCollectedAt"] = now
            if order.get("codAdvancePaid") is True:
                order["codAmountCollected"] = int(order.get("codAmountDue", 0) or 0)
            order["updatedAt"] = now
            self.payments.store.save()
            result = dict(order)
        self.identity.record_action(admin_id, "cod_payment_marked_paid", "order", order_id, "success", {
            "collectionMethod": result["paymentCollectionMethod"], "paymentCollectedAt": result["paymentCollectedAt"]
        })
        return self.payments.order_for_display(result)

    def mark_try_at_home_late_fee_paid(self, admin_id: str, order_id: str, collection_method: Any) -> dict[str, Any]:
        methods = {"cash": "cash", "upi_at_delivery": "upi_at_delivery"}
        if not isinstance(collection_method, str) or collection_method not in methods:
            raise SecurityError(400, "Choose Cash or UPI for the late fee.", "invalid_late_fee_collection_method")
        with self.payments.store.lock:
            order = self.payments.store.state["orders"].get(order_id)
            if order is None:
                raise SecurityError(404, "Order not found.", "order_not_found")
            due = int(order.get("tryAtHomeLateFeeDue", 0) or 0)
            if due <= 0:
                raise SecurityError(409, "No Try at Home late fee is due.", "late_fee_not_due")
            if order.get("tryAtHomeLateFeePaid") is True:
                raise SecurityError(409, "The Try at Home late fee is already paid.", "late_fee_already_paid")
            now = iso(utc_now())
            order["tryAtHomeLateFeePaid"] = True
            order["tryAtHomeLateFeeCollectionMethod"] = methods[collection_method]
            order["tryAtHomeLateFeeCollectedAt"] = now
            order["updatedAt"] = now
            order.setdefault("statusHistory", []).append({"status": "try_at_home_late_fee_paid", "timestamp": now, "note": f"Rs {due} Try at Home late fee collected by {methods[collection_method]}"})
            self.payments.store.save()
            result = dict(order)
        self.identity.record_action(admin_id, "try_at_home_late_fee_paid", "order", order_id, "success", {"amount": due, "collectionMethod": methods[collection_method]})
        return self.payments.order_for_display(result)

    def mark_cancellation_fee_paid(self, admin_id: str, order_id: str, collection_method: Any) -> dict[str, Any]:
        methods = {"cash": "cash", "upi_at_delivery": "upi_at_delivery"}
        if not isinstance(collection_method, str) or collection_method not in methods:
            raise SecurityError(400, "Choose Cash or UPI for the cancellation fee.", "invalid_cancellation_fee_collection_method")
        with self.payments.store.lock:
            order = self.payments.store.state["orders"].get(order_id)
            if order is None:
                raise SecurityError(404, "Order not found.", "order_not_found")
            request = order.get("cancellationRequest")
            if not isinstance(request, dict) or int(request.get("feeDue", 0) or 0) <= 0:
                raise SecurityError(409, "No cancellation fee is due.", "cancellation_fee_not_due")
            if request.get("status") != "requested":
                raise SecurityError(409, "This cancellation request is no longer active.", "cancellation_unavailable")
            if request.get("feePaid") is True:
                raise SecurityError(409, "The cancellation fee is already paid.", "cancellation_fee_already_paid")
            now = iso(utc_now())
            request.update({"feePaid": True, "feeCollectionMethod": methods[collection_method], "feeCollectedAt": now})
            order["updatedAt"] = now
            order.setdefault("statusHistory", []).append({"status": "cancellation_fee_paid", "timestamp": now, "note": f"Rs {request['feeDue']} cancellation fee collected by {methods[collection_method]}"})
            self.payments.store.save()
            result = dict(order)
        self.identity.record_action(admin_id, "cancellation_fee_paid", "order", order_id, "success", {"amount": request["feeDue"], "collectionMethod": methods[collection_method]})
        return self.payments.order_for_display(result)

    def mark_exchange_fee_paid(self, admin_id: str, order_id: str, exchange_id: str, collection_method: Any) -> dict[str, Any]:
        methods = {"cash": "cash", "upi_at_delivery": "upi_at_delivery"}
        if not isinstance(collection_method, str) or collection_method not in methods:
            raise SecurityError(400, "Choose Cash or UPI for the exchange fee.", "invalid_exchange_fee_collection_method")
        with self.payments.store.lock:
            order = self.payments.store.state["orders"].get(order_id)
            if order is None:
                raise SecurityError(404, "Order not found.", "order_not_found")
            exchange = next((entry for entry in order.get("exchangeRequests", []) if entry.get("id") == exchange_id), None)
            if not isinstance(exchange, dict):
                raise SecurityError(404, "Exchange request not found.", "exchange_not_found")
            if exchange.get("status") != "approved":
                raise SecurityError(409, "Approve and reserve the replacement size before collecting the exchange fee.", "exchange_fee_not_ready")
            if exchange.get("feePaid") is True:
                raise SecurityError(409, "The exchange fee is already paid.", "exchange_fee_already_paid")
            now = iso(utc_now())
            exchange.update({"feePaid": True, "feeCollectionMethod": methods[collection_method], "feeCollectedAt": now})
            order["updatedAt"] = now
            order.setdefault("statusHistory", []).append({"status": "exchange_fee_paid", "timestamp": now, "note": f"Rs {exchange['feeDue']} exchange fee collected by {methods[collection_method]}"})
            self.payments.store.save()
            result = dict(order)
        self.identity.record_action(admin_id, "exchange_fee_paid", "exchange_request", exchange_id, "success", {"orderId": order_id, "amount": exchange["feeDue"], "collectionMethod": methods[collection_method]})
        return self.payments.order_for_display(result)

    def update_exchange_status(self, admin_id: str, order_id: str, exchange_id: str, requested: Any) -> dict[str, Any]:
        transitions = {"requested": {"approved", "rejected"}, "approved": {"completed", "rejected"}}
        if not isinstance(requested, str):
            raise SecurityError(400, "Invalid exchange status.", "invalid_exchange_status")
        target = requested.strip().lower()
        self.payments.refresh_shop_products()
        products = self.payments.product_snapshot()
        inventory_alerts: list[dict[str, Any]] = []
        with self.payments.store.lock:
            state = self.payments.store.state
            order = state["orders"].get(order_id)
            if order is None:
                raise SecurityError(404, "Order not found.", "order_not_found")
            exchange = next((entry for entry in order.get("exchangeRequests", []) if entry.get("id") == exchange_id), None)
            if not isinstance(exchange, dict):
                raise SecurityError(404, "Exchange request not found.", "exchange_not_found")
            current = str(exchange.get("status") or "")
            if target not in transitions.get(current, set()):
                raise SecurityError(409, "Exchange transition is not allowed.", "invalid_exchange_transition")
            product = products.get(exchange.get("productId"))
            try:
                quantity = int(exchange.get("quantity", 0) or 0)
            except (TypeError, ValueError):
                quantity = 0
            variants = product.get("variants", []) if isinstance(product, dict) else []
            source = next((entry for entry in variants if entry.get("id") == exchange.get("sourceVariantId")), None)
            replacement = next((entry for entry in variants if entry.get("id") == exchange.get("targetVariantId")), None)
            now = iso(utc_now())
            if target == "approved":
                if source is None or replacement is None or quantity <= 0:
                    raise SecurityError(409, "Exchange inventory cannot be reconciled safely.", "exchange_inventory_unavailable")
                before = self.payments._inventory(state, replacement)
                if replacement.get("active") is False or before < quantity:
                    raise SecurityError(409, "The replacement size is no longer available.", "exchange_stock_changed")
                after = before - quantity
                state["inventory"][replacement["id"]] = after
                exchange.update({"targetReserved": True, "approvedAt": now})
                alert = self.payments._inventory_alert_for_change(product, replacement, before, after)
                if alert is not None:
                    inventory_alerts.append(alert)
            elif target == "rejected" and exchange.get("targetReserved") is True and exchange.get("inventoryAdjusted") is not True:
                if replacement is None or quantity <= 0:
                    raise SecurityError(409, "Reserved replacement stock cannot be reconciled safely.", "exchange_inventory_unavailable")
                state["inventory"][replacement["id"]] = self.payments._inventory(state, replacement) + quantity
                exchange["targetReserved"] = False
            elif target == "completed":
                if exchange.get("feePaid") is not True or exchange.get("targetReserved") is not True:
                    raise SecurityError(409, "Collect the exchange fee and reserve replacement stock before completion.", "exchange_not_ready")
                if source is None or quantity <= 0:
                    raise SecurityError(409, "Returned stock cannot be reconciled safely.", "exchange_inventory_unavailable")
                state["inventory"][source["id"]] = self.payments._inventory(state, source) + quantity
                exchange.update({"inventoryAdjusted": True, "completedAt": now})
            exchange["status"] = target
            exchange["reviewedBy"] = admin_id
            exchange["updatedAt"] = now
            order["updatedAt"] = now
            order.setdefault("statusHistory", []).append({"status": f"exchange_{target}", "timestamp": now, "note": f"Exchange {target}: {exchange.get('sourceSize')} to {exchange.get('targetSize')}"})
            self.payments.store.save()
            result = dict(order)
        self.identity.record_action(admin_id, f"exchange_{target}", "exchange_request", exchange_id, "success", {"orderId": order_id, "inventoryAdjusted": exchange.get("inventoryAdjusted") is True})
        if inventory_alerts:
            _notify_inventory_alerts(inventory_alerts)
        return self.payments.order_for_display(result)

    def _refund_via_public_service(
        self,
        admin_id: str,
        order_id: str,
        reason: Any,
    ) -> dict[str, Any]:
        parsed = urlsplit(self._refund_bridge_url)
        if (
            parsed.scheme != "http"
            or (parsed.hostname or "").lower() not in {"127.0.0.1", "localhost", "::1"}
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or parsed.path != "/api/internal-admin/refund-cancel"
        ):
            raise SecurityError(
                503,
                "The private refund bridge is not configured safely.",
                "refund_bridge_unavailable",
            )

        token = self._ensure_admin_refund_token(self.payments.store.path.parent)
        body = json.dumps(
            {"orderId": order_id, "requestedBy": admin_id, "reason": reason},
            separators=(",", ":"),
        ).encode("utf-8")
        request = Request(
            self._refund_bridge_url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "X-Vibe4You-Admin-Refund-Token": token,
            },
        )
        try:
            with urlopen(request, timeout=20) as response:
                raw = response.read()
        except HTTPError as error:
            try:
                payload = json.loads(error.read().decode("utf-8"))
            except Exception:
                payload = {}
            message = payload.get("error") if isinstance(payload, dict) else None
            code = payload.get("code") if isinstance(payload, dict) else None
            raise SecurityError(
                int(error.code),
                message if isinstance(message, str) and message else "Refund request failed.",
                code if isinstance(code, str) and code else "refund_request_failed",
            ) from None
        except (URLError, TimeoutError, OSError):
            raise SecurityError(
                503,
                "The private refund service is temporarily unavailable. Refresh the order before retrying.",
                "refund_bridge_unavailable",
            ) from None

        try:
            result = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise SecurityError(
                502,
                "The private refund service returned an invalid response.",
                "invalid_refund_response",
            ) from None
        if not isinstance(result, dict) or result.get("success") is not True:
            raise SecurityError(
                502,
                "The private refund service returned an invalid response.",
                "invalid_refund_response",
            )
        return result

    def refund_and_cancel_order(
        self,
        admin_id: str,
        order_id: str,
        reason: Any,
    ) -> dict[str, Any]:
        if self.payments.gateway is None:
            result = self._refund_via_public_service(admin_id, order_id, reason)
        else:
            try:
                result = self.payments.initiate_full_refund_for_cancellation(
                    order_id,
                    admin_id,
                    reason,
                )
            except self._public_api_error as exc:
                raise SecurityError(exc.status, exc.message, exc.code) from None

        with self.payments.store.lock:
            stored = self.payments.store.state["orders"].get(order_id)
            if not isinstance(stored, dict):
                raise SecurityError(404, "Order not found.", "order_not_found")
            display_order = self.payments.order_for_display(dict(stored))
            refund_request = stored.get("refundRequest")
            refund_id = (
                refund_request.get("razorpayRefundId")
                if isinstance(refund_request, dict)
                else result.get("refundId")
            )
            refund_amount = (
                refund_request.get("amount")
                if isinstance(refund_request, dict)
                else stored.get("amount")
            )

        if result.get("idempotent") is not True:
            self.identity.record_action(
                admin_id,
                "order_refund_submitted",
                "order",
                order_id,
                "success",
                {
                    "amountPaise": refund_amount,
                    "razorpayRefundId": refund_id,
                    "reason": " ".join(str(reason).strip().split())[:500],
                    "cancelAfterRefund": True,
                },
            )

        return {
            "order": display_order,
            "pending": result.get("pending", True),
            "refundId": refund_id,
            "idempotent": result.get("idempotent") is True,
        }


    def update_order_tracking(self, admin_id: str, order_id: str, tracking_id: Any) -> dict[str, Any]:
        """Save a courier/AWB tracking ID, publishing it in customer status history.

        The read/write lock serializes this update with the storefront and
        saves the same orders.json used by both services. No order status,
        payment, inventory, or invoice values are changed here.
        """
        if not isinstance(tracking_id, str):
            raise SecurityError(400, "Enter a valid tracking ID.", "invalid_tracking_id")
        tracking_id = tracking_id.strip()
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{3,79}", tracking_id):
            raise SecurityError(
                400, "Tracking ID must be 4-80 characters (letters, numbers, -, _, . or /).",
                "invalid_tracking_id"
            )
        with self.payments.store.lock:
            order = self.payments.store.state["orders"].get(order_id)
            if not isinstance(order, dict):
                raise SecurityError(404, "Order not found.", "order_not_found")
            if order.get("isPaymentTestOrder") is True or order.get("fulfillmentRequired") is False:
                raise SecurityError(409, "Tracking is unavailable for test orders.", "no_fulfillment_order")
            if order.get("status") not in {
                "confirmed", "preparing", "packed", "out_for_delivery", "delivered"
            }:
                raise SecurityError(409, "Confirm the order before adding tracking.", "order_not_confirmed")
            cancel = order.get("cancellationRequest")
            refund = order.get("refundRequest")
            if isinstance(cancel, dict) and cancel.get("status") == "requested":
                raise SecurityError(409, "Resolve the cancellation request first.", "cancellation_pending")
            if isinstance(refund, dict) and refund.get("status") in {
                "submitting", "submitted", "processing", "uncertain", "failed"
            }:
                raise SecurityError(409, "Resolve the refund request first.", "refund_pending")
            previous = str(order.get("trackingId") or "")
            if previous == tracking_id:
                return self._order_for_admin(dict(order))
            now = iso(utc_now())
            history = order.get("statusHistory")
            if not isinstance(history, list):
                history = []
            # Only the current AWB is customer-visible. Replacing an incorrect
            # ID must not leave the stale one visible in previous history rows.
            history = [
                row for row in history
                if not (isinstance(row, dict) and row.get("event") == "courier_tracking")
            ]
            history.append({
                "status": "courier_tracking", "timestamp": now, "event": "courier_tracking",
                "note": "Courier tracking ID: " + tracking_id,
            })
            order["trackingId"] = tracking_id
            order["trackingUpdatedAt"] = now
            order["statusHistory"] = history
            # Preserve order.updatedAt; it is a legacy delivered-date fallback.
            self.payments.store.save()
            result = dict(order)
        self.identity.record_action(
            admin_id, "courier_tracking_updated", "order", order_id, "success",
            {"replaced": bool(previous), "trackingIdSuffix": tracking_id[-4:]},
        )
        return self._order_for_admin(result)

    def update_order_status(
        self, admin_id: str, order_id: str, requested: Any, reason: Any = None
    ) -> dict[str, Any]:
        transitions = {
            "payment_pending": {"cancelled"},
            "payment_review_required": {"placed", "cancelled"},
            "placed": {"confirmed", "cancelled"},
            "confirmed": {"preparing", "packed", "cancelled"},
            "preparing": {"out_for_delivery", "cancelled"},
            "packed": {"out_for_delivery", "cancelled"},
            "out_for_delivery": {"delivered", "cancelled"},
            "delivered": set(),
            "cancelled": set(),
        }
        if not isinstance(requested, str):
            raise SecurityError(
                400,
                "Invalid order status.",
                "invalid_status",
            )

        inventory_alerts: list[dict[str, Any]] = []

        with self.payments.store.lock:
            state = self.payments.store.state
            order = state["orders"].get(order_id)
            if order is None:
                raise SecurityError(404, "Order not found.", "order_not_found")
            if order.get("fulfillmentRequired") is False:
                raise SecurityError(409, "This payment validation order requires no fulfillment.", "no_fulfillment_order")
            current = order.get("status", "placed")
            if requested not in transitions.get(current, set()):
                raise SecurityError(409, "Invalid order status transition.", "invalid_transition")
            cancellation_request = order.get("cancellationRequest")
            if (
                isinstance(cancellation_request, dict)
                and cancellation_request.get("status") == "requested"
                and requested != "cancelled"
            ):
                raise SecurityError(
                    409,
                    "A customer cancellation request is pending. Resolve the cancellation before continuing fulfillment.",
                    "cancellation_pending",
                )
            refund_request = order.get("refundRequest")
            if (
                isinstance(refund_request, dict)
                and refund_request.get("status") in {"submitting", "submitted", "processing", "uncertain", "failed"}
                and requested != "cancelled"
            ):
                raise SecurityError(
                    409,
                    "A cancellation refund is unresolved. Resolve the refund before continuing fulfillment.",
                    "refund_pending",
                )
            cancellation_reason = None
            if requested == "cancelled":
                if not isinstance(reason, str) or not 3 <= len(reason.strip()) <= 500:
                    raise SecurityError(
                        400,
                        "A cancellation reason is required.",
                        "cancellation_reason_required",
                    )
                cancellation_reason = " ".join(reason.strip().split())
            current_time = utc_now()
            now = iso(current_time)
            inventory_released = False

            if (
                order.get("paymentStatus") == "refunded"
                and requested != "cancelled"
            ):
                raise SecurityError(
                    409,
                    "A fully refunded order cannot continue fulfillment.",
                    "refunded_order",
                )

            if current == "payment_review_required" and requested == "placed":
                payment_verified_for_fulfillment = (
                    order.get("paymentStatus") == "paid"
                    or (
                        order.get("paymentMethod") == "cod"
                        and order.get("codAdvancePaid") is True
                    )
                )
                if not payment_verified_for_fulfillment:
                    raise SecurityError(409, "The payment state must be reconciled before fulfillment.", "payment_state_unresolved")
                try:
                    self.payments._decrement_inventory(
                        state,
                        order.get("items", []),
                        inventory_alerts=inventory_alerts,
                    )
                except Exception as error:
                    if getattr(error, "code", None) == "stock_changed":
                        raise SecurityError(409, "Stock is still unavailable for this paid order.", "stock_changed") from None
                    raise
                order["inventoryCommitted"] = True
                order.pop("inventoryShortfall", None)
                order["status"] = "placed"
                order["updatedAt"] = now
                order.setdefault("statusHistory", []).append({"status": "placed", "timestamp": now, "note": "Paid order stock confirmed by local administrator"})
                self._resolve_order_alerts(state, order, {"inventory_shortfall_after_capture", "external_payment_inventory_shortfall"}, now)

            elif requested == "cancelled":
                if isinstance(order.get("externalPayment"), dict):
                    raise SecurityError(409, "Reconcile the external payment refund before cancelling this order.", "external_refund_required")
                if (
                    current == "out_for_delivery"
                    and isinstance(cancellation_request, dict)
                    and int(cancellation_request.get("feeDue", 0) or 0) > 0
                    and cancellation_request.get("feePaid") is not True
                ):
                    raise SecurityError(409, "Collect the Rs 50 after-dispatch cancellation fee before cancelling.", "cancellation_fee_required")
                cod_advance_nonrefundable = (
                    order.get("paymentMethod") == "cod"
                    and order.get("codAdvancePaid") is True
                    and current in {"packed", "out_for_delivery"}
                )
                captured_razorpay_payment = (
                    order.get("paymentMethod") in ("upi", "card")
                    or (
                        order.get("paymentMethod") == "cod"
                        and order.get("codAdvancePaid") is True
                    )
                )
                if (
                    captured_razorpay_payment
                    and not cod_advance_nonrefundable
                    and order.get("paymentStatus") != "refunded"
                ):
                    raise SecurityError(
                        409,
                        "A captured online payment must be fully refunded in Razorpay and confirmed by the signed refund.processed webhook before cancellation.",
                        "refund_required",
                    )
                try:
                    inventory_released = self.payments._release_inventory(state, order)
                except Exception as error:
                    if getattr(error, "code", None) == "inventory_release_failed":
                        raise SecurityError(409, "Inventory could not be released safely.", "inventory_release_failed") from None
                    raise
                order["status"] = "cancelled"
                order["updatedAt"] = now
                order["cancelledAt"] = now
                order["cancellationReason"] = cancellation_reason
                if isinstance(cancellation_request, dict):
                    cancellation_request.update({"status": "completed", "completedAt": now})
                if cod_advance_nonrefundable:
                    base_note = "Cash on Delivery order cancelled; Rs 50 COD booking amount retained after packing"
                elif captured_razorpay_payment:
                    base_note = "Cancelled after verified Razorpay refund"
                else:
                    base_note = "Cash on Delivery order cancelled"
                order.setdefault("statusHistory", []).append({
                    "status": "cancelled",
                    "timestamp": now,
                    "note": f"{base_note}. Reason: {cancellation_reason}",
                })
                self._resolve_order_alerts(
                    state,
                    order,
                    {
                        "inventory_shortfall_after_capture",
                        "refund.processed",
                        "refund.processed_review",
                    },
                    now,
                )
            else:
                order["status"] = requested
                order["updatedAt"] = now
                note = "Updated by local administrator"
                if requested == "delivered":
                    started = 0
                    for item in order.get("items", []) or []:
                        trial = item.get("tryAtHome") if isinstance(item, dict) else None
                        if isinstance(trial, dict) and trial.get("status") == "reserved":
                            minutes = int(trial.get("tryMinutes", 15) or 15)
                            trial["status"] = "active"
                            trial["startedAt"] = now
                            trial["deadlineAt"] = iso(current_time + timedelta(minutes=minutes))
                            started += 1
                    if started:
                        note = f"Delivered; Try at Home 15-minute selection window started for {started} item(s)"
                order.setdefault("statusHistory", []).append({"status": requested, "timestamp": now, "note": note})

            self.payments.store.save()
            result = dict(order)
        self.identity.record_action(
            admin_id,
            "order_status",
            "order",
            order_id,
            "success",
            {
                "from": current,
                "to": requested,
                "inventoryReleased": inventory_released,
                "cancellationReason": cancellation_reason,
            },
        )

        if inventory_alerts:
            _notify_inventory_alerts(inventory_alerts)

        if requested == "cancelled":
            try:
                grand_total = result.get("grandTotal")
                amount_text = (
                    f"?{grand_total}"
                    if isinstance(grand_total, (int, float))
                    and not isinstance(grand_total, bool)
                    else "-"
                )

                payment_method = str(
                    result.get("paymentMethod") or "-"
                ).upper()

                owner_notifier().send(
                    event="order_cancelled",
                    title="Vibe4You Order Cancelled",
                    message=(
                        f"Order: {order_id}\n"
                        f"Amount: {amount_text}\n"
                        f"Payment: {payment_method}\n"
                        f"Status: Cancelled\n"
                        f"Reason: {result.get('cancellationReason') or '-'}"
                    ),
                    priority=5,
                    tags=["no_entry_sign"],
                )

            except Exception:
                # Cancellation and audit are already durable.
                print(
                    "Vibe4You notification preparation failed "
                    "event=order_cancelled",
                    flush=True,
                )

        return result

    def transition_shop_product_request(
        self,
        admin_id: str,
        request_id: str,
        target_status: Any,
        reason: Any = None,
    ) -> dict[str, Any]:
        request = next(
            (item for item in self.shops.admin_list_product_change_requests(admin_id) if item["id"] == request_id),
            None,
        ) if self.shops is not None else None
        before_variants: dict[str, dict[str, Any]] = {}
        approving_edit = (
            isinstance(target_status, str)
            and target_status.strip().upper() == "APPROVED"
            and request is not None
            and request.get("action") == "EDIT"
        )
        if not approving_edit:
            return self.shops.admin_transition_product_change_request(
                admin_id, request_id, target_status, reason
            )

        self.payments.refresh_shop_products()
        # Inventory adjustment, checkout finalization, and order release all
        # use this same lock. Keep it from the authoritative revalidation
        # through catalogue/state synchronization so a retirement cannot race
        # with stock being restored after the snapshot.
        with self.payments.store.lock:
            product = self.payments.product_snapshot().get(request["productId"])
            live_inventory: dict[str, int] = {}
            if product:
                before_variants = {
                    item["id"]: dict(item) for item in product.get("variants", [])
                }
                live_inventory = {
                    item["id"]: self.payments._inventory(
                        self.payments.store.state, item
                    )
                    for item in product.get("variants", [])
                }
            result = self.shops.admin_transition_product_change_request(
                admin_id,
                request_id,
                target_status,
                reason,
                live_inventory=live_inventory,
            )
            if result.get("status") != "APPROVED":
                return result

            self.payments.refresh_shop_products()
            product = self.payments.product_snapshot().get(result["productId"])
            changed = False
            if product:
                inventory = self.payments.store.state["inventory"]
                for variant in product.get("variants", []):
                    old = before_variants.get(variant["id"])
                    if old is None and variant.get("active") is not False:
                        inventory[variant["id"]] = int(variant.get("stock", 0))
                        changed = True
                    elif (
                        old is not None
                        and old.get("active") is not False
                        and variant.get("active") is False
                    ):
                        # The workflow revalidated this value as zero while the
                        # inventory lock was held, so this cannot erase stock.
                        inventory[variant["id"]] = 0
                        changed = True
                if changed:
                    self.payments.store.save()
            return result

    def bulk_transition_shop_product_requests(
        self, admin_id: str, request_ids: Any, target_status: Any, reason: Any = None
    ) -> dict[str, Any]:
        if not isinstance(request_ids, list) or not request_ids or len(request_ids) > 100:
            raise SecurityError(400, "Select between 1 and 100 product requests.", "invalid_bulk_product_requests")
        ids = []
        for value in request_ids:
            if not isinstance(value, str) or not value.strip() or len(value) > 200:
                raise SecurityError(400, "Invalid product request selection.", "invalid_bulk_product_requests")
            clean = value.strip()
            if clean not in ids:
                ids.append(clean)
        if not isinstance(target_status, str):
            raise SecurityError(400, "Invalid product change status.", "invalid_product_change_status")
        target = target_status.strip().upper()
        if target not in {"UNDER_REVIEW", "APPROVED", "REJECTED"}:
            raise SecurityError(400, "Invalid bulk product change status.", "invalid_product_change_status")
        current = {item["id"]: item for item in self.shops.admin_list_product_change_requests(admin_id)}
        updated, failures = [], []
        catalog_changed = False
        for request_id in ids:
            item = current.get(request_id)
            if item is None:
                failures.append({"id": request_id, "error": "Product change request not found.", "code": "product_change_not_found"})
                continue
            try:
                if item.get("status") == "SUBMITTED" and target in {"APPROVED", "REJECTED"}:
                    self.shops.admin_transition_product_change_request(admin_id, request_id, "UNDER_REVIEW")
                changed_fields = {str(change.get("field") or "") for change in item.get("changeSummary", []) if isinstance(change, dict)}
                needs_inventory_revalidation = target == "APPROVED" and item.get("action") == "EDIT" and "Options and stock" in changed_fields
                if needs_inventory_revalidation:
                    result = self.transition_shop_product_request(admin_id, request_id, target, reason)
                else:
                    result = self.shops.admin_transition_product_change_request(admin_id, request_id, target, reason)
                    if target == "APPROVED":
                        catalog_changed = True
                updated.append(result)
            except SecurityError as error:
                failures.append({"id": request_id, "productName": item.get("productName") or item.get("productId"), "error": error.message, "code": error.code})
        if catalog_changed:
            self.payments.refresh_shop_products()
        return {"updated": updated, "failures": failures, "requested": len(ids)}

    def inventory(self, query: str = "", low_only: bool = False) -> list[dict[str, Any]]:
        self.payments.refresh_shop_products()
        needle = query.strip().casefold()[:100]
        result = []
        with self.payments.store.lock:
            for product in self.payments.products.values():
                for variant in product["variants"]:
                    stock = self.payments._inventory(self.payments.store.state, variant)
                    image_candidates = [variant.get("imageUrl")]
                    if isinstance(variant.get("images"), list): image_candidates.extend(variant["images"])
                    image_candidates.extend([product.get("thumbnail"), product.get("imageUrl")])
                    if isinstance(product.get("images"), list): image_candidates.extend(product["images"])
                    image_urls = list(dict.fromkeys(value for value in image_candidates if isinstance(value, str) and value.strip()))
                    record = {
                        "productId": product["id"], "productName": product["name"],
                        "variantId": variant["id"], "size": variant.get("size"),
                        "colour": variant.get("colourName") or variant.get("colour"), "stock": stock,
                        "brand": product.get("brand"), "category": product.get("category"),
                        "department": product.get("department"), "storeName": product.get("storeName"),
                        "storeId": product.get("vendorId"), "optionMode": product.get("optionMode"),
                        "imageUrl": image_urls[0] if image_urls else None, "imageUrls": image_urls,
                    }
                    searchable = " ".join(str(record.get(key) or "") for key in (
                        "productId", "productName", "variantId", "size", "colour",
                        "brand", "category", "department", "storeName",
                    )).casefold()
                    if needle and needle not in searchable:
                        continue
                    if low_only and stock > 5:
                        continue
                    result.append(record)
        return result

    def inventory_snapshot(self, admin_id: str, query: str = "", low_only: bool = False) -> dict[str, Any]:
        """Inventory rows plus every shop known to the private admin service.

        The shop selector must not be derived from product rows: a newly added
        shop can legitimately have no published product or stock yet.
        """
        applications = self.shops.admin_list_applications(admin_id)
        shops = [
            {"id": item["id"], "name": item["shopName"], "status": item["status"]}
            for item in applications
        ]
        return {"inventory": self.inventory(query, low_only), "shops": shops}

    def adjust_inventory(
        self,
        admin_id: str,
        variant_id: str,
        delta: Any,
    ) -> dict[str, Any]:
        self.payments.refresh_shop_products()
        if (
            isinstance(delta, bool)
            or not isinstance(delta, int)
            or delta == 0
            or not -10000 <= delta <= 10000
        ):
            raise SecurityError(
                400,
                "Inventory adjustment must be a non-zero whole number.",
                "invalid_inventory_adjustment",
            )

        variant = None
        product = None

        for item in self.payments.products.values():
            match = next(
                (
                    candidate
                    for candidate in item["variants"]
                    if candidate["id"] == variant_id
                ),
                None,
            )

            if match:
                variant, product = match, item
                break

        if variant is None or product is None:
            raise SecurityError(
                404,
                "Product variant not found.",
                "variant_not_found",
            )

        inventory_alert = None

        with self.payments.store.lock:
            before = self.payments._inventory(
                self.payments.store.state,
                variant,
            )

            after = before + delta

            if after < 0:
                raise SecurityError(
                    409,
                    "Inventory cannot become negative.",
                    "negative_inventory",
                )

            inventory_alert = (
                self.payments._inventory_alert_for_change(
                    product,
                    variant,
                    before,
                    after,
                )
            )

            self.payments.store.state["inventory"][
                variant_id
            ] = after

            self.payments.store.save()

        self.identity.record_action(
            admin_id,
            "inventory_adjustment",
            "product_variant",
            variant_id,
            "success",
            {
                "delta": delta,
                "before": before,
                "after": after,
            },
        )

        if inventory_alert is not None:
            _notify_inventory_alerts([inventory_alert])

        return {
            "productId": product["id"],
            "variantId": variant_id,
            "before": before,
            "after": after,
        }

    def system_health(self, backup_root: Path) -> dict[str, Any]:
        public_health: dict[str, Any]
        try:
            with urlopen("http://127.0.0.1:8080/api/health", timeout=3) as response:
                public_health = json.load(response)
        except Exception:
            public_health = {"status": "unavailable"}
        backups = sorted((path for path in backup_root.glob("*") if path.is_dir()), reverse=True) if backup_root.exists() else []
        return {
            "adminService": "ok", "database": self.identity.integrity(),
            "publicService": public_health, "paymentMode": self.payments.mode,
            "latestBackup": backups[0].name if backups else None,
        }


class AdminHandler(BaseHTTPRequestHandler):
    server_version = "Vibe4YouAdmin"
    application: AdminApplication
    asset_root: Path
    backup_root: Path

    def _headers(self, status: int, content_type: str, length: int, extra: list[tuple[str, str]] | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", SECURITY_POLICY)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.send_header("X-Frame-Options", "DENY")
        # Local launch/deploy probes use this to prove which process owns 8081.
        # Keep the process identity private even when Cloudflare Access proxies Admin.
        if (self.headers.get("Host") or "").lower() in {"127.0.0.1:8081", "localhost:8081"}:
            self.send_header("X-StyleDash-Process-Id", str(os.getpid()))
        for name, value in extra or []:
            self.send_header(name, value)
        self.end_headers()

    def _json(self, status: int, payload: dict[str, Any], cookies: list[str] | None = None) -> None:
        body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode()
        self._headers(status, "application/json; charset=utf-8", len(body), [("Set-Cookie", value) for value in cookies or []])
        self.wfile.write(body)

    def _error(self, error: SecurityError) -> None:
        self._json(error.status, {"success": False, "error": error.message, "code": error.code})

    def _host_allowed(self) -> bool:
        return self.headers.get("Host", "").casefold() in ALLOWED_HOSTS

    def _origin_allowed(self) -> bool:
        origin = self.headers.get("Origin")
        return not origin or origin.casefold() in ALLOWED_ORIGINS

    def _cookie(self, name: str) -> str | None:
        cookies = SimpleCookie()
        try:
            cookies.load(self.headers.get("Cookie", ""))
        except Exception:
            return None
        item = cookies.get(name)
        return item.value if item else None

    def _admin(self) -> tuple[dict[str, Any], Any]:
        return self.application.identity.authenticate(self._cookie(ADMIN_COOKIE))

    def _shops(self) -> ShopWorkflow:
        if self.application.shops is None:
            raise SecurityError(
                503, "Shop administration is unavailable.", "shop_service_unavailable"
            )
        return self.application.shops

    def _csrf(self) -> None:
        if not self._origin_allowed():
            raise SecurityError(403, "Administrator request origin is not allowed.", "admin_invalid_origin")
        self.application.identity.verify_csrf(self._cookie(ADMIN_COOKIE), self.headers.get("X-CSRF-Token"))

    def _body(self, max_bytes: int = MAX_BODY_BYTES) -> dict[str, Any]:
        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().casefold()
        if content_type != "application/json":
            raise SecurityError(415, "Content-Type must be application/json.", "invalid_content_type")
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            raise SecurityError(400, "Invalid request body.", "malformed_request") from None
        if length <= 0 or length > max_bytes:
            raise SecurityError(413, "Request body is too large.", "body_too_large")
        try:
            payload = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise SecurityError(400, "Malformed JSON request.", "malformed_request") from None
        if not isinstance(payload, dict):
            raise SecurityError(400, "A JSON object is required.", "malformed_request")
        return payload

    def _query(self) -> dict[str, list[str]]:
        return parse_qs(urlsplit(self.path).query, keep_blank_values=True)

    def _serve_asset(self, filename: str, content_type: str) -> None:
        path = self.asset_root / filename
        if not path.is_file():
            self._json(404, {"success": False, "error": "Not found.", "code": "not_found"})
            return
        body = path.read_bytes()
        self._headers(200, content_type, len(body))
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if not self._host_allowed():
            self._json(421, {"success": False, "error": "Invalid local host.", "code": "invalid_host"})
            return
        path = urlsplit(self.path).path
        try:
            if path in ("/", "/index.html"):
                self._serve_asset("index.html", "text/html; charset=utf-8"); return
            if path == "/admin.css":
                self._serve_asset("admin.css", "text/css; charset=utf-8"); return
            if path == "/leaflet.css":
                self._serve_asset("leaflet.css", "text/css; charset=utf-8"); return
            if path == "/admin-variants.css":
                self._serve_asset("admin-variants.css", "text/css; charset=utf-8"); return
            if path == "/leaflet.js":
                self._serve_asset("leaflet.js", "text/javascript; charset=utf-8"); return
            if path == "/admin.js":
                self._serve_asset("admin.js", "text/javascript; charset=utf-8"); return
            if path == "/delivery-zone-map.js":
                self._serve_asset("delivery-zone-map.js", "text/javascript; charset=utf-8"); return
            if path == "/api/admin/me":
                admin, _session = self._admin()
                self._json(200, {"success": True, "admin": admin, "csrfToken": self.application.identity.csrf_token(self._cookie(ADMIN_COOKIE) or "")}); return
            if path == "/api/admin/orders":
                self._admin(); query = self._query().get("q", [""])[0]
                self._json(200, {"success": True, "orders": self.application.list_orders(query)}); return
            if path == "/api/admin/external-payments":
                self._admin(); month = self._query().get("month", [""])[0]
                self._json(200, {"success": True, "report": self.application.external_payment_report(month)}); return
            if path == "/api/admin/billing-audit":
                self._admin(); month = self._query().get("month", [""])[0]
                require_billing_preview_mode()
                self._json(200, {"success": True, "report": self.application.billing_preview(month)}); return
            if path == "/api/admin/outside-delivery-requests":
                self._admin()
                self._json(200, {"success": True, "requests": self.application.list_outside_delivery_requests()}); return
            if path == "/api/admin/payment-alerts":
                self._admin(); self._json(200, {"success": True, "alerts": self.application.payment_alerts()}); return
            if path == "/api/admin/tax-classifications/review.csv":
                admin, _session=self._admin()
                products=self._shops().admin_list_published_products_for_tax(admin["id"])
                rates=self.application.tax_classifications.list_all()
                data=review_csv(products,rates)
                self._headers(200,"text/csv; charset=utf-8",len(data),[
                    ("Content-Disposition",'attachment; filename="vibe4you-gst-review.csv"'),
                    ("Cache-Control","private, no-store"),
                ])
                self.wfile.write(data);return
            if path == "/api/admin/tax-classifications/coverage":
                admin, _session=self._admin()
                products=self._shops().admin_list_published_products_for_tax(admin["id"])
                rates=self.application.tax_classifications.list_all()
                self._json(200,{"success":True,**coverage(products,rates),**suggestion_coverage(products)});return
            if path == "/api/admin/tax-classifications":
                self._admin()
                self._json(200,{"success":True,
                    "classifications":self.application.tax_classification_list()});return
            if path == "/api/admin/invoicing/status":
                self._admin()
                self._json(200, {"success":True, **self.application.invoice_readiness()}); return
            billing_pdf_match = re.fullmatch(r"/api/admin/billing-audit/(purchases|sales)\.pdf", path)
            if billing_pdf_match:
                self._admin()
                deny_financial_billing()
            if path.startswith("/api/admin/orders/") and path.endswith("/tax-invoice"):
                self._admin()
                order_id=unquote(path.removeprefix("/api/admin/orders/").removesuffix("/tax-invoice"))
                pdf=self.application.tax_invoice_pdf(order_id)
                safe_id=re.sub(r"[^A-Za-z0-9_-]+","-",order_id)[:80] or "order"
                self._headers(200,"application/pdf",len(pdf),[
                    ("Content-Disposition",f'attachment; filename="vibe4you-tax-invoice-{safe_id}.pdf"')
                ])
                self.wfile.write(pdf); return
            if path.startswith("/api/admin/orders/") and path.endswith("/receipt"):
                self._admin()
                order_id = unquote(path.removeprefix("/api/admin/orders/").removesuffix("/receipt"))
                pdf = self.application.receipt_pdf(order_id)
                safe_id = re.sub(r"[^A-Za-z0-9_-]+", "-", order_id)[:80] or "order"
                self._headers(
                    200, "application/pdf", len(pdf),
                    [("Content-Disposition", f'attachment; filename="vibe4you-receipt-{safe_id}.pdf"')],
                )
                self.wfile.write(pdf)
                return
            if path == "/api/admin/month-end":
                self._admin()
                month = (self._query().get("month") or [""])[0]
                self._json(200, {"success": True, **self.application.month_end_overview(month)}); return
            if path == "/api/admin/month-end/profit-export":
                self._admin()
                month = (self._query().get("month") or [""])[0]
                csv_bytes = self.application.month_end_profit_csv(month)
                self._headers(200, "text/csv; charset=utf-8", len(csv_bytes), [
                    ("Content-Disposition", f'attachment; filename="vibe4you-month-profit-{month}.csv"')
                ])
                self.wfile.write(csv_bytes); return
            if path == "/api/admin/month-end/export":
                admin, _session = self._admin()
                month = (self._query().get("month") or [""])[0]
                archive, size, filename, _summary = self.application.month_end_export(admin["id"], month)
                try:
                    self._headers(200, "application/zip", size, [("Content-Disposition", f'attachment; filename="{filename}"')])
                    while True:
                        chunk = archive.read(1024 * 1024)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                finally:
                    archive.close()
                return
            seller_bill_file = re.fullmatch(r"/api/admin/orders/([^/]+)/seller-bills/([^/]+)", path)
            if seller_bill_file:
                self._admin()
                content, content_type, file_name = self.application.seller_bill_file(
                    unquote(seller_bill_file.group(1)), seller_bill_file.group(2)
                )
                safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", file_name)[:100] or "seller-bill"
                self._headers(200, content_type, len(content), [("Content-Disposition", f'attachment; filename="{safe_name}"')])
                self.wfile.write(content)
                return
            supplier_bill_match = re.fullmatch(
                r"/api/admin/orders/([^/]+)/supplier-bills/([^/]+)", path
            )
            if supplier_bill_match:
                self._admin()
                deny_financial_billing()
            if path.startswith("/api/admin/orders/"):
                self._admin(); order_id = unquote(path.removeprefix("/api/admin/orders/"))
                self._json(200, {"success": True, "order": self.application.get_order(order_id)}); return
            if path == "/api/admin/vendors":
                admin, _session = self._admin()
                self._json(200, {"success": True, "applications": self._shops().admin_list_applications(admin["id"])}); return
            if path == "/api/admin/shop-products":
                admin, _session = self._admin()
                query = self._query()
                try:
                    page = int(query.get("page", ["1"])[0])
                    page_size = int(query.get("pageSize", ["25"])[0])
                except ValueError:
                    raise SecurityError(400, "Invalid pagination parameters.", "invalid_pagination") from None
                if page < 1 or page_size not in (10, 25, 50, 100):
                    raise SecurityError(400, "Invalid pagination parameters.", "invalid_pagination")
                result = self._shops().admin_paginate_products(
                    admin["id"], page=page, page_size=page_size,
                    search=query.get("q", [""])[0],
                    shop=query.get("shop", ["all"])[0],
                    status=query.get("status", ["all"])[0],
                    category=query.get("category", ["all"])[0],
                )
                self._json(200, {"success": True, **result}); return
            if path == "/api/admin/shop-product-requests":
                admin, _session = self._admin()
                self._json(200, {"success": True, "requests": self._shops().admin_list_product_change_requests(admin["id"])}); return
            if path.startswith("/api/admin/review-photo/"):
                admin, _session = self._admin()
                if self.application.reviews is None:
                    raise SecurityError(503, "Reviews unavailable.", "reviews_unavailable")
                review_id = unquote(path.removeprefix("/api/admin/review-photo/"))
                blob = self.application.reviews.review_photo(review_id, admin["id"])
                self._headers(200, "image/webp", len(blob),
                              [("X-Content-Type-Options", "nosniff"),
                               ("Content-Security-Policy", "default-src 'none'")])
                self.wfile.write(blob)
                return
            if path == "/api/admin/product-reviews":
                admin, _session = self._admin()
                self._json(200, {"success": True, "reviews": self.application.list_product_reviews(admin["id"])})
                return
            if path == "/api/admin/store-reviews":
                admin, _session = self._admin()
                self._json(200, {"success": True, "reviews": self.application.list_store_reviews(admin["id"])}); return
            if path == "/api/admin/inventory":
                admin, _session = self._admin(); query = self._query(); needle = query.get("q", [""])[0]; low = query.get("low", ["0"])[0] == "1"
                self._json(200, {"success": True, **self.application.inventory_snapshot(admin["id"], needle, low)}); return
            if path == "/api/admin/customers":
                self._admin()
                parameters = self._query()
                query = parameters.get("q", [""])[0]
                try:
                    page = int(parameters.get("page", ["1"])[0])
                    page_size = int(parameters.get("page_size", ["50"])[0])
                except (ValueError, TypeError):
                    raise SecurityError(
                        400, "Invalid customer page or page size.",
                        "invalid_customer_pagination",
                    ) from None
                status = parameters.get("status", ["all"])[0]
                results = self.application.identity.customers_page(
                    query, page, page_size, status
                )
                self._json(200, {"success": True, **results}); return
            if path == "/api/admin/audit":
                self._admin(); self._json(200, {"success": True, "audit": self.application.identity.audit()}); return
            if path == "/api/admin/system":
                self._admin(); self._json(200, {"success": True, "system": self.application.system_health(self.backup_root)}); return
            if path == "/api/admin/delivery-zone":
                self._admin(); result = self.application.delivery_zone_configuration()
                self._json(200, {"success": True, **result}); return
            if path.startswith("/media/product-images/"):
                self._admin()
                if not PRODUCT_MEDIA_PATH_PATTERN.fullmatch(path):
                    self._json(404, {"success": False, "error": "Image not found.", "code": "not_found"}); return
                root = self.application.product_image_directory.resolve()
                image = (root / Path(path).name).resolve()
                if image.parent != root or not image.is_file():
                    self._json(404, {"success": False, "error": "Image not found.", "code": "not_found"}); return
                content_type = {".webp":"image/webp",".jpg":"image/jpeg",".png":"image/png"}.get(image.suffix.lower())
                if content_type is None:
                    self._json(404, {"success": False, "error": "Image not found.", "code": "not_found"}); return
                body=image.read_bytes(); self._headers(200, content_type, len(body), [("Cache-Control","private, no-store")]); self.wfile.write(body); return
            self._json(404, {"success": False, "error": "Not found.", "code": "not_found"})
        except SecurityError as error:
            self._error(error)
        except Exception:
            self._json(500, {"success": False, "error": "The local admin service could not process this request.", "code": "internal_error"})

    def do_POST(self) -> None:  # noqa: N802
        if not self._host_allowed() or not self._origin_allowed():
            self._json(403, {"success": False, "error": "Local administrator request rejected.", "code": "admin_request_rejected"}); return
        path = urlsplit(self.path).path
        try:
            if path == "/api/admin/login":
                challenge = self.application.identity.begin_login(self._body(), self.client_address[0])
                self._json(200, {"success": True, "requiresTotp": True}, [self.application.identity.challenge_cookie(challenge)]); return
            if path == "/api/admin/totp":
                admin, raw, csrf = self.application.identity.verify_totp(self._cookie(CHALLENGE_COOKIE), self._body().get("code"), self.client_address[0])
                self._json(200, {"success": True, "admin": admin, "csrfToken": csrf}, [self.application.identity.session_cookie(raw), self.application.identity.clear_cookie(CHALLENGE_COOKIE)]); return
            if path == "/api/admin/logout":
                self._admin(); self._csrf(); self.application.identity.logout(self._cookie(ADMIN_COOKIE))
                self._json(200, {"success": True}, [self.application.identity.clear_cookie(ADMIN_COOKIE)]); return
            profit_entry = re.fullmatch(r"/api/admin/orders/([^/]+)/profit", path)
            if profit_entry:
                admin, _session = self._admin(); self._csrf()
                saved = self.application.save_order_profit(
                    admin["id"], unquote(profit_entry.group(1)), self._body()
                )
                self._json(200, {"success": True, **saved}); return
            seller_bill_upload = re.fullmatch(r"/api/admin/orders/([^/]+)/seller-bills", path)
            if seller_bill_upload:
                admin, _session = self._admin(); self._csrf()
                payload = self._body(ORDER_DOCUMENT_REQUEST_MAX_BYTES)
                bill = self.application.upload_seller_bill(admin["id"], unquote(seller_bill_upload.group(1)), payload)
                self._json(201, {"success": True, "bill": bill}); return
            seller_bill_void = re.fullmatch(r"/api/admin/orders/([^/]+)/seller-bills/([^/]+)/void", path)
            if seller_bill_void:
                admin, _session = self._admin(); self._csrf()
                result = self.application.void_seller_bill(
                    admin["id"], unquote(seller_bill_void.group(1)), seller_bill_void.group(2), self._body()
                )
                self._json(200, {"success": True, **result}); return
            if path == "/api/admin/manual-orders":
                admin, _session = self._admin(); self._csrf()
                result = self.application.create_manual_order(admin["id"], self._body())
                self._json(201, {"success": True, **result}); return
            supplier_bill_match = re.fullmatch(
                r"/api/admin/orders/([^/]+)/supplier-bills", path
            )
            if supplier_bill_match:
                self._admin()
                self._csrf()
                deny_financial_billing()
            if path == "/api/admin/tax-classifications/apply-verified-watches":
                admin, _session=self._admin(); self._csrf()
                payload=self._body()
                products=self._shops().admin_list_published_products_for_tax(admin["id"])
                outcome=self.application.approve_source_backed_watch_rates(
                    admin["id"],payload.get("confirmation"),products
                )
                self._json(201,{"success":True,**outcome});return
            if path == "/api/admin/tax-classifications/bulk":
                admin, _session=self._admin(); self._csrf()
                payload=self._body(BULK_PRODUCT_REQUEST_MAX_BYTES)
                products=self._shops().admin_list_published_products_for_tax(admin["id"])
                result=self.application.approve_tax_csv(admin["id"],payload,products)
                self._json(201,{"success":True,**result});return
            if path == "/api/admin/tax-classifications":
                admin, _session=self._admin(); self._csrf()
                classification=self.application.approve_tax_classification(admin["id"],self._body())
                self._json(201,{"success":True,"classification":classification});return
            if path.startswith("/api/admin/orders/") and path.endswith("/tax-invoice"):
                admin, _session=self._admin(); self._csrf()
                order_id=unquote(path.removeprefix("/api/admin/orders/").removesuffix("/tax-invoice"))
                result=self.application.issue_tax_invoice(admin["id"],order_id)
                self._json(201,{"success":True,**result});return
            if path == "/api/admin/customers":
                admin, _session = self._admin(); self._csrf()
                result = self.application.identity.create_customer_account(admin["id"], self._body())
                self._json(201, {"success": True, "customer": result}); return
            if path == "/api/admin/vendors":
                admin, _session = self._admin(); self._csrf(); payload = self._body()
                owner_user_id = payload.pop("ownerUserId", None)
                if not isinstance(owner_user_id, str) or not owner_user_id:
                    raise SecurityError(400, "Choose a store-owner account.", "invalid_customer")
                for field, label in (("bannerImage", "store cover"), ("logoImage", "store logo")):
                    value = payload.get(field)
                    if value in (None, ""):
                        continue
                    if not isinstance(value, str) or not PRODUCT_MEDIA_PATH_PATTERN.fullmatch(value):
                        raise SecurityError(400, f"Upload a valid {label} image.", "invalid_store_branding")
                    if not (self.application.product_image_directory / Path(value).name).is_file():
                        raise SecurityError(400, f"Upload a valid {label} image.", "invalid_store_branding")
                result = self._shops().admin_create_application(admin["id"], owner_user_id, payload)
                self._json(201, {"success": True, "application": result}); return
            if path == "/api/admin/product-images":
                self._admin(); self._csrf()
                result = self.application.store_product_image(self._body(PRODUCT_IMAGE_REQUEST_MAX_BYTES))
                self._json(201, {"success": True, "image": result}); return
            if path == "/api/admin/shop-products/bulk":
                admin, _session = self._admin(); self._csrf(); payload = self._body(BULK_PRODUCT_REQUEST_MAX_BYTES)
                application_id = payload.get("applicationId")
                if not isinstance(application_id, str) or not application_id:
                    raise SecurityError(400, "Choose a local store.", "vendor_application_not_found")
                if "csvText" in payload:
                    products = parse_admin_product_csv(payload.get("csvText"), payload.get("images"), self.application.product_image_directory)
                else:
                    products = payload.get("products")
                    if isinstance(products, list):
                        for row_number, product in enumerate(products, 1):
                            require_existing_admin_product_media(product, self.application.product_image_directory, row_number)
                result = self._shops().admin_bulk_create_products(admin["id"], application_id, products)
                self._json(201, {"success": True, "products": result, "created": len(result)}); return
            if path == "/api/admin/shop-products":
                admin, _session = self._admin(); self._csrf(); payload = self._body()
                application_id = payload.pop("applicationId", None)
                if not isinstance(application_id, str) or not application_id:
                    raise SecurityError(400, "Choose a local store.", "vendor_application_not_found")
                require_existing_admin_product_media(payload, self.application.product_image_directory)
                result = self._shops().admin_create_product(admin["id"], application_id, payload)
                self._json(201, {"success": True, "product": result}); return
            self._json(404, {"success": False, "error": "Not found.", "code": "not_found"})
        except SecurityError as error:
            self._error(error)
        except Exception:
            self._json(500, {"success": False, "error": "The local admin service could not process this request.", "code": "internal_error"})

    def do_PATCH(self) -> None:  # noqa: N802
        if not self._host_allowed():
            self._json(421, {"success": False, "error": "Invalid local host.", "code": "invalid_host"}); return
        path = urlsplit(self.path).path
        try:
            admin, _session = self._admin(); self._csrf(); payload = self._body()
            if path == "/api/admin/delivery-zone":
                result = self.application.replace_delivery_zone_configuration(admin["id"], payload)
                self._json(200, {"success": True, **result}); return
            outside_delivery_match = re.fullmatch(r"/api/admin/outside-delivery-requests/([^/]+)/(quote|reject|external-payment)", path)
            if outside_delivery_match:
                request_id, action = (unquote(value) for value in outside_delivery_match.groups())
                if action == "quote":
                    result = self.application.quote_outside_delivery_request(admin["id"], request_id, payload)
                elif action == "external-payment":
                    payment = self.application.confirm_external_delivery_payment(admin["id"], request_id, payload)
                    self._json(200, {"success": True, **payment}); return
                else:
                    result = self.application.reject_outside_delivery_request(admin["id"], request_id, payload)
                self._json(200, {"success": True, "request": result}); return
            manual_payment_match = re.fullmatch(r"/api/admin/orders/([^/]+)/external-payment", path)
            if manual_payment_match:
                order_id = unquote(manual_payment_match.group(1))
                result = self.application.confirm_existing_order_payment(admin["id"], order_id, payload)
                self._json(200, {"success": True, **result}); return
            if path.startswith("/api/admin/orders/") and path.endswith("/payment"):
                order_id = unquote(path.removeprefix("/api/admin/orders/").removesuffix("/payment"))
                result = self.application.mark_cod_paid(admin["id"], order_id, payload.get("collectionMethod"))
                self._json(200, {"success": True, "order": result}); return
            if path.startswith("/api/admin/orders/") and path.endswith("/cancellation-fee"):
                order_id = unquote(path.removeprefix("/api/admin/orders/").removesuffix("/cancellation-fee"))
                result = self.application.mark_cancellation_fee_paid(admin["id"], order_id, payload.get("collectionMethod"))
                self._json(200, {"success": True, "order": result}); return
            exchange_match = re.fullmatch(r"/api/admin/orders/([^/]+)/exchanges/([^/]+)/(fee|status)", path)
            if exchange_match:
                order_id, exchange_id, action = (unquote(value) for value in exchange_match.groups())
                if action == "fee":
                    result = self.application.mark_exchange_fee_paid(admin["id"], order_id, exchange_id, payload.get("collectionMethod"))
                else:
                    result = self.application.update_exchange_status(admin["id"], order_id, exchange_id, payload.get("status"))
                self._json(200, {"success": True, "order": result}); return
            if path.startswith("/api/admin/orders/") and path.endswith("/refund-cancel"):
                order_id = unquote(path.removeprefix("/api/admin/orders/").removesuffix("/refund-cancel"))
                result = self.application.refund_and_cancel_order(
                    admin["id"], order_id, payload.get("reason")
                )
                self._json(200, {"success": True, **result}); return
            tracking_match = re.fullmatch(r"/api/admin/orders/([^/]+)/tracking", path)
            if tracking_match:
                order_id = unquote(tracking_match.group(1))
                result = self.application.update_order_tracking(admin["id"], order_id, payload.get("trackingId"))
                self._json(200, {"success": True, "order": result}); return
            if path.startswith("/api/admin/orders/") and path.endswith("/status"):
                order_id = unquote(path.removeprefix("/api/admin/orders/").removesuffix("/status"))
                result = self.application.update_order_status(
                    admin["id"], order_id, payload.get("status"), payload.get("reason")
                )
                self._json(200, {"success": True, "order": result}); return
            if path.startswith("/api/admin/orders/") and path.endswith("/try-at-home-late-fee"):
                order_id = unquote(path.removeprefix("/api/admin/orders/").removesuffix("/try-at-home-late-fee"))
                result = self.application.mark_try_at_home_late_fee_paid(admin["id"], order_id, payload.get("collectionMethod"))
                self._json(200, {"success": True, "order": result}); return
            if path.startswith("/api/admin/vendors/") and path.endswith("/details"):
                application_id = unquote(path.removeprefix("/api/admin/vendors/").removesuffix("/details"))
                for field, label in (("bannerImage", "store cover"), ("logoImage", "store logo")):
                    value = payload.get(field)
                    if value in (None, ""):
                        continue
                    if not isinstance(value, str) or not PRODUCT_MEDIA_PATH_PATTERN.fullmatch(value):
                        raise SecurityError(400, f"Upload a valid {label} image.", "invalid_store_branding")
                    if not (self.application.product_image_directory / Path(value).name).is_file():
                        raise SecurityError(400, f"Upload a valid {label} image.", "invalid_store_branding")
                result = self._shops().admin_update_application(admin["id"], application_id, payload)
                self._json(200, {"success": True, "application": result}); return
            if path.startswith("/api/admin/vendors/"):
                application_id = unquote(path.removeprefix("/api/admin/vendors/"))
                result = self._shops().admin_transition_application(
                    admin["id"], application_id, payload.get("status"), payload.get("reason")
                )
                self._json(200, {"success": True, "application": result}); return
            if path == "/api/admin/shop-product-requests/bulk":
                result = self.application.bulk_transition_shop_product_requests(
                    admin["id"], payload.get("ids"), payload.get("status"), payload.get("reason")
                )
                self._json(200, {"success": True, **result}); return
            if path.startswith("/api/admin/shop-product-requests/"):
                request_id = unquote(path.removeprefix("/api/admin/shop-product-requests/"))
                result = self.application.transition_shop_product_request(
                    admin["id"], request_id, payload.get("status"), payload.get("reason")
                )
                self._json(200, {"success": True, "request": result}); return
            if path == "/api/admin/shop-products/bulk-commission":
                if set(payload) != {"ids", "commissionBasisPoints"}:
                    raise SecurityError(
                        400, "Supply only ids and commissionBasisPoints.",
                        "invalid_product_commission",
                    )
                result = self._shops().admin_bulk_set_product_commission(
                    admin["id"], payload["ids"], payload["commissionBasisPoints"]
                )
                self._json(200, {"success": True, **result}); return
            commission_match = re.fullmatch(r"/api/admin/shop-products/([^/]+)/commission", path)
            if commission_match:
                if set(payload) != {"commissionBasisPoints"}:
                    raise SecurityError(
                        400, "Supply only commissionBasisPoints (integer or null).",
                        "invalid_product_commission",
                    )
                product_id = unquote(commission_match.group(1))
                result = self._shops().admin_set_product_commission(
                    admin["id"], product_id, payload["commissionBasisPoints"]
                )
                self._json(200, {"success": True, "product": result}); return
            if path == "/api/admin/shop-products/bulk-features":
                if not isinstance(payload, dict) or set(payload) != {"ids", "feature", "enabled"}:
                    raise SecurityError(
                        400, "Supply ids, feature and enabled only.", "invalid_bulk_product_feature"
                    )
                result = self._shops().admin_bulk_set_product_feature(
                    admin["id"], payload["ids"], payload["feature"], payload["enabled"]
                )
                self._json(200, {"success": True, **result}); return
            if path.startswith("/api/admin/shop-products/") and path.endswith("/details"):
                product_id = unquote(path.removeprefix("/api/admin/shop-products/").removesuffix("/details"))
                require_existing_admin_product_media(payload, self.application.product_image_directory)
                result = self._shops().admin_update_product(admin["id"], product_id, payload)
                self._json(200, {"success": True, "product": result}); return
            product_review_match = re.fullmatch(r"/api/admin/product-reviews/([^/]+)", path)
            if product_review_match:
                review_id = unquote(product_review_match.group(1))
                result = self.application.moderate_product_review(admin["id"], review_id, payload.get("status"))
                self._json(200, {"success": True, "review": result})
                return
            review_match = re.fullmatch(r"/api/admin/store-reviews/([^/]+)", path)
            if review_match:
                review_id = unquote(review_match.group(1))
                result = self.application.moderate_store_review(admin["id"], review_id, payload.get("status"))
                self._json(200, {"success": True, "review": result}); return
            if path.startswith("/api/admin/customers/") and path.endswith("/password"):
                user_id = unquote(path.removeprefix("/api/admin/customers/").removesuffix("/password"))
                result = self.application.identity.set_customer_password(admin["id"], user_id, payload.get("password"))
                self._json(200, {"success": True, "customer": result}); return
            if path == "/api/admin/shop-products/manage":
                result = self._shops().admin_bulk_manage_products(
                    admin["id"], payload.get("ids"), payload.get("action")
                )
                self.application.payments.refresh_shop_products()
                self._json(200, {"success": True, **result}); return
            if path.startswith("/api/admin/shop-products/"):
                product_id = unquote(path.removeprefix("/api/admin/shop-products/"))
                result = self._shops().admin_transition_product(
                    admin["id"], product_id, payload.get("status"), payload.get("reason")
                )
                self._json(200, {"success": True, "product": result}); return
            if path.startswith("/api/admin/inventory/"):
                variant_id = unquote(path.removeprefix("/api/admin/inventory/"))
                result = self.application.adjust_inventory(admin["id"], variant_id, payload.get("delta"))
                self._json(200, {"success": True, "inventory": result}); return
            if path.startswith("/api/admin/customers/"):
                user_id = unquote(path.removeprefix("/api/admin/customers/"))
                if not isinstance(payload.get("active"), bool):
                    raise SecurityError(400, "Customer active state must be true or false.", "invalid_customer_status")
                result = self.application.identity.set_customer_active(admin["id"], user_id, payload["active"])
                self._json(200, {"success": True, "customer": result}); return
            self._json(404, {"success": False, "error": "Not found.", "code": "not_found"})
        except SecurityError as error:
            self._error(error)
        except Exception:
            self._json(500, {"success": False, "error": "The local admin service could not process this request.", "code": "internal_error"})

    def do_PUT(self) -> None:  # noqa: N802
        self._json(405, {"success": False, "error": "Method not allowed.", "code": "method_not_allowed"})

    do_DELETE = do_PUT

    def log_message(self, format: str, *args: Any) -> None:
        super().log_message(format, *args)


def create_admin_server(
    bind: str, port: int, database: Path, encryption_key: str, catalog: Path,
    settings: Path, data_dir: Path, asset_root: Path, backup_root: Path,
) -> ThreadingHTTPServer:
    if bind not in ("127.0.0.1", "::1"):
        raise RuntimeError("The administrator service must bind to loopback only")
    application = AdminApplication(database, encryption_key, catalog, settings, data_dir)
    handler = type("ConfiguredAdminHandler", (AdminHandler,), {"application": application, "asset_root": asset_root, "backup_root": backup_root})
    return ThreadingHTTPServer((bind, port), handler)


def main() -> None:
    home = Path.home()
    parser = argparse.ArgumentParser()
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8081)
    parser.add_argument("--database", default=os.environ.get("STYLEDASH_DATABASE_PATH", home / ".local/share/styledash/styledash.db"))
    parser.add_argument("--catalog", default=os.environ.get("STYLEDASH_CATALOG_PATH", home / ".local/share/styledash/catalog.json"))
    parser.add_argument("--settings", default=os.environ.get("STYLEDASH_SETTINGS_PATH", home / ".local/share/styledash/settings.json"))
    parser.add_argument("--data-dir", default=os.environ.get("STYLEDASH_DATA_DIR", home / ".local/share/styledash/runtime"))
    parser.add_argument("--assets", default=Path(__file__).resolve().parent / "admin")
    args = parser.parse_args()
    key = os.environ.get("STYLEDASH_TOTP_ENCRYPTION_KEY", "")
    if not key:
        raise SystemExit("STYLEDASH_TOTP_ENCRYPTION_KEY is required")
    server = create_admin_server(
        args.bind, args.port, Path(args.database).resolve(), key, Path(args.catalog).resolve(),
        Path(args.settings).resolve(), Path(args.data_dir).resolve(), Path(args.assets).resolve(),
        home / ".local/share/styledash/backups",
    )
    print(f"Vibe4You local administrator service listening on {args.bind}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
