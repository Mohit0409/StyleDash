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
import sqlite3
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit
from urllib.request import urlopen

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
    from styledash_notify import owner_notifier
except ModuleNotFoundError:
    from scripts.styledash_notify import owner_notifier


MAX_BODY_BYTES = 64 * 1024
PRODUCT_IMAGE_REQUEST_MAX_BYTES = 700 * 1024
BULK_PRODUCT_REQUEST_MAX_BYTES = 1024 * 1024
ALLOWED_HOSTS = {"127.0.0.1:8081", "localhost:8081"}
ALLOWED_ORIGINS = {"http://127.0.0.1:8081", "http://localhost:8081"}
SECURITY_POLICY = (
    "default-src 'self'; base-uri 'none'; object-src 'none'; frame-ancestors 'none'; "
    "form-action 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "connect-src 'self'"
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
    if not isinstance(image_map, dict) or len(image_map) > 100:
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
        image_file = values.get("imageFile", "")
        if image_file:
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
            image_urls.insert(0, mapped_path)
        if not image_urls:
            _import_error(row_number, "At least one product image is required.")
        product = {
            "name": name, "description": values.get("description", ""), "brand": values.get("brand") or None,
            "department": values.get("department", ""), "category": values.get("category", ""),
            "subcategory": values.get("subcategory") or None, "deliveryType": values.get("deliveryType") or "normal",
            "pricePaise": round(price * 100), "originalPricePaise": round(original * 100),
            "variants": _bulk_variants(values.get("variants", ""), row_number),
            "colourName": values.get("colourName", ""), "colourHex": values.get("colourHex") or None,
            "imageUrls": image_urls, "attributes": {},
        }
        require_existing_admin_product_media(product, product_image_directory, row_number)
        products.append(product)
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
        probe = sqlite3.connect(database)
        try:
            has_customers = probe.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='users'"
            ).fetchone() is not None
        finally:
            probe.close()
        self.shops = ShopWorkflow(database) if has_customers else None
        self._store_product_image_payload = public.store_product_image_payload
        self.product_image_directory = database.parent / "product-images"
        self.payments = public.PaymentService(
            catalog, settings, data_dir, key_id="", key_secret="", webhook_secret="",
            mode=os.environ.get("RAZORPAY_MODE", "test"), gateway=None,
            shop_workflow=self.shops,
        )

    def store_product_image(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._store_product_image_payload(self.product_image_directory, payload)

    def list_orders(self, query: str = "") -> list[dict[str, Any]]:
        needle = query.strip().casefold()[:100]
        with self.payments.store.lock:
            orders = list(self.payments.store.state["orders"].values())
            if needle:
                orders = [order for order in orders if needle in str(order.get("id", "")).casefold()]
            selected = [dict(order) for order in sorted(orders, key=lambda item: item.get("createdAt", ""), reverse=True)[:250]]
        return [self.payments.order_for_display(order) for order in selected]

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
        return self.payments.order_for_display(selected)

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
            order["updatedAt"] = now
            self.payments.store.save()
            result = dict(order)
        self.identity.record_action(admin_id, "cod_payment_marked_paid", "order", order_id, "success", {
            "collectionMethod": result["paymentCollectionMethod"], "paymentCollectedAt": result["paymentCollectedAt"]
        })
        return self.payments.order_for_display(result)

    def update_order_status(
        self, admin_id: str, order_id: str, requested: Any, reason: Any = None
    ) -> dict[str, Any]:
        transitions = {
            "payment_pending": {"cancelled"},
            "payment_review_required": {"placed", "cancelled"},
            "placed": {"confirmed", "cancelled"},
            "confirmed": {"preparing", "packed", "cancelled"},
            "preparing": {"out_for_delivery", "cancelled"},
            "packed": {"out_for_delivery"},
            "out_for_delivery": {"delivered"},
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
            cancellation_reason = None
            if requested == "cancelled":
                if not isinstance(reason, str) or not 3 <= len(reason.strip()) <= 500:
                    raise SecurityError(
                        400,
                        "A cancellation reason is required.",
                        "cancellation_reason_required",
                    )
                cancellation_reason = " ".join(reason.strip().split())
            now = iso(utc_now())
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
                if order.get("paymentStatus") != "paid":
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
                self._resolve_order_alerts(state, order, {"inventory_shortfall_after_capture"}, now)

            elif requested == "cancelled":
                online = order.get("paymentMethod") in ("upi", "card")
                if online and order.get("paymentStatus") != "refunded":
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
                base_note = "Cancelled after verified Razorpay refund" if online else "Cash on Delivery order cancelled"
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
                order.setdefault("statusHistory", []).append({"status": requested, "timestamp": now, "note": "Updated by local administrator"})

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

    def inventory(self, query: str = "", low_only: bool = False) -> list[dict[str, Any]]:
        self.payments.refresh_shop_products()
        needle = query.strip().casefold()[:100]
        result = []
        with self.payments.store.lock:
            for product in self.payments.products.values():
                for variant in product["variants"]:
                    stock = self.payments._inventory(self.payments.store.state, variant)
                    record = {
                        "productId": product["id"], "productName": product["name"],
                        "variantId": variant["id"], "size": variant.get("size"),
                        "colour": variant.get("colour"), "stock": stock,
                    }
                    searchable = f"{record['productId']} {record['productName']} {record['variantId']}".casefold()
                    if needle and needle not in searchable:
                        continue
                    if low_only and stock > 5:
                        continue
                    result.append(record)
        return result[:500]

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
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.send_header("X-Frame-Options", "DENY")
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
            if path == "/admin.js":
                self._serve_asset("admin.js", "text/javascript; charset=utf-8"); return
            if path == "/api/admin/me":
                admin, _session = self._admin()
                self._json(200, {"success": True, "admin": admin, "csrfToken": self.application.identity.csrf_token(self._cookie(ADMIN_COOKIE) or "")}); return
            if path == "/api/admin/orders":
                self._admin(); query = self._query().get("q", [""])[0]
                self._json(200, {"success": True, "orders": self.application.list_orders(query)}); return
            if path == "/api/admin/payment-alerts":
                self._admin(); self._json(200, {"success": True, "alerts": self.application.payment_alerts()}); return
            if path.startswith("/api/admin/orders/"):
                self._admin(); order_id = unquote(path.removeprefix("/api/admin/orders/"))
                self._json(200, {"success": True, "order": self.application.get_order(order_id)}); return
            if path == "/api/admin/vendors":
                admin, _session = self._admin()
                self._json(200, {"success": True, "applications": self._shops().admin_list_applications(admin["id"])}); return
            if path == "/api/admin/shop-products":
                admin, _session = self._admin()
                self._json(200, {"success": True, "products": self._shops().admin_list_products(admin["id"])}); return
            if path == "/api/admin/shop-product-requests":
                admin, _session = self._admin()
                self._json(200, {"success": True, "requests": self._shops().admin_list_product_change_requests(admin["id"])}); return
            if path == "/api/admin/inventory":
                self._admin(); query = self._query(); needle = query.get("q", [""])[0]; low = query.get("low", ["0"])[0] == "1"
                self._json(200, {"success": True, "inventory": self.application.inventory(needle, low)}); return
            if path == "/api/admin/customers":
                self._admin(); query = self._query().get("q", [""])[0]
                self._json(200, {"success": True, "customers": self.application.identity.customers(query)}); return
            if path == "/api/admin/audit":
                self._admin(); self._json(200, {"success": True, "audit": self.application.identity.audit()}); return
            if path == "/api/admin/system":
                self._admin(); self._json(200, {"success": True, "system": self.application.system_health(self.backup_root)}); return
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
            if path == "/api/admin/customers":
                admin, _session = self._admin(); self._csrf()
                result = self.application.identity.create_customer_account(admin["id"], self._body())
                self._json(201, {"success": True, "customer": result}); return
            if path == "/api/admin/vendors":
                admin, _session = self._admin(); self._csrf(); payload = self._body()
                owner_user_id = payload.pop("ownerUserId", None)
                if not isinstance(owner_user_id, str) or not owner_user_id:
                    raise SecurityError(400, "Choose a store-owner account.", "invalid_customer")
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
            if path.startswith("/api/admin/orders/") and path.endswith("/payment"):
                order_id = unquote(path.removeprefix("/api/admin/orders/").removesuffix("/payment"))
                result = self.application.mark_cod_paid(admin["id"], order_id, payload.get("collectionMethod"))
                self._json(200, {"success": True, "order": result}); return
            if path.startswith("/api/admin/orders/") and path.endswith("/status"):
                order_id = unquote(path.removeprefix("/api/admin/orders/").removesuffix("/status"))
                result = self.application.update_order_status(
                    admin["id"], order_id, payload.get("status"), payload.get("reason")
                )
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
            if path.startswith("/api/admin/shop-product-requests/"):
                request_id = unquote(path.removeprefix("/api/admin/shop-product-requests/"))
                result = self.application.transition_shop_product_request(
                    admin["id"], request_id, payload.get("status"), payload.get("reason")
                )
                self._json(200, {"success": True, "request": result}); return
            if path.startswith("/api/admin/shop-products/") and path.endswith("/details"):
                product_id = unquote(path.removeprefix("/api/admin/shop-products/").removesuffix("/details"))
                require_existing_admin_product_media(payload, self.application.product_image_directory)
                result = self._shops().admin_update_product(admin["id"], product_id, payload)
                self._json(200, {"success": True, "product": result}); return
            if path.startswith("/api/admin/customers/") and path.endswith("/password"):
                user_id = unquote(path.removeprefix("/api/admin/customers/").removesuffix("/password"))
                result = self.application.identity.set_customer_password(admin["id"], user_id, payload.get("password"))
                self._json(200, {"success": True, "customer": result}); return
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
