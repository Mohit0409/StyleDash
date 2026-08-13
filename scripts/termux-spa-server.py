#!/usr/bin/env python3
"""Serve StyleDash and provide its same-origin payment API."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from http.cookies import SimpleCookie
from collections import defaultdict, deque
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlsplit

try:
    import fcntl
except ImportError:  # Windows test environment; Termux provides fcntl.
    fcntl = None

try:
    from styledash_security import COOKIE_NAME, SecurityError, SecurityStore
except ModuleNotFoundError:  # Repository test import path.
    from scripts.styledash_security import COOKIE_NAME, SecurityError, SecurityStore

try:
    import razorpay
except ImportError:  # The static site and COD can still start without the SDK.
    razorpay = None


MAX_BODY_BYTES = 64 * 1024
API_PREFIX = "/api/"
SECURITY_POLICY = (
    "default-src 'self'; "
    "base-uri 'self'; object-src 'none'; frame-ancestors 'self'; "
    "script-src 'self' https://checkout.razorpay.com https://*.razorpay.com; "
    "style-src 'self' 'unsafe-inline' https://*.razorpay.com; "
    "img-src 'self' data: https:; font-src 'self' data: https:; "
    "connect-src 'self' https://api.razorpay.com https://*.razorpay.com; "
    "frame-src https://api.razorpay.com https://checkout.razorpay.com https://*.razorpay.com; "
    "form-action 'self' https://api.razorpay.com https://*.razorpay.com"
)


class ApiError(Exception):
    def __init__(self, status: int, message: str, code: str = "request_failed") -> None:
        super().__init__(message)
        self.status = status
        self.message = message
        self.code = code


class RazorpayGateway:
    """Small adapter that keeps SDK details out of the order service."""

    def __init__(self, key_id: str, key_secret: str) -> None:
        if razorpay is None:
            raise RuntimeError("The Razorpay Python package is not installed")
        self.client = razorpay.Client(auth=(key_id, key_secret))

    def create_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return self.client.order.create(data=payload)
        except Exception as exc:  # Razorpay SDK exceptions expose status_code.
            status = int(getattr(exc, "status_code", 500) or 500)
            if status in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
                raise ApiError(
                    HTTPStatus.UNAUTHORIZED,
                    "Payment service authentication failed.",
                    "payment_auth_failed",
                ) from None
            raise ApiError(
                HTTPStatus.BAD_GATEWAY,
                "The payment service is temporarily unavailable.",
                "payment_service_unavailable",
            ) from None

    def fetch_payment(self, payment_id: str) -> dict[str, Any]:
        try:
            return self.client.payment.fetch(payment_id)
        except Exception as exc:  # Razorpay SDK exceptions expose status_code.
            status = int(getattr(exc, "status_code", 500) or 500)
            if status in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
                raise ApiError(
                    HTTPStatus.UNAUTHORIZED,
                    "Payment service authentication failed.",
                    "payment_auth_failed",
                ) from None
            raise ApiError(
                HTTPStatus.BAD_GATEWAY,
                "The payment service is temporarily unavailable.",
                "payment_service_unavailable",
            ) from None


class StateFileLock:
    """Thread lock plus Termux process lock; reloads state after acquisition."""

    def __init__(self, owner: "JsonStateStore") -> None:
        self.owner = owner
        self.thread_lock = threading.RLock()
        self.handle = None
        self.depth = 0

    def __enter__(self):
        self.thread_lock.acquire()
        if self.depth:
            self.depth += 1
            return self
        try:
            self.owner.lock_path.parent.mkdir(parents=True, exist_ok=True)
            self.handle = self.owner.lock_path.open("a+b")
            os.chmod(self.owner.lock_path, 0o600)
            if fcntl is not None:
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX)
            self.owner.state = self.owner._load()
            self.depth = 1
            return self
        except Exception:
            if self.handle:
                self.handle.close()
                self.handle = None
            self.thread_lock.release()
            raise

    def __exit__(self, exc_type, exc_value, traceback):
        self.depth -= 1
        if self.depth:
            self.thread_lock.release()
            return
        try:
            if self.handle and fcntl is not None:
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
            if self.handle:
                self.handle.close()
                self.handle = None
        finally:
            self.thread_lock.release()


class JsonStateStore:
    """Thread-safe JSON persistence using atomic replacement."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock_path = self.path.with_suffix(f"{self.path.suffix}.lock")
        self.state = self._load()
        self.lock = StateFileLock(self)

    def _load(self) -> dict[str, Any]:
        default = {
            "orders": {},
            "inventory": {},
            "idempotency": {},
            "processedPayments": {},
            "processedWebhookEvents": {},
            "operationalAlerts": {},
        }
        if not self.path.exists():
            return default
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(loaded, dict):
                raise RuntimeError("StyleDash payment state is not a JSON object")
            for key, value in default.items():
                loaded.setdefault(key, value)
            for order_id, order in loaded["orders"].items():
                payment_id = order.get("razorpayPaymentId") if isinstance(order, dict) else None
                if payment_id and order.get("paymentStatus") == "paid":
                    loaded["processedPayments"].setdefault(payment_id, order_id)
            return loaded
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError("StyleDash payment state could not be loaded safely") from exc

    def save(self) -> None:
        temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(self.state, handle, separators=(",", ":"), ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, self.path)
        os.chmod(self.path, 0o600)


class RateLimiter:
    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int, window_seconds: int = 60) -> bool:
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            events = self._events[key]
            while events and events[0] < cutoff:
                events.popleft()
            if len(events) >= limit:
                return False
            events.append(now)
            return True


def _money(value: Any, field: str) -> Decimal:
    if isinstance(value, bool):
        raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, f"Invalid {field}.", "invalid_cart")
    try:
        result = Decimal(str(value))
    except Exception:
        raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, f"Invalid {field}.", "invalid_cart") from None
    if not result.is_finite() or result < 0:
        raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, f"Invalid {field}.", "invalid_cart")
    return result


def _rounded_rupees(value: Decimal) -> int:
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _clean_string(value: Any, field: str, minimum: int, maximum: int) -> str:
    if not isinstance(value, str):
        raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, f"Invalid {field}.", "invalid_customer")
    cleaned = value.strip()
    if not minimum <= len(cleaned) <= maximum:
        raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, f"Invalid {field}.", "invalid_customer")
    return cleaned


class PaymentService:
    def __init__(
        self,
        catalog_path: Path,
        settings_path: Path,
        data_directory: Path,
        *,
        key_id: str | None = None,
        key_secret: str | None = None,
        webhook_secret: str | None = None,
        mode: str | None = None,
        gateway: Any | None = None,
        security_store: SecurityStore | None = None,
    ) -> None:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        self.products = {item["id"]: item for item in catalog}
        self.settings = settings
        self.mode = (mode or os.environ.get("RAZORPAY_MODE", "test")).strip().lower()
        if self.mode not in ("test", "live"):
            raise RuntimeError("RAZORPAY_MODE must be test or live")
        prefix = f"RAZORPAY_{self.mode.upper()}"
        self.key_id = key_id if key_id is not None else os.environ.get(f"{prefix}_KEY_ID", "").strip()
        self.key_secret = key_secret if key_secret is not None else os.environ.get(f"{prefix}_KEY_SECRET", "").strip()
        self.webhook_secret = (
            webhook_secret
            if webhook_secret is not None
            else os.environ.get(f"{prefix}_WEBHOOK_SECRET", "").strip()
        )
        self.gateway = gateway
        if self.gateway is None and self.key_id and self.key_secret:
            self.gateway = RazorpayGateway(self.key_id, self.key_secret)
        self.store = JsonStateStore(data_directory / "orders.json")
        self.security = security_store

        configured_pincodes = os.environ.get("STYLEDASH_SUPPORTED_PINCODES", "")
        if configured_pincodes.strip():
            self.supported_pincodes = {
                item.strip() for item in configured_pincodes.split(",") if item.strip()
            }
        else:
            self.supported_pincodes = set(settings["supportedPincodes"])

    def health(self) -> dict[str, str]:
        result = {"status": "ok", "service": "StyleDash", "paymentMode": self.mode}
        if self.security is not None:
            result["database"] = "ok" if self.security.health() else "error"
        return result

    def is_serviceable_pincode(self, pincode: str) -> bool:
        return len(pincode) == 6 and pincode.isdigit() and pincode in self.supported_pincodes

    def check_serviceability(self, pincode: Any) -> dict[str, Any]:
        if not isinstance(pincode, str):
            raise ApiError(HTTPStatus.BAD_REQUEST, "A 6-digit pincode is required.", "invalid_pincode")
        cleaned = pincode.strip()
        if len(cleaned) != 6 or not cleaned.isdigit():
            raise ApiError(HTTPStatus.BAD_REQUEST, "A valid 6-digit pincode is required.", "invalid_pincode")
        if not self.is_serviceable_pincode(cleaned):
            return {"success": True, "pincode": cleaned, "serviceable": False}
        return {
            "success": True,
            "pincode": cleaned,
            "serviceable": True,
            "city": "Neemuch",
            "state": "Madhya Pradesh",
            "expressAvailable": True,
            "estimatedDeliveryMinutes": 60,
        }

    def _inventory(self, state: dict[str, Any], variant: dict[str, Any]) -> int:
        return int(state["inventory"].get(variant["id"], variant["stock"]))

    def _validate_address(self, payload: dict[str, Any]) -> dict[str, str]:
        address = payload.get("address")
        if not isinstance(address, dict):
            raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, "Delivery address is required.", "invalid_customer")
        pincode = _clean_string(address.get("pincode"), "pincode", 6, 6)
        if not self.is_serviceable_pincode(pincode):
            raise ApiError(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "Delivery is not available for this pincode.",
                "unsupported_pincode",
            )
        phone = _clean_string(address.get("phone"), "phone number", 10, 16)
        if not all(character.isdigit() or character in "+ -" for character in phone):
            raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, "Invalid phone number.", "invalid_customer")
        return {
            "id": "addr-checkout",
            "name": _clean_string(address.get("name"), "name", 2, 80),
            "phone": phone,
            "street": _clean_string(address.get("street"), "street address", 5, 200),
            "city": _clean_string(address.get("city"), "city", 2, 80),
            "state": "Madhya Pradesh",
            "pincode": pincode,
        }

    def calculate_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ApiError(HTTPStatus.BAD_REQUEST, "A JSON object is required.", "malformed_request")
        items = payload.get("items")
        if not isinstance(items, list) or not items or len(items) > 50:
            raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, "A non-empty cart is required.", "invalid_cart")

        delivery_method = payload.get("deliveryMethod")
        delivery_fees = self.settings["deliveryFees"]
        if delivery_method not in delivery_fees:
            raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, "Unsupported delivery method.", "invalid_delivery")

        wallet_amount = payload.get("walletAmount", 0)
        if wallet_amount not in (0, None):
            raise ApiError(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "Wallet credit is unavailable until secure authentication is enabled.",
                "wallet_unavailable",
            )

        address = self._validate_address(payload)
        trusted_items: list[dict[str, Any]] = []
        subtotal = Decimal("0")
        seen_variants: set[str] = set()
        max_quantity = int(self.settings["maxQuantityPerItem"])

        with self.store.lock:
            state = self.store.state
            for item in items:
                if not isinstance(item, dict):
                    raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, "Invalid cart item.", "invalid_cart")
                product_id = item.get("productId")
                variant_id = item.get("variantId")
                quantity = item.get("quantity")
                if not isinstance(product_id, str) or product_id not in self.products:
                    raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, "A product is unavailable.", "invalid_product")
                product = self.products[product_id]
                if not product.get("active"):
                    raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, "A product is unavailable.", "invalid_product")
                variant = next(
                    (candidate for candidate in product["variants"] if candidate["id"] == variant_id),
                    None,
                )
                if variant is None:
                    raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, "A product option is unavailable.", "invalid_variant")
                if isinstance(quantity, bool) or not isinstance(quantity, int) or not 1 <= quantity <= max_quantity:
                    raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, "Invalid item quantity.", "invalid_quantity")
                if variant_id in seen_variants:
                    raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, "Duplicate cart item.", "invalid_cart")
                seen_variants.add(variant_id)
                available = self._inventory(state, variant)
                if available < quantity:
                    raise ApiError(
                        HTTPStatus.CONFLICT,
                        f"Only {available} unit(s) remain for {product['name']}.",
                        "insufficient_stock",
                    )
                unit_price = _money(variant.get("price", product["price"]), "price")
                line_total = unit_price * quantity
                subtotal += line_total
                trusted_items.append(
                    {
                        "productId": product_id,
                        "productName": product["name"],
                        "productSlug": product["slug"],
                        "variantId": variant["id"],
                        "sku": variant["sku"],
                        "size": variant["size"],
                        "colourName": variant["colourName"],
                        "quantity": quantity,
                        "unitPrice": _rounded_rupees(unit_price),
                        "lineTotal": _rounded_rupees(line_total),
                    }
                )

        coupon_code = payload.get("couponCode")
        coupon_discount = Decimal("0")
        applied_coupon: str | None = None
        if coupon_code not in (None, ""):
            if not isinstance(coupon_code, str):
                raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, "Invalid coupon.", "invalid_coupon")
            normalized = coupon_code.strip().upper()
            coupon = next((entry for entry in self.settings["coupons"] if entry["code"] == normalized), None)
            if (
                coupon is None
                or not coupon.get("active")
                or date.fromisoformat(coupon["expiryDate"]) < date.today()
                or subtotal < _money(coupon["minOrderValue"], "coupon")
            ):
                raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, "This coupon is not eligible.", "invalid_coupon")
            if coupon["discountType"] == "fixed":
                coupon_discount = _money(coupon["value"], "coupon")
            else:
                coupon_discount = subtotal * _money(coupon["value"], "coupon") / Decimal("100")
                if coupon.get("maxDiscount") is not None:
                    coupon_discount = min(coupon_discount, _money(coupon["maxDiscount"], "coupon"))
            coupon_discount = min(coupon_discount, subtotal)
            applied_coupon = normalized

        delivery_fee = Decimal("0")
        if subtotal < _money(self.settings["freeDeliveryThreshold"], "delivery threshold"):
            delivery_fee = _money(delivery_fees[delivery_method], "delivery fee")
        taxes = Decimal(_rounded_rupees((subtotal - coupon_discount) * _money(self.settings["taxRate"], "tax")))
        grand_total = max(Decimal("0"), subtotal - coupon_discount + delivery_fee + taxes)
        amount_paise = _rounded_rupees(grand_total * Decimal("100"))
        if amount_paise < 100:
            raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, "Order total is below the minimum amount.", "invalid_amount")

        return {
            "items": trusted_items,
            "address": address,
            "userId": str(payload.get("userId") or "guest-user-id")[:128],
            "deliveryMethod": delivery_method,
            "couponCode": applied_coupon,
            "subtotal": _rounded_rupees(subtotal),
            "discount": _rounded_rupees(coupon_discount),
            "walletAmount": 0,
            "deliveryFee": _rounded_rupees(delivery_fee),
            "taxes": _rounded_rupees(taxes),
            "grandTotal": _rounded_rupees(grand_total),
            "amount": amount_paise,
            "currency": self.settings["currency"],
        }

    def _new_order_id(self) -> str:
        return f"SD-{datetime.now(timezone.utc):%Y%m%d}-{secrets.token_hex(3).upper()}"

    def _idempotency_key(self, value: str | None) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str) or not 8 <= len(value) <= 128:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Invalid idempotency key.", "invalid_idempotency_key")
        if not all(character.isalnum() or character in "-_" for character in value):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Invalid idempotency key.", "invalid_idempotency_key")
        return value

    def _public_order(self, order: dict[str, Any]) -> dict[str, Any]:
        allowed = (
            "id", "userId", "items", "address", "paymentMethod", "paymentStatus",
            "subtotal", "discount", "walletAmount", "deliveryFee", "taxes", "grandTotal",
            "deliveryMethod", "estimatedDelivery", "status", "statusHistory", "createdAt",
            "updatedAt", "razorpayOrderId", "razorpayPaymentId", "paymentVerifiedAt",
        )
        return {key: order[key] for key in allowed if key in order}

    def _create_response(self, order: dict[str, Any]) -> dict[str, Any]:
        return {
            "success": True,
            "styleDashOrderId": order["id"],
            "razorpayOrderId": order["razorpayOrderId"],
            "keyId": self.key_id,
            "amount": order["amount"],
            "currency": order["currency"],
            "receipt": order["receipt"],
            "trustedTotals": {
                "subtotal": order["subtotal"],
                "discount": order["discount"],
                "deliveryFee": order["deliveryFee"],
                "taxes": order["taxes"],
                "grandTotal": order["grandTotal"],
            },
        }

    def create_razorpay_order(self, payload: dict[str, Any], idempotency_value: str | None) -> dict[str, Any]:
        if not self.key_id or not self.key_secret or self.gateway is None:
            raise ApiError(
                HTTPStatus.SERVICE_UNAVAILABLE,
                "Online payments are temporarily unavailable.",
                "payments_not_configured",
            )
        expected_key_prefix = f"rzp_{self.mode}_"
        if not self.key_id.startswith(expected_key_prefix):
            raise ApiError(
                HTTPStatus.SERVICE_UNAVAILABLE,
                "Payment configuration does not match the selected mode.",
                "payment_mode_mismatch",
            )
        if payload.get("paymentMethod") not in ("upi", "card"):
            raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, "Unsupported online payment method.", "invalid_payment_method")
        idempotency_key = self._idempotency_key(idempotency_value)
        with self.store.lock:
            if idempotency_key:
                existing_id = self.store.state["idempotency"].get(f"online:{idempotency_key}")
                if existing_id:
                    existing = self.store.state["orders"].get(existing_id)
                    if existing and existing.get("razorpayOrderId"):
                        return self._create_response(existing)
            # Keep the idempotency check, gateway order creation and persistence
            # in one critical section so concurrent retries cannot create two
            # Razorpay orders for the same checkout attempt.
            calculated = self.calculate_order(payload)
            style_order_id = self._new_order_id()
            receipt = style_order_id
            gateway_order = self.gateway.create_order(
                {
                    "amount": calculated["amount"],
                    "currency": calculated["currency"],
                    "receipt": receipt,
                    "notes": {"styleDashOrderId": style_order_id},
                }
            )
            razorpay_order_id = gateway_order.get("id")
            if not isinstance(razorpay_order_id, str) or not razorpay_order_id.startswith("order_"):
                raise ApiError(HTTPStatus.BAD_GATEWAY, "Invalid response from payment service.", "invalid_payment_response")

            now = datetime.now(timezone.utc).isoformat()
            order = {
                **calculated,
                "id": style_order_id,
                "receipt": receipt,
                "razorpayOrderId": razorpay_order_id,
                "paymentMethod": str(payload.get("paymentMethod") or "card"),
                "paymentStatus": "pending",
                "status": "payment_pending",
                "estimatedDelivery": "60 minutes",
                "statusHistory": [{"status": "payment_pending", "timestamp": now, "note": "Awaiting verified payment"}],
                "createdAt": now,
                "updatedAt": now,
            }
            self.store.state["orders"][style_order_id] = order
            if idempotency_key:
                self.store.state["idempotency"][f"online:{idempotency_key}"] = style_order_id
            self.store.save()
            return self._create_response(order)

    def _decrement_inventory(self, state: dict[str, Any], items: list[dict[str, Any]]) -> None:
        checked: list[tuple[str, int, int]] = []
        for item in items:
            product = self.products[item["productId"]]
            variant = next(entry for entry in product["variants"] if entry["id"] == item["variantId"])
            remaining = self._inventory(state, variant)
            quantity = int(item["quantity"])
            if remaining < quantity:
                raise ApiError(
                    HTTPStatus.CONFLICT,
                    "Stock changed while the order was being processed. Contact support before retrying payment.",
                    "stock_changed",
                )
            checked.append((variant["id"], remaining, quantity))
        for variant_id, remaining, quantity in checked:
            state["inventory"][variant_id] = remaining - quantity

    def _find_order_by_razorpay_id(self, razorpay_order_id: str) -> dict[str, Any] | None:
        return next(
            (
                order
                for order in self.store.state["orders"].values()
                if order.get("razorpayOrderId") == razorpay_order_id
            ),
            None,
        )

    def _find_order_by_payment_id(self, payment_id: str) -> dict[str, Any] | None:
        order_id = self.store.state["processedPayments"].get(payment_id)
        if order_id:
            order = self.store.state["orders"].get(order_id)
            if order is not None:
                return order
        return next(
            (
                order
                for order in self.store.state["orders"].values()
                if order.get("razorpayPaymentId") == payment_id
            ),
            None,
        )

    def _finalize_payment(
        self,
        style_order_id: str,
        razorpay_order_id: str,
        payment_id: str,
        *,
        source: str,
        amount: Any | None = None,
        currency: Any | None = None,
    ) -> dict[str, Any]:
        """Atomically mark a verified payment paid and commit inventory once."""
        with self.store.lock:
            state = self.store.state
            order = state["orders"].get(style_order_id)
            if order is None:
                raise ApiError(HTTPStatus.NOT_FOUND, "Order not found.", "order_not_found")
            if order.get("razorpayOrderId") != razorpay_order_id:
                raise ApiError(HTTPStatus.BAD_REQUEST, "Payment does not match this order.", "order_mismatch")
            if amount is not None and (isinstance(amount, bool) or amount != order.get("amount")):
                raise ApiError(HTTPStatus.BAD_REQUEST, "Payment amount does not match this order.", "amount_mismatch")
            if currency is not None and currency != order.get("currency"):
                raise ApiError(HTTPStatus.BAD_REQUEST, "Payment currency does not match this order.", "currency_mismatch")

            processed_order_id = state["processedPayments"].get(payment_id)
            if processed_order_id and processed_order_id != style_order_id:
                raise ApiError(HTTPStatus.CONFLICT, "This payment is already associated with another order.", "duplicate_payment")
            if order.get("paymentStatus") == "paid":
                if order.get("razorpayPaymentId") == payment_id:
                    if payment_id not in state["processedPayments"]:
                        state["processedPayments"][payment_id] = style_order_id
                        self.store.save()
                    return {"success": True, "idempotent": True, "duplicate": True, "order": self._public_order(order)}
                raise ApiError(HTTPStatus.CONFLICT, "This order already has a verified payment.", "duplicate_payment")

            self._decrement_inventory(state, order["items"])
            now = datetime.now(timezone.utc).isoformat()
            order.update(
                {
                    "paymentStatus": "paid",
                    "status": "placed",
                    "razorpayPaymentId": payment_id,
                    "paymentVerifiedAt": now,
                    "paymentVerificationSource": source,
                    "inventoryCommitted": True,
                    "updatedAt": now,
                }
            )
            order["statusHistory"].append(
                {"status": "placed", "timestamp": now, "note": f"Razorpay payment verified by {source}"}
            )
            state["processedPayments"][payment_id] = style_order_id
            self.store.save()
            return {"success": True, "idempotent": False, "duplicate": False, "order": self._public_order(order)}

    def verify_payment(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ApiError(HTTPStatus.BAD_REQUEST, "A JSON object is required.", "malformed_request")
        required = ("razorpay_order_id", "razorpay_payment_id", "razorpay_signature", "styleDashOrderId")
        if any(not isinstance(payload.get(field), str) or not payload[field].strip() for field in required):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Missing payment verification fields.", "missing_payment_fields")
        if not self.key_secret:
            raise ApiError(HTTPStatus.SERVICE_UNAVAILABLE, "Payment verification is unavailable.", "payments_not_configured")

        style_order_id = payload["styleDashOrderId"]
        payment_id = payload["razorpay_payment_id"]
        with self.store.lock:
            order = self.store.state["orders"].get(style_order_id)
            if order is None:
                raise ApiError(HTTPStatus.NOT_FOUND, "Order not found.", "order_not_found")
            if order.get("razorpayOrderId") != payload["razorpay_order_id"]:
                raise ApiError(HTTPStatus.BAD_REQUEST, "Payment does not match this order.", "order_mismatch")
            expected = hmac.new(
                self.key_secret.encode("utf-8"),
                f"{order['razorpayOrderId']}|{payment_id}".encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
            if not hmac.compare_digest(expected, payload["razorpay_signature"]):
                raise ApiError(HTTPStatus.BAD_REQUEST, "Payment verification failed.", "signature_mismatch")

            expected_amount = order["amount"]
            expected_currency = order["currency"]

        if self.gateway is None or not hasattr(self.gateway, "fetch_payment"):
            raise ApiError(
                HTTPStatus.SERVICE_UNAVAILABLE,
                "Payment capture verification is unavailable.",
                "payments_not_configured",
            )
        payment = self.gateway.fetch_payment(payment_id)
        if not isinstance(payment, dict):
            raise ApiError(HTTPStatus.BAD_GATEWAY, "Invalid response from payment service.", "invalid_payment_response")
        if payment.get("order_id") != payload["razorpay_order_id"]:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Payment does not match this order.", "order_mismatch")
        amount = payment.get("amount")
        currency = payment.get("currency")
        if isinstance(amount, bool) or amount != expected_amount:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Payment amount does not match this order.", "amount_mismatch")
        if currency != expected_currency:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Payment currency does not match this order.", "currency_mismatch")

        status = payment.get("status")
        if status == "authorized":
            return self._record_authorized_payment(style_order_id, payment_id)
        if status != "captured":
            raise ApiError(
                HTTPStatus.CONFLICT,
                "Payment has not been captured. The order remains pending.",
                "payment_not_captured",
            )
        return self._finalize_payment(
            style_order_id,
            payload["razorpay_order_id"],
            payment_id,
            source="browser callback",
            amount=amount,
            currency=currency,
        )

    def _record_authorized_payment(self, style_order_id: str, payment_id: str) -> dict[str, Any]:
        """Record authorization without treating it as captured or fulfilling inventory."""
        with self.store.lock:
            order = self.store.state["orders"].get(style_order_id)
            if order is None:
                raise ApiError(HTTPStatus.NOT_FOUND, "Order not found.", "order_not_found")
            if order.get("paymentStatus") == "paid":
                return {"success": True, "pending": False, "idempotent": True, "order": self._public_order(order)}
            previous = order.get("lastAuthorizedPayment")
            if isinstance(previous, dict) and previous.get("razorpayPaymentId") == payment_id:
                return {"success": True, "pending": True, "idempotent": True, "order": self._public_order(order)}
            now = datetime.now(timezone.utc).isoformat()
            order["lastAuthorizedPayment"] = {"razorpayPaymentId": payment_id, "recordedAt": now}
            order["updatedAt"] = now
            self.store.save()
            return {"success": True, "pending": True, "idempotent": False, "order": self._public_order(order)}

    @staticmethod
    def _webhook_entity(payload: dict[str, Any], name: str) -> dict[str, Any]:
        container = payload.get("payload")
        wrapper = container.get(name) if isinstance(container, dict) else None
        entity = wrapper.get("entity") if isinstance(wrapper, dict) else None
        return entity if isinstance(entity, dict) else {}

    def _record_failed_payment(self, razorpay_order_id: str, payment_id: str | None) -> bool:
        with self.store.lock:
            order = self._find_order_by_razorpay_id(razorpay_order_id)
            if order is None or order.get("paymentStatus") == "paid":
                return False
            previous = order.get("lastPaymentFailure")
            if isinstance(previous, dict) and payment_id and previous.get("razorpayPaymentId") == payment_id:
                return False
            now = datetime.now(timezone.utc).isoformat()
            order["lastPaymentFailure"] = {
                "razorpayPaymentId": payment_id,
                "recordedAt": now,
            }
            order["updatedAt"] = now
            order["statusHistory"].append(
                {"status": "payment_pending", "timestamp": now, "note": "Razorpay reported a failed payment attempt"}
            )
            self.store.save()
            return True

    @staticmethod
    def _safe_webhook_event_id(event_id: str | None) -> str | None:
        if not isinstance(event_id, str):
            return None
        cleaned = event_id.strip()
        if not cleaned or len(cleaned) > 200 or any(ord(character) < 32 for character in cleaned):
            return None
        return cleaned

    def _record_operational_alert(
        self,
        event: str,
        entity_id: str,
        payment_id: str,
        razorpay_order_id: str | None,
        event_id: str | None,
    ) -> dict[str, Any]:
        """Persist a minimal private-admin alert without mutating fulfillment state."""
        alert_id = f"{event}:{entity_id}"
        safe_event_id = self._safe_webhook_event_id(event_id)
        with self.store.lock:
            state = self.store.state
            event_key = safe_event_id or alert_id
            previous_alert_id = state["processedWebhookEvents"].get(event_key)
            if previous_alert_id:
                return {"duplicate": True, "alert": state["operationalAlerts"].get(previous_alert_id)}
            existing = state["operationalAlerts"].get(alert_id)
            if existing is not None:
                state["processedWebhookEvents"][event_key] = alert_id
                self.store.save()
                return {"duplicate": True, "alert": existing}

            order = self._find_order_by_payment_id(payment_id)
            if order is None and razorpay_order_id:
                order = self._find_order_by_razorpay_id(razorpay_order_id)
            now = datetime.now(timezone.utc).isoformat()
            alert = {
                "id": alert_id,
                "type": event,
                "entityId": entity_id,
                "razorpayPaymentId": payment_id,
                "styleDashOrderId": order.get("id") if order else None,
                "status": "open",
                "recordedAt": now,
            }
            state["operationalAlerts"][alert_id] = alert
            state["processedWebhookEvents"][event_key] = alert_id
            if order is not None:
                order["requiresAdminAttention"] = True
                if event == "refund.failed":
                    order["refundFailureAttention"] = True
                else:
                    order["paymentDisputed"] = True
                    order["paymentDisputeId"] = entity_id
                order["updatedAt"] = now
            self.store.save()
            return {"duplicate": False, "alert": alert}

    def process_webhook(
        self,
        raw_body: bytes,
        signature: str | None,
        event_id: str | None = None,
    ) -> dict[str, Any]:
        if not signature:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Missing webhook signature.", "missing_webhook_signature")
        if not self.webhook_secret:
            raise ApiError(HTTPStatus.UNAUTHORIZED, "Webhook verification failed.", "webhook_signature_mismatch")
        expected = hmac.new(self.webhook_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise ApiError(HTTPStatus.UNAUTHORIZED, "Webhook verification failed.", "webhook_signature_mismatch")
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Malformed JSON request.", "malformed_request") from None
        if not isinstance(payload, dict) or not isinstance(payload.get("event"), str):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Malformed webhook request.", "malformed_request")

        event = payload["event"]
        if event == "payment.authorized":
            print("Razorpay webhook event=payment.authorized result=observed-not-fulfilled", flush=True)
            return {"success": True}
        if event in ("refund.failed", "payment.dispute.created"):
            entity_name = "refund" if event == "refund.failed" else "dispute"
            entity = self._webhook_entity(payload, entity_name)
            payment = self._webhook_entity(payload, "payment")
            entity_id = entity.get("id")
            payment_id = entity.get("payment_id") or payment.get("id")
            payment_entity_id = payment.get("id")
            if not isinstance(entity_id, str) or not entity_id:
                raise ApiError(HTTPStatus.BAD_REQUEST, "Webhook is missing alert information.", "malformed_webhook")
            if not isinstance(payment_id, str) or not payment_id:
                raise ApiError(HTTPStatus.BAD_REQUEST, "Webhook is missing payment information.", "malformed_webhook")
            if payment_entity_id and payment_entity_id != payment_id:
                raise ApiError(HTTPStatus.BAD_REQUEST, "Webhook payment information does not match.", "malformed_webhook")
            razorpay_order_id = payment.get("order_id")
            if not isinstance(razorpay_order_id, str):
                razorpay_order_id = None
            recorded = self._record_operational_alert(
                event, entity_id, payment_id, razorpay_order_id, event_id
            )
            alert = recorded["alert"] or {}
            print(
                f"Razorpay webhook event={event} styleOrderId={alert.get('styleDashOrderId') or '-'} "
                f"entityId={entity_id} result={'duplicate' if recorded['duplicate'] else 'alerted'}",
                flush=True,
            )
            response = {"success": True}
            if recorded["duplicate"]:
                response["duplicate"] = True
            return response
        if event not in ("payment.captured", "payment.failed", "order.paid"):
            print(f"Razorpay webhook event={event} result=ignored", flush=True)
            return {"success": True}

        payment = self._webhook_entity(payload, "payment")
        order_entity = self._webhook_entity(payload, "order")
        payment_id = payment.get("id")
        razorpay_order_id = payment.get("order_id") or order_entity.get("id")
        if not isinstance(razorpay_order_id, str) or not razorpay_order_id:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Webhook is missing order information.", "malformed_webhook")

        with self.store.lock:
            style_order = self._find_order_by_razorpay_id(razorpay_order_id)
            style_order_id = style_order.get("id") if style_order else None
        if style_order_id is None:
            raise ApiError(HTTPStatus.NOT_FOUND, "Order not found.", "order_not_found")

        if event == "payment.failed":
            recorded = self._record_failed_payment(
                razorpay_order_id,
                payment_id if isinstance(payment_id, str) else None,
            )
            print(
                f"Razorpay webhook event={event} styleOrderId={style_order_id} "
                f"razorpayOrderId={razorpay_order_id} razorpayPaymentId={payment_id or '-'} "
                f"result={'failed' if recorded else 'ignored'}",
                flush=True,
            )
            return {"success": True}

        if not isinstance(payment_id, str) or not payment_id:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Webhook is missing payment information.", "malformed_webhook")
        amount = payment.get("amount", order_entity.get("amount_paid", order_entity.get("amount")))
        currency = payment.get("currency", order_entity.get("currency"))
        if isinstance(amount, bool) or not isinstance(amount, int):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Webhook is missing payment amount.", "malformed_webhook")
        if not isinstance(currency, str):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Webhook is missing payment currency.", "malformed_webhook")
        result = self._finalize_payment(
            style_order_id,
            razorpay_order_id,
            payment_id,
            source=f"{event} webhook",
            amount=amount,
            currency=currency,
        )
        print(
            f"Razorpay webhook event={event} styleOrderId={style_order_id} "
            f"razorpayOrderId={razorpay_order_id} razorpayPaymentId={payment_id} "
            f"result={'duplicate' if result['idempotent'] else 'processed'}",
            flush=True,
        )
        response = {"success": True}
        if result["idempotent"]:
            response["duplicate"] = True
        return response

    def place_cod_order(self, payload: dict[str, Any], idempotency_value: str | None) -> dict[str, Any]:
        idempotency_key = self._idempotency_key(idempotency_value)
        with self.store.lock:
            if idempotency_key:
                existing_id = self.store.state["idempotency"].get(f"cod:{idempotency_key}")
                if existing_id:
                    existing = self.store.state["orders"].get(existing_id)
                    if existing:
                        return {"success": True, "idempotent": True, "order": self._public_order(existing)}
            calculated = self.calculate_order(payload)
            now = datetime.now(timezone.utc).isoformat()
            style_order_id = self._new_order_id()
            order = {
                **calculated,
                "id": style_order_id,
                "paymentMethod": "cod",
                "paymentStatus": "pending",
                "status": "placed",
                "estimatedDelivery": "60 minutes",
                "statusHistory": [{"status": "placed", "timestamp": now, "note": "Cash on Delivery order placed"}],
                "createdAt": now,
                "updatedAt": now,
            }
            self._decrement_inventory(self.store.state, order["items"])
            self.store.state["orders"][style_order_id] = order
            if idempotency_key:
                self.store.state["idempotency"][f"cod:{idempotency_key}"] = style_order_id
            self.store.save()
            return {"success": True, "idempotent": False, "order": self._public_order(order)}


class StyleDashRequestHandler(SimpleHTTPRequestHandler):
    payment_service: PaymentService
    rate_limiter = RateLimiter()

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header("Content-Security-Policy", SECURITY_POLICY)
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        super().end_headers()

    def _json_response(
        self, status: int, payload: dict[str, Any], *, head_only: bool = False,
        headers: dict[str, str] | None = None,
    ) -> None:
        encoded = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        if not head_only:
            self.wfile.write(encoded)

    def _error_response(self, error: ApiError) -> None:
        self._json_response(error.status, {"success": False, "error": error.message, "code": error.code})

    def _security_error(self, error: SecurityError) -> None:
        self._json_response(error.status, {"success": False, "error": error.message, "code": error.code})

    def _security(self) -> SecurityStore:
        if self.payment_service.security is None:
            raise SecurityError(HTTPStatus.SERVICE_UNAVAILABLE, "Authentication is unavailable.", "authentication_unavailable")
        return self.payment_service.security

    def _session_token(self) -> str | None:
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
        except Exception:
            return None
        morsel = cookie.get(COOKIE_NAME)
        return morsel.value if morsel else None

    def _current_user(self) -> tuple[dict[str, Any], Any]:
        return self._security().authenticate(self._session_token())

    def _csrf(self) -> None:
        origin = self.headers.get("Origin")
        expected_origin = os.environ.get("STYLEDASH_PUBLIC_ORIGIN", "").rstrip("/")
        if origin and expected_origin and origin.rstrip("/") != expected_origin:
            raise SecurityError(403, "Request origin is not allowed.", "invalid_origin")
        self._security().verify_csrf(self._session_token(), self.headers.get("X-CSRF-Token"))

    def _auth_payload(self, payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        user, _session = self._current_user()
        self._csrf()
        trusted = dict(payload)
        trusted["userId"] = user["id"]
        trusted.pop("role", None)
        trusted.pop("paymentStatus", None)
        return user, trusted

    def _client_key(self, route: str) -> str:
        forwarded = self.headers.get("X-Forwarded-For", "").split(",", 1)[0].strip()
        peer = self.client_address[0]
        trusted_proxy = os.environ.get("STYLEDASH_TRUST_LOOPBACK_PROXY") == "1" and peer in ("127.0.0.1", "::1")
        client = forwarded if trusted_proxy and forwarded and len(forwarded) <= 64 else peer
        return f"{route}:{client}"

    def _read_json(self) -> dict[str, Any]:
        raw_body = self._read_raw_body()
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Malformed JSON request.", "malformed_request") from None
        if not isinstance(payload, dict):
            raise ApiError(HTTPStatus.BAD_REQUEST, "A JSON object is required.", "malformed_request")
        return payload

    def _read_raw_body(self) -> bytes:
        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            raise ApiError(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "Content-Type must be application/json.", "invalid_content_type")
        raw_length = self.headers.get("Content-Length")
        if raw_length is None:
            raise ApiError(HTTPStatus.LENGTH_REQUIRED, "Content-Length is required.", "length_required")
        try:
            length = int(raw_length)
        except ValueError:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Invalid Content-Length.", "malformed_request") from None
        if length <= 0 or length > MAX_BODY_BYTES:
            raise ApiError(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "Request body is too large.", "body_too_large")
        return self.rfile.read(length)

    def _rate_limit(self, route: str, limit: int) -> None:
        if not self.rate_limiter.allow(self._client_key(route), limit):
            raise ApiError(HTTPStatus.TOO_MANY_REQUESTS, "Too many requests. Please wait and try again.", "rate_limited")

    def do_GET(self) -> None:  # noqa: N802 - stdlib override name
        parsed = urlsplit(self.path)
        path = parsed.path
        try:
            if self._sensitive_path(path):
                self._json_response(HTTPStatus.NOT_FOUND, {"success": False, "error": "Not found.", "code": "not_found"})
                return
            if path == "/api/health":
                self._json_response(HTTPStatus.OK, self.payment_service.health())
                return
            if path == "/api/serviceability":
                self._rate_limit(path, 60)
                query = parse_qs(parsed.query, keep_blank_values=True)
                pincode_values = query.get("pincode", [])
                pincode = pincode_values[0] if len(pincode_values) == 1 else None
                self._json_response(HTTPStatus.OK, self.payment_service.check_serviceability(pincode))
                return
            if path == "/api/auth/me":
                raw = self._session_token()
                user, _session = self._current_user()
                profile = self._security().profile(user["id"])
                self._json_response(HTTPStatus.OK, {"success": True, "user": profile, "csrfToken": self._security().csrf_token(raw or "")})
                return
            if path == "/api/orders":
                user, _session = self._current_user()
                orders = self._security().list_orders(self.payment_service.store, user["id"])
                self._json_response(HTTPStatus.OK, {"success": True, "orders": orders})
                return
            if path == "/api/profile":
                user, _session = self._current_user()
                self._json_response(HTTPStatus.OK, {"success": True, "profile": self._security().profile(user["id"])})
                return
            if path.startswith("/api/orders/"):
                user, _session = self._current_user()
                order = self._security().get_order(self.payment_service.store, path.removeprefix("/api/orders/"), user["id"])
                self._json_response(HTTPStatus.OK, {"success": True, "order": order})
                return
            if path.startswith(API_PREFIX):
                self._json_response(HTTPStatus.NOT_FOUND, {"success": False, "error": "API endpoint not found.", "code": "not_found"})
                return
            super().do_GET()
        except ApiError as error:
            self._error_response(error)
        except SecurityError as error:
            self._security_error(error)

    def do_HEAD(self) -> None:  # noqa: N802 - stdlib override name
        path = urlsplit(self.path).path
        if self._sensitive_path(path):
            self._json_response(HTTPStatus.NOT_FOUND, {"success": False, "error": "Not found.", "code": "not_found"}, head_only=True)
            return
        if path == "/api/health":
            self._json_response(HTTPStatus.OK, self.payment_service.health(), head_only=True)
            return
        if path.startswith(API_PREFIX):
            self._json_response(HTTPStatus.METHOD_NOT_ALLOWED, {"success": False, "error": "Method not allowed.", "code": "method_not_allowed"}, head_only=True)
            return
        super().do_HEAD()

    def do_POST(self) -> None:  # noqa: N802 - stdlib override name
        path = urlsplit(self.path).path
        try:
            if self._sensitive_path(path):
                self._json_response(HTTPStatus.NOT_FOUND, {"success": False, "error": "Not found.", "code": "not_found"})
                return
            if path == "/api/create-order":
                self._rate_limit(path, 10)
                _user, payload = self._auth_payload(self._read_json())
                result = self.payment_service.create_razorpay_order(
                    payload, self.headers.get("Idempotency-Key")
                )
                self._json_response(HTTPStatus.CREATED, result)
                return
            if path == "/api/verify-payment":
                self._rate_limit(path, 20)
                user, payload = self._auth_payload(self._read_json())
                self._security().get_order(self.payment_service.store, str(payload.get("styleDashOrderId", "")), user["id"])
                result = self.payment_service.verify_payment(payload)
                self._json_response(HTTPStatus.OK, result)
                return
            if path == "/api/webhooks/razorpay":
                self._rate_limit(path, 120)
                result = self.payment_service.process_webhook(
                    self._read_raw_body(),
                    self.headers.get("X-Razorpay-Signature"),
                    self.headers.get("X-Razorpay-Event-Id"),
                )
                self._json_response(HTTPStatus.OK, result)
                return
            if path == "/api/place-cod-order":
                self._rate_limit(path, 10)
                _user, payload = self._auth_payload(self._read_json())
                result = self.payment_service.place_cod_order(
                    payload, self.headers.get("Idempotency-Key")
                )
                self._json_response(HTTPStatus.CREATED, result)
                return
            if path == "/api/auth/register":
                self._rate_limit(path, 5)
                user, raw, csrf = self._security().register(self._read_json())
                self._json_response(HTTPStatus.CREATED, {"success": True, "user": user, "csrfToken": csrf}, headers={"Set-Cookie": self._security().cookie(raw)})
                return
            if path == "/api/auth/login":
                self._rate_limit(path, 12)
                user, raw, csrf = self._security().login(self._read_json(), self._client_key("login"))
                self._json_response(HTTPStatus.OK, {"success": True, "user": user, "csrfToken": csrf}, headers={"Set-Cookie": self._security().cookie(raw)})
                return
            if path == "/api/auth/logout":
                self._current_user()
                self._csrf()
                self._security().revoke(self._session_token() or "")
                self._json_response(HTTPStatus.OK, {"success": True}, headers={"Set-Cookie": self._security().clear_cookie()})
                return
            if path == "/api/auth/change-password":
                self._csrf()
                raw, csrf = self._security().change_password(self._session_token() or "", self._read_json())
                self._json_response(HTTPStatus.OK, {"success": True, "csrfToken": csrf}, headers={"Set-Cookie": self._security().cookie(raw)})
                return
            if path == "/api/vendor-applications":
                self._rate_limit(path, 5)
                user, _session = self._current_user()
                self._csrf()
                result = self._security().create_vendor_application(user["id"], self._read_json())
                self._json_response(HTTPStatus.CREATED, {"success": True, "application": result})
                return
            if path.startswith(API_PREFIX):
                self._json_response(HTTPStatus.NOT_FOUND, {"success": False, "error": "API endpoint not found.", "code": "not_found"})
                return
            self._json_response(HTTPStatus.METHOD_NOT_ALLOWED, {"success": False, "error": "Method not allowed.", "code": "method_not_allowed"})
        except ApiError as error:
            self._error_response(error)
        except SecurityError as error:
            self._security_error(error)
        except Exception:
            self._json_response(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"success": False, "error": "The server could not process this request.", "code": "internal_error"},
            )

    def do_PUT(self) -> None:  # noqa: N802 - stdlib override name
        if self._sensitive_path(urlsplit(self.path).path):
            self._json_response(HTTPStatus.NOT_FOUND, {"success": False, "error": "Not found.", "code": "not_found"})
            return
        self._json_response(HTTPStatus.METHOD_NOT_ALLOWED, {"success": False, "error": "Method not allowed.", "code": "method_not_allowed"})

    def do_DELETE(self) -> None:  # noqa: N802 - stdlib override name
        self.do_PUT()

    def do_PATCH(self) -> None:  # noqa: N802 - stdlib override name
        path = urlsplit(self.path).path
        try:
            if self._sensitive_path(path):
                self._json_response(HTTPStatus.NOT_FOUND, {"success": False, "error": "Not found.", "code": "not_found"})
                return
            if path == "/api/profile":
                user, _session = self._current_user()
                self._csrf()
                profile = self._security().update_profile(user["id"], self._read_json())
                self._json_response(HTTPStatus.OK, {"success": True, "profile": profile})
                return
            self._json_response(HTTPStatus.METHOD_NOT_ALLOWED, {"success": False, "error": "Method not allowed.", "code": "method_not_allowed"})
        except ApiError as error:
            self._error_response(error)
        except SecurityError as error:
            self._security_error(error)

    def send_head(self):  # noqa: N802 - stdlib override name
        url_path = urlsplit(self.path).path
        if self._sensitive_path(url_path):
            self.send_error(HTTPStatus.NOT_FOUND)
            return None
        translated = Path(self.translate_path(url_path))
        if not translated.exists() and "." not in Path(url_path).name and not url_path.startswith(API_PREFIX):
            self.path = "/index.html"
        return super().send_head()

    @staticmethod
    def _sensitive_path(path: str) -> bool:
        lowered = path.lower()
        return (
            lowered.startswith(("/backups/", "/logs/", "/.config/", "/admin", "/api/admin/", "/api/internal-admin/", "/admin-api/"))
            or lowered.startswith(("/tools/", "/payment-data/"))
            or lowered in ("/.env", "/secrets.env", "/styledash.db", "/firebase-service-account.json", "/serve.py", "/styledash_security.py")
            or lowered.endswith((".db", ".db-wal", ".db-shm", ".log", ".py", ".pyc"))
        )

    def log_message(self, format: str, *args: Any) -> None:
        # The standard access log contains method/path/status only; request bodies
        # and environment configuration are never logged.
        super().log_message(format, *args)


def _default_payment_file(filename: str) -> Path:
    script = Path(__file__).resolve()
    candidates = (
        script.parent / "payment-data" / filename,
        script.parent.parent / "server" / "payment-data" / filename,
    )
    return next((candidate for candidate in candidates if candidate.exists()), candidates[-1])


def create_server(
    bind: str,
    port: int,
    directory: Path,
    catalog_path: Path,
    settings_path: Path,
    data_directory: Path,
    *,
    service: PaymentService | None = None,
) -> ThreadingHTTPServer:
    if service is None:
        encryption_key = os.environ.get("STYLEDASH_TOTP_ENCRYPTION_KEY", "").strip()
        if not encryption_key:
            raise RuntimeError("STYLEDASH_TOTP_ENCRYPTION_KEY is required")
        database_path = Path(
            os.environ.get("STYLEDASH_DATABASE_PATH", str(data_directory.parent / "styledash.db"))
        ).resolve()
        security_store = SecurityStore(database_path, encryption_key)
        payment_service = PaymentService(
            catalog_path, settings_path, data_directory, security_store=security_store
        )
    else:
        payment_service = service
    class BoundStyleDashRequestHandler(StyleDashRequestHandler):
        pass

    BoundStyleDashRequestHandler.payment_service = payment_service
    handler = partial(BoundStyleDashRequestHandler, directory=str(directory))
    return ThreadingHTTPServer((bind, port), handler)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--directory", default=".")
    parser.add_argument(
        "--catalog",
        default=os.environ.get("STYLEDASH_CATALOG_PATH", str(_default_payment_file("catalog.json"))),
    )
    parser.add_argument(
        "--settings",
        default=os.environ.get("STYLEDASH_SETTINGS_PATH", str(_default_payment_file("settings.json"))),
    )
    parser.add_argument(
        "--data-directory",
        default=os.environ.get("STYLEDASH_DATA_DIR", str(Path.home() / ".local" / "share" / "styledash")),
    )
    args = parser.parse_args()

    directory = Path(args.directory).resolve()
    server = create_server(
        args.bind,
        args.port,
        directory,
        Path(args.catalog).resolve(),
        Path(args.settings).resolve(),
        Path(args.data_directory).resolve(),
    )
    print(f"Serving StyleDash at http://{args.bind}:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
