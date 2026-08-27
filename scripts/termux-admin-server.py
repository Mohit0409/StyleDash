#!/usr/bin/env python3
"""Loopback-only StyleDash administrator UI/API. Never tunnel through ngrok."""

from __future__ import annotations

import argparse
import importlib.util
import json
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
    from styledash_shops import ShopWorkflow
except ModuleNotFoundError:
    from scripts.styledash_shops import ShopWorkflow

try:
    from styledash_notify import owner_notifier
except ModuleNotFoundError:
    from scripts.styledash_notify import owner_notifier


MAX_BODY_BYTES = 64 * 1024
ALLOWED_HOSTS = {"127.0.0.1:8081", "localhost:8081"}
ALLOWED_ORIGINS = {"http://127.0.0.1:8081", "http://localhost:8081"}
SECURITY_POLICY = (
    "default-src 'self'; base-uri 'none'; object-src 'none'; frame-ancestors 'none'; "
    "form-action 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "connect-src 'self'"
)


def load_public_module():
    script = Path(__file__).resolve()
    candidates = (
        script.parent.parent / "server" / "serve.py",
        script.parent / "termux-spa-server.py",
    )
    source = next((path for path in candidates if path.exists()), None)
    if source is None:
        raise RuntimeError("StyleDash public server module was not found")
    spec = importlib.util.spec_from_file_location("styledash_public_runtime", source)
    if spec is None or spec.loader is None:
        raise RuntimeError("StyleDash public server module could not be loaded")
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
                title = "StyleDash Out of Stock"
                tags = ["rotating_light"]
            elif kind == "low_stock":
                event = "inventory_low_stock"
                title = "StyleDash Low Stock"
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
                "StyleDash notification preparation failed "
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
        self.payments = public.PaymentService(
            catalog, settings, data_dir, key_id="", key_secret="", webhook_secret="",
            mode=os.environ.get("RAZORPAY_MODE", "test"), gateway=None,
            shop_workflow=self.shops,
        )

    @staticmethod
    def _order_product_ids(order: dict[str, Any]) -> list[str]:
        return [
            item["productId"]
            for item in order.get("items", [])
            if isinstance(item, dict) and isinstance(item.get("productId"), str)
        ]

    def _with_shop_fulfillments(self, admin_id: str, order: dict[str, Any]) -> dict[str, Any]:
        result = dict(order)
        if self.shops is not None and order.get("fulfillmentRequired") is not False:
            result["shopFulfillments"] = self.shops.admin_order_fulfillments(
                admin_id, str(order.get("id") or ""), self._order_product_ids(order)
            )
        else:
            result["shopFulfillments"] = []
        return result

    def list_orders(self, query: str = "", admin_id: str | None = None) -> list[dict[str, Any]]:
        needle = query.strip().casefold()[:100]
        with self.payments.store.lock:
            orders = list(self.payments.store.state["orders"].values())
            if needle:
                orders = [order for order in orders if needle in str(order.get("id", "")).casefold()]
            ordered = [dict(order) for order in sorted(orders, key=lambda item: item.get("createdAt", ""), reverse=True)[:250]]
        return ordered if admin_id is None else [self._with_shop_fulfillments(admin_id, order) for order in ordered]

    def payment_alerts(self) -> list[dict[str, Any]]:
        with self.payments.store.lock:
            alerts = self.payments.store.state["operationalAlerts"].values()
            return [
                dict(alert)
                for alert in sorted(alerts, key=lambda item: item.get("recordedAt", ""), reverse=True)[:250]
            ]

    def get_order(self, order_id: str, admin_id: str | None = None) -> dict[str, Any]:
        with self.payments.store.lock:
            order = self.payments.store.state["orders"].get(order_id)
            if order is None:
                raise SecurityError(404, "Order not found.", "order_not_found")
            result = dict(order)
        return result if admin_id is None else self._with_shop_fulfillments(admin_id, result)

    def override_order_fulfillment(
        self,
        admin_id: str,
        order_id: str,
        application_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        if self.shops is None:
            raise SecurityError(409, "Shop fulfillment is unavailable.", "shop_fulfillment_unavailable")
        with self.payments.store.lock:
            order = self.payments.store.state["orders"].get(order_id)
            if order is None:
                raise SecurityError(404, "Order not found.", "order_not_found")
            if order.get("fulfillmentRequired") is False:
                raise SecurityError(409, "This payment validation order requires no fulfillment.", "no_fulfillment_order")
            if order.get("status") == "cancelled" or order.get("paymentStatus") == "refunded":
                raise SecurityError(
                    409, "A cancelled or fully refunded order cannot be fulfilled.", "order_not_fulfillable"
                )
            product_ids = self._order_product_ids(order)
        return self.shops.admin_override_fulfillment(
            admin_id, order_id, application_id, product_ids, payload
        )

    def return_requests(self, admin_id: str) -> dict[str, list[dict[str, Any]]]:
        item_requests = self.shops.admin_return_requests(admin_id) if self.shops is not None else []
        cancellations: list[dict[str, Any]] = []
        with self.payments.store.lock:
            for order in self.payments.store.state["orders"].values():
                request = order.get("cancellationRequest")
                if not isinstance(request, dict):
                    continue
                row = dict(request)
                row["orderId"] = order.get("id")
                row["orderStatus"] = order.get("status")
                row["paymentStatus"] = order.get("paymentStatus")
                address = order.get("address") if isinstance(order.get("address"), dict) else {}
                row["customerName"] = address.get("name")
                cancellations.append(row)
        cancellations.sort(key=lambda row: str(row.get("createdAt") or ""), reverse=True)
        return {"items": item_requests, "cancellations": cancellations}

    def transition_return_request(
        self, admin_id: str, request_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        if self.shops is None:
            raise SecurityError(409, "Return requests are unavailable.", "returns_unavailable")
        result = self.shops.admin_transition_return_request(
            admin_id, request_id, payload.get("status"),
            payload.get("note"), payload.get("resolutionReference"),
        )
        if result.get("status") in {"REJECTED", "EXCHANGED", "CANCELLED"}:
            self.shops.restore_settlements_for_order(result["orderId"])
        return result

    def transition_cancellation_request(
        self, admin_id: str, order_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        if not isinstance(payload, dict) or not isinstance(payload.get("status"), str):
            raise SecurityError(400, "Invalid cancellation request status.", "invalid_cancellation_request_status")
        target = payload["status"].strip().upper()
        transitions = {
            "REQUESTED": {"UNDER_REVIEW", "REJECTED"},
            "UNDER_REVIEW": {"APPROVED", "REJECTED"},
        }
        note = payload.get("note")
        clean_note = None if note in (None, "") else " ".join(str(note).split())[:1000]
        if target == "REJECTED" and (clean_note is None or len(clean_note) < 2):
            raise SecurityError(400, "A rejection note is required.", "cancellation_note_required")
        now = iso(utc_now())
        with self.payments.store.lock:
            order = self.payments.store.state["orders"].get(order_id)
            if order is None:
                raise SecurityError(404, "Order not found.", "order_not_found")
            request = order.get("cancellationRequest")
            if not isinstance(request, dict):
                raise SecurityError(404, "Cancellation request not found.", "cancellation_request_not_found")
            current = str(request.get("status") or "").upper()
            if target not in transitions.get(current, set()):
                raise SecurityError(409, "Cancellation request transition is not allowed.", "invalid_cancellation_request_transition")
            updated = dict(request)
            updated["status"] = target
            updated["updatedAt"] = now
            updated["reviewedAt"] = now
            if clean_note is not None:
                updated["adminNote"] = clean_note
            if target == "REJECTED":
                updated["resolvedAt"] = now
            order["cancellationRequest"] = updated
            order["updatedAt"] = now
            self.payments.store.save()
            result = dict(updated)
        self.identity.record_action(
            admin_id, "cancellation_request_status", "order", order_id, "success",
            {"from": current, "to": target},
        )
        if self.shops is not None and target == "REJECTED":
            self.shops.restore_settlements_for_order(order_id)
        return result

    def settlements(self, admin_id: str) -> list[dict[str, Any]]:
        if self.shops is None:
            return []
        rows = self.shops.admin_settlements(admin_id)
        with self.payments.store.lock:
            orders = self.payments.store.state["orders"]
            for row in rows:
                order = orders.get(row["orderId"])
                if not isinstance(order, dict):
                    row["orderStatus"] = None
                    row["currentPaymentStatus"] = None
                    continue
                row["orderStatus"] = order.get("status")
                row["currentPaymentStatus"] = order.get("paymentStatus")
                row["refundAmount"] = order.get("refundAmount")
                request = order.get("cancellationRequest")
                row["cancellationStatus"] = request.get("status") if isinstance(request, dict) else None
        return rows

    def set_shop_commission(self, admin_id: str, application_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        if self.shops is None:
            raise SecurityError(409, "Shop settlements are unavailable.", "settlements_unavailable")
        if not isinstance(payload, dict) or set(payload) != {"commissionPercent"}:
            raise SecurityError(400, "A commission percentage is required.", "invalid_commission")
        return self.shops.admin_set_commission(admin_id, application_id, payload.get("commissionPercent"))

    def _settlement_order_guard(self, settlement: dict[str, Any]) -> None:
        with self.payments.store.lock:
            order = self.payments.store.state["orders"].get(settlement["orderId"])
            if not isinstance(order, dict):
                raise SecurityError(404, "Settlement order not found.", "order_not_found")
            if order.get("status") == "cancelled" or order.get("paymentStatus") == "refunded":
                raise SecurityError(409, "Cancelled or refunded orders cannot be settled.", "settlement_order_blocked")
            refund_amount = order.get("refundAmount")
            if isinstance(refund_amount, (int, float)) and not isinstance(refund_amount, bool) and refund_amount > 0:
                raise SecurityError(409, "An order with recorded refunds cannot be settled automatically.", "settlement_refund_hold")
            request = order.get("cancellationRequest")
            if isinstance(request, dict) and request.get("status") not in {"REJECTED", "CANCELLED"}:
                raise SecurityError(409, "An active cancellation request blocks settlement.", "settlement_cancellation_hold")
            if settlement.get("paymentMethod") in {"upi", "card"} and order.get("paymentStatus") != "paid":
                raise SecurityError(409, "Online payment is not in a paid state.", "settlement_payment_unresolved")

    def settlement_action(self, admin_id: str, settlement_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        if self.shops is None:
            raise SecurityError(409, "Shop settlements are unavailable.", "settlements_unavailable")
        if not isinstance(payload, dict) or not isinstance(payload.get("action"), str):
            raise SecurityError(400, "A settlement action is required.", "invalid_settlement_action")
        action = payload["action"].strip().upper()
        current = next((row for row in self.shops.admin_settlements(admin_id) if row["id"] == settlement_id), None)
        if current is None:
            raise SecurityError(404, "Settlement not found.", "settlement_not_found")
        self._settlement_order_guard(current)
        if action == "CONFIRM_COLLECTION":
            return self.shops.admin_confirm_settlement_collection(admin_id, settlement_id, payload.get("note"))
        if action == "RELEASE":
            return self.shops.admin_release_settlement(admin_id, settlement_id, payload.get("note"))
        if action == "MARK_SETTLED":
            return self.shops.admin_mark_settlement_settled(
                admin_id, settlement_id, payload.get("payoutReference"), payload.get("note")
            )
        raise SecurityError(400, "Unknown settlement action.", "invalid_settlement_action")

    def _close_cancellation_request_after_order_cancel(
        self, order: dict[str, Any], now: str
    ) -> None:
        request = order.get("cancellationRequest")
        if not isinstance(request, dict):
            return
        if request.get("status") in {"REJECTED", "CANCELLED"}:
            return
        updated = dict(request)
        updated["status"] = "CANCELLED"
        updated["updatedAt"] = now
        updated["resolvedAt"] = now
        order["cancellationRequest"] = updated

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

    def update_order_status(self, admin_id: str, order_id: str, requested: Any) -> dict[str, Any]:
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
                order.setdefault("statusHistory", []).append({
                    "status": "cancelled",
                    "timestamp": now,
                    "note": "Cancelled after verified Razorpay refund" if online else "Cash on Delivery order cancelled",
                })
                self._close_cancellation_request_after_order_cancel(order, now)
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
            },
        )

        if requested == "cancelled" and self.shops is not None:
            self.shops.void_settlements_for_order(order_id, "Order cancelled")

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
                    title="StyleDash Order Cancelled",
                    message=(
                        f"Order: {order_id}\n"
                        f"Amount: {amount_text}\n"
                        f"Payment: {payment_method}\n"
                        f"Status: Cancelled"
                    ),
                    priority=5,
                    tags=["no_entry_sign"],
                )

            except Exception:
                # Cancellation and audit are already durable.
                print(
                    "StyleDash notification preparation failed "
                    "event=order_cancelled",
                    flush=True,
                )

        return result

    def inventory(self, query: str = "", low_only: bool = False) -> list[dict[str, Any]]:
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
    server_version = "StyleDashAdmin"
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

    def _body(self) -> dict[str, Any]:
        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().casefold()
        if content_type != "application/json":
            raise SecurityError(415, "Content-Type must be application/json.", "invalid_content_type")
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            raise SecurityError(400, "Invalid request body.", "malformed_request") from None
        if length <= 0 or length > MAX_BODY_BYTES:
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
                admin, _session = self._admin(); query = self._query().get("q", [""])[0]
                self._json(200, {"success": True, "orders": self.application.list_orders(query, admin_id=admin["id"])}); return
            if path == "/api/admin/returns":
                admin, _session = self._admin()
                self._json(200, {"success": True, **self.application.return_requests(admin["id"])}); return
            if path == "/api/admin/settlements":
                admin, _session = self._admin()
                self._json(200, {"success": True, "settlements": self.application.settlements(admin["id"])}); return
            if path == "/api/admin/payment-alerts":
                self._admin(); self._json(200, {"success": True, "alerts": self.application.payment_alerts()}); return
            if path.startswith("/api/admin/orders/"):
                admin, _session = self._admin(); order_id = unquote(path.removeprefix("/api/admin/orders/"))
                self._json(200, {"success": True, "order": self.application.get_order(order_id, admin_id=admin["id"])}); return
            if path == "/api/admin/vendors":
                admin, _session = self._admin()
                self._json(200, {"success": True, "applications": self._shops().admin_list_applications(admin["id"])}); return
            if path == "/api/admin/shop-products":
                admin, _session = self._admin()
                self._json(200, {"success": True, "products": self._shops().admin_list_products(admin["id"])}); return
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
            if path.startswith("/api/admin/settlements/"):
                settlement_id = unquote(path.removeprefix("/api/admin/settlements/")).strip("/")
                if not settlement_id or "/" in settlement_id:
                    raise SecurityError(404, "Settlement not found.", "settlement_not_found")
                result = self.application.settlement_action(admin["id"], settlement_id, payload)
                self._json(200, {"success": True, "settlement": result}); return
            if path.startswith("/api/admin/vendors/") and path.endswith("/commission"):
                application_id = unquote(path.removeprefix("/api/admin/vendors/").removesuffix("/commission")).strip("/")
                if not application_id or "/" in application_id:
                    raise SecurityError(404, "Shop application not found.", "vendor_application_not_found")
                result = self.application.set_shop_commission(admin["id"], application_id, payload)
                self._json(200, {"success": True, "application": result}); return
            if path.startswith("/api/admin/returns/items/"):
                request_id = unquote(path.removeprefix("/api/admin/returns/items/")).strip("/")
                if not request_id or "/" in request_id:
                    raise SecurityError(404, "Return request not found.", "return_request_not_found")
                result = self.application.transition_return_request(admin["id"], request_id, payload)
                self._json(200, {"success": True, "request": result}); return
            if path.startswith("/api/admin/returns/cancellations/"):
                order_id = unquote(path.removeprefix("/api/admin/returns/cancellations/")).strip("/")
                if not order_id or "/" in order_id:
                    raise SecurityError(404, "Cancellation request not found.", "cancellation_request_not_found")
                result = self.application.transition_cancellation_request(admin["id"], order_id, payload)
                self._json(200, {"success": True, "request": result}); return
            if path.startswith("/api/admin/orders/") and "/fulfillment/" in path:
                tail = path.removeprefix("/api/admin/orders/")
                raw_order_id, raw_application_id = tail.split("/fulfillment/", 1)
                order_id = unquote(raw_order_id).strip("/")
                application_id = unquote(raw_application_id).strip("/")
                if not order_id or not application_id or "/" in order_id or "/" in application_id:
                    raise SecurityError(404, "Shop segment not found for this order.", "order_shop_segment_not_found")
                result = self.application.override_order_fulfillment(
                    admin["id"], order_id, application_id, payload
                )
                self._json(200, {"success": True, "fulfillment": result}); return
            if path.startswith("/api/admin/orders/") and path.endswith("/status"):
                order_id = unquote(path.removeprefix("/api/admin/orders/").removesuffix("/status"))
                result = self.application.update_order_status(admin["id"], order_id, payload.get("status"))
                self._json(200, {"success": True, "order": result}); return
            if path.startswith("/api/admin/vendors/"):
                application_id = unquote(path.removeprefix("/api/admin/vendors/"))
                result = self._shops().admin_transition_application(
                    admin["id"], application_id, payload.get("status"), payload.get("reason")
                )
                self._json(200, {"success": True, "application": result}); return
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
    print(f"StyleDash local administrator service listening on {args.bind}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
