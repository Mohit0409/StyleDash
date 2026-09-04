#!/usr/bin/env python3
"""Serve Vibe4You and provide its same-origin payment API."""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import hmac
import json
import os
import posixpath
import re
import secrets
import threading
import time
from http.cookies import SimpleCookie
from collections import defaultdict, deque
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, unquote, urlsplit
from xml.sax.saxutils import escape as xml_escape

try:
    import fcntl
except ImportError:  # Windows test environment; Termux provides fcntl.
    fcntl = None

try:
    from styledash_security import COOKIE_NAME, SecurityError, SecurityStore, normalize_email, token_hash
except ModuleNotFoundError:  # Repository test import path.
    from scripts.styledash_security import COOKIE_NAME, SecurityError, SecurityStore, normalize_email, token_hash

try:
    from styledash_shops import ShopWorkflow
except ModuleNotFoundError:  # Repository test import path.
    from scripts.styledash_shops import ShopWorkflow

try:
    from styledash_reviews import ReviewWorkflow
except ModuleNotFoundError:  # Repository test import path.
    from scripts.styledash_reviews import ReviewWorkflow

try:
    from styledash_mail import PasswordResetDeliveryQueue, SmtpPasswordResetSender
except ModuleNotFoundError:  # Repository test import path.
    from scripts.styledash_mail import PasswordResetDeliveryQueue, SmtpPasswordResetSender

try:
    from styledash_notify import mask_email, mask_phone, owner_notifier
except ModuleNotFoundError:  # Repository test import path.
    from scripts.styledash_notify import mask_email, mask_phone, owner_notifier

try:
    from receipt_pdf import build_receipt_pdf
except ModuleNotFoundError:  # Repository test import path.
    from scripts.receipt_pdf import build_receipt_pdf

try:
    import razorpay
except ImportError:  # The static site and COD can still start without the SDK.
    razorpay = None


MAX_BODY_BYTES = 64 * 1024
PRODUCT_IMAGE_MAX_BYTES = 500 * 1024
PRODUCT_IMAGE_REQUEST_MAX_BYTES = 700 * 1024
PRODUCT_IMAGE_ROUTE_PATTERN = re.compile(r"^/media/product-images/([0-9a-f]{32}\.(?:webp|jpg|png))$")
API_PREFIX = "/api/"
# Firebase/Google endpoints are added narrowly (never a wildcard) and only to
# support the Google + Phone-OTP identity flows; Firebase is never granted
# order/payment/inventory/admin authority.
SECURITY_POLICY = (
    "default-src 'self'; "
    "base-uri 'self'; object-src 'none'; frame-ancestors 'self'; "
    "script-src 'self' https://checkout.razorpay.com https://*.razorpay.com "
    "https://apis.google.com https://www.gstatic.com https://www.google.com https://www.recaptcha.net "
    "https://static.cloudflareinsights.com; "
    "style-src 'self' 'unsafe-inline' https://*.razorpay.com; "
    "img-src 'self' data: https:; font-src 'self' data: https:; "
    "connect-src 'self' https://api.razorpay.com https://*.razorpay.com "
    "https://identitytoolkit.googleapis.com https://securetoken.googleapis.com https://www.googleapis.com "
    "https://*.firebaseio.com wss://*.firebaseio.com https://cloudflareinsights.com; "
    "frame-src https://api.razorpay.com https://checkout.razorpay.com https://*.razorpay.com "
    "https://accounts.google.com https://*.firebaseapp.com https://www.google.com https://www.recaptcha.net; "
    "form-action 'self' https://api.razorpay.com https://*.razorpay.com"
)
ACCESS_LOG_TOKEN_PATTERN = re.compile(r"([?&](?:token|reset_token)=)[^&#\s]*", re.IGNORECASE)
PAYMENT_TEST_PRODUCT_ID = "styledash-payment-test-item"
PAYMENT_TEST_PRODUCT_SLUG = "styledash-payment-test-item"
PAYMENT_TEST_ROUTE = f"/payment-test/{PAYMENT_TEST_PRODUCT_SLUG}"
PAYMENT_TEST_PRODUCT_NAME = "Vibe4You Payment Test Item"
PAYMENT_TEST_VARIANT_ID = "styledash-payment-test-item-validation"
PAYMENT_TEST_PRICE_RUPEES = 10
PAYMENT_TEST_AMOUNT_PAISE = 1000
PAYMENT_TEST_CURRENCY = "INR"
PAYMENT_TEST_ADMIN_LABELS = ["TEST", "NO FULFILLMENT REQUIRED"]
LOW_STOCK_THRESHOLD = 5


def _notify_finalized_payment(order: dict[str, Any]) -> None:
    """Best-effort owner notification after captured payment is durable."""

    try:
        order_id = str(order.get("id") or "-")
        grand_total = order.get("grandTotal")

        amount_text = (
            f"?{grand_total}"
            if isinstance(grand_total, (int, float))
            and not isinstance(grand_total, bool)
            else "-"
        )

        payment_method = str(
            order.get("paymentMethod") or "online"
        ).upper()

        status = order.get("status")

        if status == "payment_review_required":
            owner_notifier().send(
                event="payment_review_required",
                title="PAYMENT NEEDS ATTENTION",
                message=(
                    f"Order: {order_id}\n"
                    f"Amount: {amount_text}\n"
                    f"Payment: {payment_method}\n"
                    f"Status: Paid - review required\n"
                    f"Reason: Stock confirmation required"
                ),
                priority=5,
                tags=["rotating_light"],
            )
            return

        owner_notifier().send(
            event="payment_captured",
            title="Vibe4You Payment Received",
            message=(
                f"Order: {order_id}\n"
                f"Amount: {amount_text}\n"
                f"Payment: {payment_method}\n"
                f"Status: Paid"
            ),
            priority=5,
            tags=["moneybag"],
        )

    except Exception:
        # Notification preparation must never affect financial truth.
        print(
            "Vibe4You notification preparation failed "
            "event=payment_captured",
            flush=True,
        )


def _notify_inventory_alerts(
    alerts: list[dict[str, Any]],
) -> None:
    """Send inventory threshold alerts only after durable persistence."""

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

            remaining = alert.get("remaining")

            owner_notifier().send(
                event=event,
                title=title,
                message=(
                    f"Product: {product_name}\n"
                    f"Variant: {size} / {colour}\n"
                    f"Remaining: {remaining}"
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
            "processedRefunds": {},
            "processedWebhookEvents": {},
            "operationalAlerts": {},
        }
        if not self.path.exists():
            return default
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(loaded, dict):
                raise RuntimeError("Vibe4You payment state is not a JSON object")
            for key, value in default.items():
                loaded.setdefault(key, value)
            for order_id, order in loaded["orders"].items():
                payment_id = order.get("razorpayPaymentId") if isinstance(order, dict) else None
                if payment_id and order.get("paymentStatus") == "paid":
                    loaded["processedPayments"].setdefault(payment_id, order_id)
            return loaded
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError("Vibe4You payment state could not be loaded safely") from exc

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


def _pdf_escape(value: Any) -> str:
    text = str(value or "").encode("latin-1", "replace").decode("latin-1")
    text = "".join(character if ord(character) >= 32 else " " for character in text)
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _simple_pdf(lines: list[str]) -> bytes:
    wrapped: list[str] = []
    for line in lines:
        text = str(line or "")
        if not text:
            wrapped.append("")
            continue
        while len(text) > 88:
            split = text.rfind(" ", 0, 89)
            split = split if split > 20 else 88
            wrapped.append(text[:split].rstrip())
            text = text[split:].lstrip()
        wrapped.append(text)
    pages = [wrapped[index:index + 38] for index in range(0, len(wrapped), 38)] or [[""]]
    font_number = 3 + (2 * len(pages))
    kids = " ".join(f"{3 + (2 * index)} 0 R" for index in range(len(pages)))
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode(),
    ]
    for index, page_lines in enumerate(pages):
        page_number = 3 + (2 * index)
        content_number = page_number + 1
        commands = ["BT", "/F1 11 Tf", "48 760 Td"]
        for line_index, line in enumerate(page_lines):
            if line_index:
                commands.append("0 -17 Td")
            commands.append(f"({_pdf_escape(line)}) Tj")
        commands.append("ET")
        stream = "\n".join(commands).encode("latin-1", "replace")
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 {font_number} 0 R >> >> /Contents {content_number} 0 R >>".encode())
        objects.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(pdf)); pdf.extend(f"{number} 0 obj\n".encode()); pdf.extend(obj); pdf.extend(b"\nendobj\n")
    xref = len(pdf); pdf.extend(f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]: pdf.extend(f"{offset:010d} 00000 n \n".encode())
    pdf.extend(f"trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(pdf)


def _clean_string(value: Any, field: str, minimum: int, maximum: int) -> str:
    if not isinstance(value, str):
        raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, f"Invalid {field}.", "invalid_customer")
    cleaned = value.strip()
    if not minimum <= len(cleaned) <= maximum:
        raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, f"Invalid {field}.", "invalid_customer")
    return cleaned


def _is_six_ascii_digits(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 6
        and all("0" <= character <= "9" for character in value)
    )


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
        shop_workflow: ShopWorkflow | None = None,
        payment_test_enabled: bool | None = None,
        payment_test_allowed_emails: set[str] | None = None,
    ) -> None:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        self._products_lock = threading.RLock()
        self._static_products = {item["id"]: item for item in catalog}
        self.products = dict(self._static_products)
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
        self.shops = shop_workflow
        if self.shops is None and security_store is not None:
            self.shops = ShopWorkflow(security_store.path)
        self.refresh_shop_products()

        configured_pincodes = os.environ.get("STYLEDASH_SUPPORTED_PINCODES", "")
        if configured_pincodes.strip():
            self.supported_pincodes = {
                item.strip() for item in configured_pincodes.split(",") if item.strip()
            }
        else:
            self.supported_pincodes = set(settings["supportedPincodes"])

        self.payment_test_enabled = (
            payment_test_enabled
            if payment_test_enabled is not None
            else os.environ.get("STYLEDASH_ENABLE_TEST_PRODUCT", "").strip().casefold() == "true"
        )
        if payment_test_allowed_emails is None:
            configured_emails = os.environ.get("STYLEDASH_TEST_PRODUCT_ALLOWED_EMAILS", "")
            candidates = {item.strip() for item in configured_emails.split(",") if item.strip()}
        else:
            candidates = payment_test_allowed_emails
        try:
            self.payment_test_allowed_emails = {normalize_email(item) for item in candidates}
        except SecurityError:
            raise RuntimeError("STYLEDASH_TEST_PRODUCT_ALLOWED_EMAILS contains an invalid email address") from None

    def health(self) -> dict[str, str]:
        result = {"status": "ok", "service": "Vibe4You"}
        if self.security is not None:
            result["database"] = "ok" if self.security.health() else "error"
        return result

    def refresh_shop_products(self) -> None:
        """Atomically refresh DB-backed products without rewriting catalog JSON.

        All shop submissions remain in the authoritative map. Non-published or
        suspended entries are retained with active=false so historic order
        inventory can still be finalized or released safely.
        """
        dynamic = self.shops.payment_catalog_products() if self.shops is not None else []
        snapshot = dict(self._static_products)
        snapshot.update({product["id"]: product for product in dynamic})
        with self._products_lock:
            self.products = snapshot

    def product_snapshot(self) -> dict[str, dict[str, Any]]:
        with self._products_lock:
            return self.products

    def order_for_display(self, order: dict[str, Any]) -> dict[str, Any]:
        """Enrich safe order-item snapshots with current display-only metadata."""
        self.refresh_shop_products()
        products = self.product_snapshot()
        result = dict(order)
        if "items" not in order:
            return result
        display_items: list[dict[str, Any]] = []
        for source in order.get("items", []) or []:
            item = dict(source)
            product = products.get(item.get("productId"))
            if product is not None:
                for key, product_key in (
                    ("storeId", "vendorId"), ("storeName", "storeName"),
                    ("storeSlug", "storeSlug"),
                ):
                    value = product.get(product_key)
                    if value and not item.get(key):
                        item[key] = value
                variant = next((candidate for candidate in product.get("variants", [])
                                if candidate.get("id") == item.get("variantId")), None)
                images = (variant or {}).get("images") or product.get("images") or []
                image_url = item.get("imageUrl") or product.get("thumbnail") or (images[0] if images else None)
                if image_url:
                    item["imageUrl"] = image_url
            display_items.append(item)
        result["items"] = display_items
        return result

    def receipt_pdf(self, order: dict[str, Any]) -> bytes:
        display = self.order_for_display(order)
        if display.get("status") != "delivered":
            raise SecurityError(409, "Receipt is available after delivery.", "receipt_not_ready")
        return build_receipt_pdf(display)

    @staticmethod
    def express_delivery_available(now: datetime | None = None) -> bool:
        current = now or datetime.now(timezone.utc)
        india_time = current.astimezone(timezone(timedelta(hours=5, minutes=30)))
        return india_time.weekday() >= 5

    @staticmethod
    def estimated_delivery_label(delivery_method: str) -> str:
        return "60 minutes" if delivery_method == "express" else "within a day"

    def is_serviceable_pincode(self, pincode: str) -> bool:
        return _is_six_ascii_digits(pincode) and pincode in self.supported_pincodes

    def check_serviceability(self, pincode: Any) -> dict[str, Any]:
        if not _is_six_ascii_digits(pincode):
            raise ApiError(HTTPStatus.BAD_REQUEST, "A valid 6-digit pincode is required.", "invalid_pincode")
        if not self.is_serviceable_pincode(pincode):
            return {"success": True, "pincode": pincode, "serviceable": False}
        return {
            "success": True,
            "pincode": pincode,
            "serviceable": True,
            "city": "Neemuch",
            "state": "Madhya Pradesh",
            "expressAvailable": self.express_delivery_available(),
            "estimatedDeliveryMinutes": 60 if self.express_delivery_available() else None,
        }

    def can_access_payment_test_product(self, user: Any) -> bool:
        if (
            not self.payment_test_enabled
            or not isinstance(user, dict)
            or user.get("emailVerified") is not True
        ):
            return False
        try:
            normalized = normalize_email(user.get("email"))
        except SecurityError:
            return False
        return normalized in self.payment_test_allowed_emails

    def payment_test_product(self, user: Any) -> dict[str, Any]:
        if not self.can_access_payment_test_product(user):
            raise ApiError(HTTPStatus.NOT_FOUND, "Not found.", "not_found")
        return {
            "success": True,
            "product": {
                "id": PAYMENT_TEST_PRODUCT_ID,
                "slug": PAYMENT_TEST_PRODUCT_SLUG,
                "name": PAYMENT_TEST_PRODUCT_NAME,
                "price": PAYMENT_TEST_PRICE_RUPEES,
                "amount": PAYMENT_TEST_AMOUNT_PAISE,
                "currency": PAYMENT_TEST_CURRENCY,
                "fulfillmentRequired": False,
            },
        }

    def _inventory(self, state: dict[str, Any], variant: dict[str, Any]) -> int:
        return int(state["inventory"].get(variant["id"], variant["stock"]))

    def public_inventory_availability(self, variant_id: Any = None, product_ids: Any = None) -> dict[str, Any]:
        """Return only customer-safe, current availability for active catalog variants."""
        if variant_id is not None and (
            not isinstance(variant_id, str) or not variant_id or len(variant_id) > 128
        ):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Invalid product option.", "invalid_variant")
        if product_ids is not None and (
            not isinstance(product_ids, list) or not product_ids or len(product_ids) > 32
            or any(not isinstance(product_id, str) or not product_id or len(product_id) > 128 for product_id in product_ids)
        ):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Invalid product selection.", "invalid_product")
        if variant_id is not None and product_ids is not None:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Choose one inventory filter.", "invalid_inventory_filter")
        product_filter = set(product_ids) if product_ids is not None else None

        self.refresh_shop_products()
        products = self.product_snapshot()
        availability: list[dict[str, Any]] = []
        with self.store.lock:
            state = self.store.state
            for product in products.values():
                if not product.get("active") or (product_filter is not None and product["id"] not in product_filter):
                    continue
                for variant in product["variants"]:
                    if variant.get("active") is False:
                        continue
                    if variant_id is not None and variant["id"] != variant_id:
                        continue
                    availability.append({
                        "productId": product["id"],
                        "variantId": variant["id"],
                        "available": self._inventory(state, variant) > 0,
                    })
        return {"success": True, "availability": availability}

    def shop_inventory_snapshot(self, product_ids: list[str]) -> dict[str, int]:
        self.refresh_shop_products()
        products = self.product_snapshot()
        result: dict[str, int] = {}
        with self.store.lock:
            state = self.store.state
            for product_id in product_ids:
                product = products.get(product_id)
                if not product or not product.get("vendorId") or not product.get("variants"):
                    continue
                for variant in product["variants"]:
                    result[variant["id"]] = self._inventory(state, variant)
        return result

    def set_shop_inventory(
        self, product_id: str, stock: Any, variant_id: str | None = None
    ) -> dict[str, Any]:
        if (
            isinstance(stock, bool)
            or not isinstance(stock, int)
            or not 0 <= stock <= 100_000
        ):
            raise SecurityError(
                400,
                "Stock must be a whole number from 0 to 100000.",
                "invalid_inventory_adjustment",
            )
        self.refresh_shop_products()
        product = self.product_snapshot().get(product_id)
        if (
            not product
            or not product.get("vendorId")
            or not product.get("active")
            or not product.get("variants")
        ):
            raise SecurityError(
                409,
                "The published product is not currently active.",
                "published_product_required",
            )
        active_variants = [item for item in product["variants"] if item.get("active") is not False]
        if variant_id is None:
            if len(active_variants) != 1:
                raise SecurityError(
                    400,
                    "Choose the size whose stock you want to update.",
                    "variant_required",
                )
            variant = active_variants[0]
        else:
            variant = next(
                (item for item in active_variants if item["id"] == variant_id),
                None,
            )
            if variant is None:
                raise SecurityError(404, "Product size variant not found.", "variant_not_found")
        inventory_alert = None
        with self.store.lock:
            before = self._inventory(self.store.state, variant)
            inventory_alert = self._inventory_alert_for_change(
                product, variant, before, stock
            )
            self.store.state["inventory"][variant["id"]] = stock
            self.store.save()
        if inventory_alert is not None:
            _notify_inventory_alerts([inventory_alert])
        return {
            "productId": product_id,
            "variantId": variant["id"],
            "size": variant.get("size"),
            "before": before,
            "stock": stock,
        }

    def _validate_address(self, payload: dict[str, Any]) -> dict[str, str]:
        address = payload.get("address")
        if not isinstance(address, dict):
            raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, "Delivery address is required.", "invalid_customer")
        pincode = address.get("pincode")
        if not _is_six_ascii_digits(pincode) or not self.is_serviceable_pincode(pincode):
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
        self.refresh_shop_products()
        products = self.product_snapshot()
        if not isinstance(payload, dict):
            raise ApiError(HTTPStatus.BAD_REQUEST, "A JSON object is required.", "malformed_request")
        items = payload.get("items")
        if not isinstance(items, list) or not items or len(items) > 50:
            raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, "A non-empty cart is required.", "invalid_cart")

        delivery_method = payload.get("deliveryMethod")
        delivery_fees = self.settings["deliveryFees"]
        if delivery_method not in delivery_fees:
            raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, "Unsupported delivery method.", "invalid_delivery")
        if delivery_method == "express" and not self.express_delivery_available():
            delivery_method = "standard"

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
                if not isinstance(product_id, str) or product_id not in products:
                    raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, "A product is unavailable.", "invalid_product")
                product = products[product_id]
                if not product.get("active"):
                    raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, "A product is unavailable.", "invalid_product")
                variant = next(
                    (candidate for candidate in product["variants"] if candidate["id"] == variant_id),
                    None,
                )
                if variant is None or variant.get("active") is False:
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
                trusted_item = {
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
                for key, value in (
                    ("storeId", product.get("vendorId")),
                    ("storeName", product.get("storeName")),
                    ("storeSlug", product.get("storeSlug")),
                ):
                    if value:
                        trusted_item[key] = value
                images = variant.get("images") or product.get("images") or []
                image_url = product.get("thumbnail") or (images[0] if images else None)
                if image_url:
                    trusted_item["imageUrl"] = image_url
                trusted_items.append(trusted_item)

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
        display_order = self.order_for_display(order)
        allowed = (
            "id", "userId", "items", "address", "paymentMethod", "paymentStatus",
            "subtotal", "discount", "walletAmount", "deliveryFee", "taxes", "grandTotal",
            "deliveryMethod", "estimatedDelivery", "status", "statusHistory", "createdAt",
            "updatedAt", "razorpayOrderId", "razorpayPaymentId", "paymentVerifiedAt",
            "isPaymentTestOrder", "fulfillmentRequired", "adminLabels", "inventoryCommitted",
            "inventoryReleasedAt", "refundId", "refundAmount", "refundCurrency", "refundProcessedAt",
            "cancellationReason", "cancelledAt",
        )
        return {key: display_order[key] for key in allowed if key in display_order}

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
                "estimatedDelivery": self.estimated_delivery_label(calculated["deliveryMethod"]),
                "statusHistory": [{"status": "payment_pending", "timestamp": now, "note": "Awaiting verified payment"}],
                "createdAt": now,
                "updatedAt": now,
            }
            self.store.state["orders"][style_order_id] = order
            if idempotency_key:
                self.store.state["idempotency"][f"online:{idempotency_key}"] = style_order_id
            self.store.save()
            return self._create_response(order)

    def create_payment_test_order(
        self,
        user: dict[str, Any],
        payload: dict[str, Any],
        idempotency_value: str | None,
    ) -> dict[str, Any]:
        """Create an owner-authorized, exact-value Razorpay validation order."""
        if not self.can_access_payment_test_product(user):
            raise ApiError(HTTPStatus.NOT_FOUND, "Not found.", "not_found")
        user_id = str(user.get("id") or "")[:128]
        if not user_id:
            raise ApiError(HTTPStatus.NOT_FOUND, "Not found.", "not_found")
        if set(payload) - {"paymentMethod"}:
            raise ApiError(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "Unsupported payment-test field.",
                "invalid_payment_test_request",
            )
        payment_method = payload.get("paymentMethod")
        if payment_method not in ("upi", "card"):
            raise ApiError(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "Razorpay is required for this validation item.",
                "invalid_payment_method",
            )
        if self.settings.get("currency") != PAYMENT_TEST_CURRENCY:
            raise ApiError(
                HTTPStatus.SERVICE_UNAVAILABLE,
                "The payment validation item is unavailable.",
                "payment_test_configuration_error",
            )
        if not self.key_id or not self.key_secret or self.gateway is None:
            raise ApiError(
                HTTPStatus.SERVICE_UNAVAILABLE,
                "Online payments are temporarily unavailable.",
                "payments_not_configured",
            )
        if not self.key_id.startswith(f"rzp_{self.mode}_"):
            raise ApiError(
                HTTPStatus.SERVICE_UNAVAILABLE,
                "Payment configuration does not match the selected mode.",
                "payment_mode_mismatch",
            )

        idempotency_key = self._idempotency_key(idempotency_value)
        stored_idempotency_key = (
            f"payment-test:{user_id}:{idempotency_key}" if idempotency_key else None
        )
        with self.store.lock:
            if stored_idempotency_key:
                existing_id = self.store.state["idempotency"].get(stored_idempotency_key)
                if existing_id:
                    existing = self.store.state["orders"].get(existing_id)
                    if existing and existing.get("isPaymentTestOrder") is True:
                        return self._create_response(existing)

            style_order_id = self._new_order_id()
            receipt = style_order_id
            gateway_order = self.gateway.create_order({
                "amount": PAYMENT_TEST_AMOUNT_PAISE,
                "currency": PAYMENT_TEST_CURRENCY,
                "receipt": receipt,
                "notes": {
                    "styleDashOrderId": style_order_id,
                    "purpose": "payment_validation",
                    "fulfillmentRequired": "false",
                },
            })
            razorpay_order_id = gateway_order.get("id")
            if not isinstance(razorpay_order_id, str) or not razorpay_order_id.startswith("order_"):
                raise ApiError(HTTPStatus.BAD_GATEWAY, "Invalid response from payment service.", "invalid_payment_response")

            now = datetime.now(timezone.utc).isoformat()
            order = {
                "id": style_order_id,
                "receipt": receipt,
                "razorpayOrderId": razorpay_order_id,
                "userId": user_id,
                "items": [{
                    "productId": PAYMENT_TEST_PRODUCT_ID,
                    "productName": PAYMENT_TEST_PRODUCT_NAME,
                    "productSlug": PAYMENT_TEST_PRODUCT_SLUG,
                    "variantId": PAYMENT_TEST_VARIANT_ID,
                    "sku": "PAYMENT-VALIDATION-ONLY",
                    "size": "N/A",
                    "colourName": "N/A",
                    "quantity": 1,
                    "unitPrice": PAYMENT_TEST_PRICE_RUPEES,
                    "lineTotal": PAYMENT_TEST_PRICE_RUPEES,
                }],
                "address": {
                    "id": "payment-test-no-fulfillment",
                    "name": "Payment validation only",
                    "phone": "",
                    "street": "No fulfillment required",
                    "city": "",
                    "state": "",
                    "pincode": "",
                },
                "paymentMethod": payment_method,
                "paymentStatus": "pending",
                "subtotal": PAYMENT_TEST_PRICE_RUPEES,
                "discount": 0,
                "walletAmount": 0,
                "deliveryFee": 0,
                "taxes": 0,
                "grandTotal": PAYMENT_TEST_PRICE_RUPEES,
                "amount": PAYMENT_TEST_AMOUNT_PAISE,
                "currency": PAYMENT_TEST_CURRENCY,
                "deliveryMethod": "none",
                "estimatedDelivery": "No fulfillment required",
                "status": "payment_pending",
                "statusHistory": [{
                    "status": "payment_pending",
                    "timestamp": now,
                    "note": "TEST payment awaiting captured-state verification; no fulfillment required",
                }],
                "isPaymentTestOrder": True,
                "fulfillmentRequired": False,
                "adminLabels": list(PAYMENT_TEST_ADMIN_LABELS),
                "inventoryCommitted": False,
                "createdAt": now,
                "updatedAt": now,
            }
            self.store.state["orders"][style_order_id] = order
            if stored_idempotency_key:
                self.store.state["idempotency"][stored_idempotency_key] = style_order_id
            self.store.save()
            return self._create_response(order)

    def _inventory_alert_for_change(
        self,
        product: dict[str, Any],
        variant: dict[str, Any],
        before: int,
        after: int,
    ) -> dict[str, Any] | None:
        """Return one alert only when stock crosses an important threshold."""

        kind: str | None = None

        if before > 0 and after == 0:
            kind = "out_of_stock"
        elif (
            before > LOW_STOCK_THRESHOLD
            and 0 < after <= LOW_STOCK_THRESHOLD
        ):
            kind = "low_stock"

        if kind is None:
            return None

        return {
            "kind": kind,
            "productId": product.get("id"),
            "productName": product.get("name"),
            "variantId": variant.get("id"),
            "size": variant.get("size"),
            "colour": (
                variant.get("colourName")
                or variant.get("colour")
                or "-"
            ),
            "remaining": after,
        }

    def _try_decrement_inventory(
        self,
        state: dict[str, Any],
        items: list[dict[str, Any]],
        *,
        inventory_alerts: list[dict[str, Any]] | None = None,
    ) -> bool:
        """Commit all requested inventory or none of it."""

        products = self.product_snapshot()
        checked: list[
            tuple[
                dict[str, Any],
                dict[str, Any],
                int,
                int,
            ]
        ] = []

        for item in items:
            if not isinstance(item, dict):
                return False

            product = products.get(item.get("productId"))

            if not isinstance(product, dict):
                return False

            variant = next(
                (
                    entry
                    for entry in product.get("variants", [])
                    if entry.get("id") == item.get("variantId")
                ),
                None,
            )

            if not isinstance(variant, dict):
                return False

            try:
                remaining = self._inventory(state, variant)
                quantity = int(item.get("quantity", 0))
            except (KeyError, TypeError, ValueError):
                return False

            if quantity <= 0 or remaining < quantity:
                return False

            checked.append(
                (
                    product,
                    variant,
                    remaining,
                    quantity,
                )
            )

        for product, variant, remaining, quantity in checked:
            after = remaining - quantity
            state["inventory"][variant["id"]] = after

            if inventory_alerts is not None:
                alert = self._inventory_alert_for_change(
                    product,
                    variant,
                    remaining,
                    after,
                )

                if alert is not None:
                    inventory_alerts.append(alert)

        return True

    def _decrement_inventory(
        self,
        state: dict[str, Any],
        items: list[dict[str, Any]],
        *,
        inventory_alerts: list[dict[str, Any]] | None = None,
    ) -> None:
        if not self._try_decrement_inventory(
            state,
            items,
            inventory_alerts=inventory_alerts,
        ):
            raise ApiError(
                HTTPStatus.CONFLICT,
                "Stock changed while the order was being processed. Contact support before retrying.",
                "stock_changed",
            )

    def _release_inventory(
        self,
        state: dict[str, Any],
        order: dict[str, Any],
    ) -> bool:
        """Release committed inventory exactly once."""
        committed = order.get("inventoryCommitted")
        if committed is None:
            # Historical COD orders always decremented stock at placement.
            # Do not infer committed inventory for online orders: a signed
            # refund can arrive even when this server missed the capture event.
            committed = order.get("paymentMethod") == "cod"
        if committed is not True:
            return False

        products = self.product_snapshot()
        restored: list[tuple[str, int, int]] = []
        for item in order.get("items", []):
            product = products.get(item.get("productId"))
            if not isinstance(product, dict):
                raise ApiError(HTTPStatus.CONFLICT, "Inventory could not be released safely.", "inventory_release_failed")
            variant = next(
                (entry for entry in product.get("variants", []) if entry.get("id") == item.get("variantId")),
                None,
            )
            quantity = int(item.get("quantity", 0))
            if variant is None or quantity <= 0:
                raise ApiError(HTTPStatus.CONFLICT, "Inventory could not be released safely.", "inventory_release_failed")
            restored.append((variant["id"], self._inventory(state, variant), quantity))

        for variant_id, current, quantity in restored:
            state["inventory"][variant_id] = current + quantity
        order["inventoryCommitted"] = False
        order["inventoryReleasedAt"] = datetime.now(timezone.utc).isoformat()
        return True

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
        """Persist captured financial truth before fulfillment decisions."""

        inventory_alerts: list[dict[str, Any]] = []

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
            if order.get("paymentStatus") in ("paid", "refunded"):
                if order.get("razorpayPaymentId") == payment_id:
                    if payment_id not in state["processedPayments"]:
                        state["processedPayments"][payment_id] = style_order_id
                        self.store.save()
                    return {"success": True, "idempotent": True, "duplicate": True, "order": self._public_order(order)}
                raise ApiError(HTTPStatus.CONFLICT, "This order already has a verified payment.", "duplicate_payment")

            payment_test_order = order.get("isPaymentTestOrder") is True
            inventory_committed = False
            if not payment_test_order:
                inventory_committed = (
                    order.get("inventoryCommitted") is True
                    or self._try_decrement_inventory(
                        state,
                        order["items"],
                        inventory_alerts=inventory_alerts,
                    )
                )

            now = datetime.now(timezone.utc).isoformat()
            if payment_test_order:
                next_status = "payment_test_completed"
                note = f"TEST payment verified by {source}; no fulfillment required"
            elif inventory_committed:
                next_status = "placed"
                note = f"Razorpay payment verified by {source}"
            else:
                next_status = "payment_review_required"
                note = f"Razorpay payment verified by {source}; stock confirmation required; do not request another payment"

            order.update({
                "paymentStatus": "paid",
                "status": next_status,
                "razorpayPaymentId": payment_id,
                "paymentVerifiedAt": now,
                "paymentVerificationSource": source,
                "inventoryCommitted": False if payment_test_order else inventory_committed,
                "updatedAt": now,
            })
            if not payment_test_order and not inventory_committed:
                order["inventoryShortfall"] = True
                order["requiresAdminAttention"] = True
                alert_id = f"inventory_shortfall_after_capture:{style_order_id}"
                state["operationalAlerts"].setdefault(alert_id, {
                    "id": alert_id,
                    "type": "inventory_shortfall_after_capture",
                    "entityId": style_order_id,
                    "razorpayPaymentId": payment_id,
                    "styleDashOrderId": style_order_id,
                    "status": "open",
                    "recordedAt": now,
                })
            else:
                order.pop("inventoryShortfall", None)

            order.setdefault("statusHistory", []).append({"status": next_status, "timestamp": now, "note": note})
            state["processedPayments"][payment_id] = style_order_id
            self.store.save()
            public_order = self._public_order(order)

        # Financial state is already durable and the store lock has
        # been released. Duplicate finalizations return above and
        # therefore never reach this notification.
        _notify_finalized_payment(public_order)

        if inventory_alerts:
            _notify_inventory_alerts(inventory_alerts)

        return {
            "success": True,
            "idempotent": False,
            "duplicate": False,
            "order": public_order,
        }

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
                elif event == "payment.dispute.created":
                    order["paymentDisputed"] = True
                    order["paymentDisputeId"] = entity_id
                order["updatedAt"] = now
            self.store.save()
            return {"duplicate": False, "alert": alert}

    def _record_refund_processed(
        self,
        refund: dict[str, Any],
        payment: dict[str, Any],
        event_id: str | None,
    ) -> dict[str, Any]:
        """Persist signed processed-refund truth without automatic restocking."""
        refund_id = refund.get("id")
        payment_id = refund.get("payment_id")
        amount = refund.get("amount")
        currency = refund.get("currency")
        if not isinstance(refund_id, str) or not refund_id:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Webhook is missing refund information.", "malformed_webhook")
        if not isinstance(payment_id, str) or not payment_id:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Webhook is missing payment information.", "malformed_webhook")
        if payment.get("id") and payment.get("id") != payment_id:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Webhook payment information does not match.", "malformed_webhook")
        if refund.get("status") != "processed":
            raise ApiError(HTTPStatus.BAD_REQUEST, "Webhook refund state is invalid.", "malformed_webhook")
        if isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Webhook refund amount is invalid.", "malformed_webhook")
        if not isinstance(currency, str) or not currency:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Webhook refund currency is invalid.", "malformed_webhook")

        razorpay_order_id = payment.get("order_id") if isinstance(payment.get("order_id"), str) else None
        safe_event_id = self._safe_webhook_event_id(event_id)
        with self.store.lock:
            state = self.store.state
            existing = state["processedRefunds"].get(refund_id)
            if isinstance(existing, dict):
                order_id = existing.get("styleDashOrderId")
                order = state["orders"].get(order_id) if order_id else None
                return {"duplicate": True, "fullRefund": existing.get("fullRefund") is True, "order": self._public_order(order) if order else None}

            order = self._find_order_by_payment_id(payment_id)
            if order is None and razorpay_order_id:
                order = self._find_order_by_razorpay_id(razorpay_order_id)
            relation_matches = order is not None
            if order is not None:
                if order.get("razorpayPaymentId") and order.get("razorpayPaymentId") != payment_id:
                    relation_matches = False
                if razorpay_order_id and order.get("razorpayOrderId") and order.get("razorpayOrderId") != razorpay_order_id:
                    relation_matches = False
            payment_amount = payment.get("amount")
            payment_currency = payment.get("currency")
            cumulative_refunded = payment.get("amount_refunded")
            if isinstance(cumulative_refunded, bool) or not isinstance(
                cumulative_refunded,
                int,
            ):
                cumulative_refunded = None

            if order is not None:
                if (
                    payment_amount is not None
                    and (
                        isinstance(payment_amount, bool)
                        or not isinstance(payment_amount, int)
                        or payment_amount != order.get("amount")
                    )
                ):
                    relation_matches = False
                if (
                    payment_currency is not None
                    and payment_currency != order.get("currency")
                ):
                    relation_matches = False

            full_refund = bool(
                relation_matches
                and order is not None
                and currency == order.get("currency")
                and (
                    amount == order.get("amount")
                    or cumulative_refunded == order.get("amount")
                )
            )

            now = datetime.now(timezone.utc).isoformat()
            style_order_id = order.get("id") if order else None
            alert_type = "refund.processed" if full_refund else "refund.processed_review"
            alert_id = f"{alert_type}:{refund_id}"
            state["operationalAlerts"][alert_id] = {
                "id": alert_id,
                "type": alert_type,
                "entityId": refund_id,
                "razorpayPaymentId": payment_id,
                "styleDashOrderId": style_order_id,
                "status": "open",
                "recordedAt": now,
                "refundAmount": amount,
                "refundCurrency": currency,
            }
            state["processedRefunds"][refund_id] = {
                "styleDashOrderId": style_order_id,
                "razorpayPaymentId": payment_id,
                "amount": amount,
                "currency": currency,
                "fullRefund": full_refund,
                "recordedAt": now,
            }
            if safe_event_id:
                state["processedWebhookEvents"][safe_event_id] = alert_id
            if order is not None:
                order["requiresAdminAttention"] = True
                order["updatedAt"] = now
                if full_refund:
                    order["paymentStatus"] = "refunded"
                    order["razorpayPaymentId"] = payment_id
                    order["refundId"] = refund_id
                    # paymentStatus=refunded means the entire trusted order
                    # amount has been reconciled, even when several partial
                    # refunds made up that total.
                    order["refundAmount"] = order.get("amount")
                    order["refundCurrency"] = currency
                    order["refundProcessedAt"] = now
                    state["processedPayments"].setdefault(payment_id, order["id"])
                    order.setdefault("statusHistory", []).append({
                        "status": order.get("status", "payment_pending"),
                        "timestamp": now,
                        "note": "Razorpay confirmed a full refund; fulfillment state awaits administrator reconciliation",
                    })
            self.store.save()
            return {"duplicate": False, "fullRefund": full_refund, "order": self._public_order(order) if order else None}

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
        if event == "refund.processed":
            refund = self._webhook_entity(payload, "refund")
            payment = self._webhook_entity(payload, "payment")
            result = self._record_refund_processed(refund, payment, event_id)
            order = result.get("order") or {}
            print(
                f"Razorpay webhook event={event} styleOrderId={order.get('id') or '-'} "
                f"refundId={refund.get('id') or '-'} result={'duplicate' if result['duplicate'] else 'recorded'}",
                flush=True,
            )
            if not result["duplicate"]:
                refund_amount = refund.get("amount")
                amount_text = (
                    f"?{refund_amount / 100:.2f}"
                    if isinstance(refund_amount, int)
                    and not isinstance(refund_amount, bool)
                    else "-"
                )
                order_id = order.get("id") or "-"

                if result["fullRefund"]:
                    owner_notifier().send(
                        event="refund_processed",
                        title="Vibe4You Refund Processed",
                        message=(
                            f"Order: {order_id}\n"
                            f"Amount: {amount_text}\n"
                            f"Status: Refunded"
                        ),
                        priority=5,
                        tags=["money_with_wings"],
                    )
                else:
                    owner_notifier().send(
                        event="refund_review_required",
                        title="REFUND NEEDS ATTENTION",
                        message=(
                            f"Order: {order_id}\n"
                            f"Amount: {amount_text}\n"
                            f"Status: Review required"
                        ),
                        priority=5,
                        tags=["rotating_light"],
                    )

            response = {"success": True}
            if result["duplicate"]:
                response["duplicate"] = True
            if not result["fullRefund"]:
                response["reviewRequired"] = True
            return response
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
            if not recorded["duplicate"]:
                order_id = alert.get("styleDashOrderId") or "-"

                if event == "refund.failed":
                    owner_notifier().send(
                        event="refund_failed",
                        title="REFUND NEEDS ATTENTION",
                        message=(
                            f"Order: {order_id}\n"
                            f"Refund reference: ...{entity_id[-8:]}\n"
                            f"Status: Refund failed"
                        ),
                        priority=5,
                        tags=["rotating_light"],
                    )
                else:
                    owner_notifier().send(
                        event="payment_dispute",
                        title="PAYMENT DISPUTE ALERT",
                        message=(
                            f"Order: {order_id}\n"
                            f"Dispute reference: ...{entity_id[-8:]}\n"
                            f"Status: Immediate review required"
                        ),
                        priority=5,
                        tags=["rotating_light"],
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

            if recorded:
                safe_payment_ref = (
                    f"...{payment_id[-8:]}"
                    if isinstance(payment_id, str) and payment_id
                    else "-"
                )

                owner_notifier().send(
                    event="payment_failed",
                    title="Vibe4You Payment Failed",
                    message=(
                        f"Order: {style_order_id}\n"
                        f"Payment reference: {safe_payment_ref}\n"
                        f"Status: Payment failed"
                    ),
                    priority=5,
                    tags=["warning"],
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
        inventory_alerts: list[dict[str, Any]] = []

        with self.store.lock:
            if idempotency_key:
                existing_id = self.store.state["idempotency"].get(
                    f"cod:{idempotency_key}"
                )
                if existing_id:
                    existing = self.store.state["orders"].get(
                        existing_id
                    )
                    if existing:
                        return {
                            "success": True,
                            "idempotent": True,
                            "order": self._public_order(existing),
                        }

            calculated = self.calculate_order(payload)
            now = datetime.now(timezone.utc).isoformat()
            style_order_id = self._new_order_id()

            order = {
                **calculated,
                "id": style_order_id,
                "paymentMethod": "cod",
                "paymentStatus": "pending",
                "status": "placed",
                "inventoryCommitted": True,
                "estimatedDelivery": self.estimated_delivery_label(calculated["deliveryMethod"]),
                "statusHistory": [{
                    "status": "placed",
                    "timestamp": now,
                    "note": "Cash on Delivery order placed",
                }],
                "createdAt": now,
                "updatedAt": now,
            }

            self._decrement_inventory(
                self.store.state,
                order["items"],
                inventory_alerts=inventory_alerts,
            )

            self.store.state["orders"][style_order_id] = order

            if idempotency_key:
                self.store.state["idempotency"][
                    f"cod:{idempotency_key}"
                ] = style_order_id

            self.store.save()
            public_order = self._public_order(order)

        # Inventory and order are both durable before notifying.
        if inventory_alerts:
            _notify_inventory_alerts(inventory_alerts)

        return {
            "success": True,
            "idempotent": False,
            "order": public_order,
        }


class StyleDashRequestHandler(SimpleHTTPRequestHandler):
    payment_service: PaymentService
    product_image_directory: Path
    review_workflow: ReviewWorkflow | None
    rate_limiter = RateLimiter()

    def guess_type(self, path: str) -> str:
        content_type = super().guess_type(path)
        if "charset=" not in content_type and (
            content_type.startswith("text/")
            or content_type in {
                "application/javascript",
                "application/json",
                "application/xml",
                "image/svg+xml",
            }
        ):
            return f"{content_type}; charset=utf-8"
        return content_type

    def end_headers(self) -> None:
        path = urlsplit(self.path).path
        if path.startswith(("/assets/", "/media/product-images/")):
            self.send_header("Cache-Control", "public, max-age=31536000, immutable")
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

    def _binary_response(self, status: int, body: bytes, content_type: str, headers: dict[str, str] | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for name, value in (headers or {}).items(): self.send_header(name, value)
        self.end_headers(); self.wfile.write(body)

    def _text_response(
        self, status: int, body: str, content_type: str, *, head_only: bool = False,
    ) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "public, max-age=300")
        self.end_headers()
        if not head_only:
            self.wfile.write(encoded)

    @staticmethod
    def _public_origin() -> str:
        return os.environ.get("STYLEDASH_PUBLIC_ORIGIN", "").rstrip("/")

    def _product_image_file(self, request_path: str) -> tuple[Path, str] | None:
        match = PRODUCT_IMAGE_ROUTE_PATTERN.fullmatch(request_path)
        if match is None:
            return None
        filename = match.group(1)
        target = (self.product_image_directory / filename).resolve()
        if target.parent != self.product_image_directory.resolve():
            return None
        content_type = {"webp": "image/webp", "jpg": "image/jpeg", "png": "image/png"}[target.suffix.lstrip(".")]
        return target, content_type

    def _serve_product_image(self, request_path: str, *, head_only: bool = False) -> None:
        resolved = self._product_image_file(request_path)
        if resolved is None or not resolved[0].is_file():
            raise ApiError(HTTPStatus.NOT_FOUND, "Image not found.", "not_found")
        target, content_type = resolved
        body = b"" if head_only else target.read_bytes()
        size = target.stat().st_size
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(size))
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def _store_product_image(self, payload: dict[str, Any]) -> dict[str, Any]:
        if set(payload) != {"fileName", "contentType", "dataBase64"}:
            raise SecurityError(400, "Invalid image upload.", "invalid_product_image")
        file_name = payload.get("fileName")
        content_type = payload.get("contentType")
        encoded = payload.get("dataBase64")
        if (
            not isinstance(file_name, str)
            or not 1 <= len(file_name) <= 120
            or "/" in file_name
            or "\\" in file_name
            or any(ord(character) < 32 for character in file_name)
        ):
            raise SecurityError(400, "Invalid image filename.", "invalid_product_image")
        extensions = {"image/webp": "webp", "image/jpeg": "jpg", "image/png": "png"}
        extension = extensions.get(content_type)
        if extension is None or not isinstance(encoded, str) or not encoded:
            raise SecurityError(400, "Upload a JPEG, PNG or WebP image.", "invalid_product_image")
        try:
            content = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError):
            raise SecurityError(400, "Invalid image data.", "invalid_product_image") from None
        if not 32 <= len(content) <= PRODUCT_IMAGE_MAX_BYTES:
            raise SecurityError(413, "The optimized image must be 500 KB or smaller.", "product_image_too_large")
        magic_ok = (
            (content_type == "image/jpeg" and content.startswith(b"\xff\xd8\xff"))
            or (content_type == "image/png" and content.startswith(b"\x89PNG\r\n\x1a\n"))
            or (content_type == "image/webp" and len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP")
        )
        if not magic_ok:
            raise SecurityError(400, "The uploaded file does not match its image type.", "invalid_product_image")
        digest = hashlib.sha256(content).hexdigest()[:32]
        self.product_image_directory.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.product_image_directory, 0o700)
        except OSError:
            pass
        target = self.product_image_directory / f"{digest}.{extension}"
        if not target.exists():
            temporary = self.product_image_directory / f".{digest}.{secrets.token_hex(6)}.tmp"
            temporary.write_bytes(content)
            try:
                os.chmod(temporary, 0o644)
            except OSError:
                pass
            os.replace(temporary, target)
        return {"url": f"/media/product-images/{target.name}", "bytes": len(content), "contentType": content_type}

    def _require_product_image_seller(self) -> dict[str, Any]:
        user, _session = self._current_user()
        self._csrf()
        application = self._shops().get_application(user["id"])
        if not application or application.get("status") not in {"APPROVED", "ACTIVE"}:
            raise SecurityError(403, "An approved shop is required before uploading product images.", "approved_shop_required")
        return user

    def _require_uploaded_store_branding(self, payload: Any) -> None:
        """Reject remote, malformed, or missing media before branding persistence."""
        if not isinstance(payload, dict):
            return
        for field in ("bannerImage", "logoImage"):
            value = payload.get(field)
            if value in (None, ""):
                continue
            if not isinstance(value, str):
                continue
            resolved = self._product_image_file(value)
            if resolved is None or not resolved[0].is_file():
                label = "store cover" if field == "bannerImage" else "store logo"
                raise SecurityError(
                    400,
                    f"Upload a valid {label} image.",
                    "invalid_store_branding",
                )

    def _redirect_to_canonical_host(self) -> bool:
        origin = self._public_origin()
        canonical_host = urlsplit(origin).hostname if origin else None
        request_host = urlsplit(f"//{self.headers.get('Host', '').strip()}").hostname
        if not canonical_host or not request_host:
            return False
        if request_host.lower() in {canonical_host.lower(), "localhost", "127.0.0.1", "::1"}:
            return False
        if urlsplit(self.path).path.startswith(API_PREFIX):
            return False

        request_target = self.path if self.path.startswith("/") else f"/{self.path}"
        self.send_response(HTTPStatus.PERMANENT_REDIRECT)
        self.send_header("Location", f"{origin}{request_target}")
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "public, max-age=300")
        self.end_headers()
        return True

    def _robots_body(self) -> str:
        origin = self._public_origin()
        lines = ["User-agent: *", "Allow: /"]
        if origin:
            lines.append(f"Sitemap: {origin}/sitemap.xml")
        return "\n".join(lines) + "\n"

    def _sitemap_body(self) -> str:
        origin = self._public_origin()
        if not origin:
            raise ApiError(HTTPStatus.SERVICE_UNAVAILABLE, "Sitemap is unavailable.", "sitemap_unavailable")
        paths = [
            "/", "/products", "/categories", "/stores", "/help",
            "/returns", "/privacy", "/terms",
        ]
        product_paths = [
            f"/product/{product['slug']}"
            for product in self.payment_service.product_snapshot().values()
            if product.get("active") is True and isinstance(product.get("slug"), str)
        ]
        urls = paths + sorted(set(product_paths))
        items = "".join(
            f"  <url><loc>{xml_escape(origin + path)}</loc></url>\n"
            for path in urls
        )
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f"{items}</urlset>\n"
        )

    def _error_response(self, error: ApiError) -> None:
        self._json_response(error.status, {"success": False, "error": error.message, "code": error.code})

    def _security_error(self, error: SecurityError) -> None:
        self._json_response(error.status, {"success": False, "error": error.message, "code": error.code})

    def _security(self) -> SecurityStore:
        if self.payment_service.security is None:
            raise SecurityError(HTTPStatus.SERVICE_UNAVAILABLE, "Authentication is unavailable.", "authentication_unavailable")
        return self.payment_service.security

    def _shops(self) -> ShopWorkflow:
        if self.payment_service.shops is None:
            raise SecurityError(
                HTTPStatus.SERVICE_UNAVAILABLE,
                "Shop applications are unavailable.",
                "shop_service_unavailable",
            )
        return self.payment_service.shops

    def _reviews(self) -> ReviewWorkflow:
        if self.review_workflow is None:
            raise SecurityError(HTTPStatus.SERVICE_UNAVAILABLE, "Reviews are unavailable.", "review_service_unavailable")
        return self.review_workflow

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

    def _payment_test_user(self) -> dict[str, Any]:
        try:
            user, _session = self._current_user()
        except SecurityError:
            raise ApiError(HTTPStatus.NOT_FOUND, "Not found.", "not_found") from None
        if not self.payment_service.can_access_payment_test_product(user):
            raise ApiError(HTTPStatus.NOT_FOUND, "Not found.", "not_found")
        return user

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

    def _read_json(self, maximum_bytes: int = MAX_BODY_BYTES) -> dict[str, Any]:
        raw_body = self._read_raw_body(maximum_bytes)
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Malformed JSON request.", "malformed_request") from None
        if not isinstance(payload, dict):
            raise ApiError(HTTPStatus.BAD_REQUEST, "A JSON object is required.", "malformed_request")
        return payload

    def _read_raw_body(self, maximum_bytes: int = MAX_BODY_BYTES) -> bytes:
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
        if length <= 0 or length > maximum_bytes:
            raise ApiError(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "Request body is too large.", "body_too_large")
        return self.rfile.read(length)

    def _rate_limit(self, route: str, limit: int) -> None:
        if not self.rate_limiter.allow(self._client_key(route), limit):
            raise ApiError(HTTPStatus.TOO_MANY_REQUESTS, "Too many requests. Please wait and try again.", "rate_limited")

    def _password_reset_rate_limit(self, payload: dict[str, Any]) -> None:
        """Apply IP and non-plaintext normalized-email limits without disclosure."""
        self._rate_limit("/api/auth/password-reset/request", 5)
        try:
            email = normalize_email(payload.get("email"))
        except SecurityError:
            return
        account_key = f"password-reset-email:{token_hash(email)}"
        if not self.rate_limiter.allow(account_key, 3):
            raise ApiError(HTTPStatus.TOO_MANY_REQUESTS, "Too many requests. Please wait and try again.", "rate_limited")

    def do_GET(self) -> None:  # noqa: N802 - stdlib override name
        parsed = urlsplit(self.path)
        path = parsed.path
        try:
            if self._redirect_to_canonical_host():
                return
            if self._sensitive_path(path):
                self._json_response(HTTPStatus.NOT_FOUND, {"success": False, "error": "Not found.", "code": "not_found"})
                return
            if path.startswith("/media/product-images/"):
                self._serve_product_image(path)
                return
            if path == "/payment-test" or path.startswith("/payment-test/"):
                if path != PAYMENT_TEST_ROUTE:
                    raise ApiError(HTTPStatus.NOT_FOUND, "Not found.", "not_found")
                self._rate_limit(path, 30)
                self._payment_test_user()
                super().do_GET()
                return
            if path == "/robots.txt":
                self._text_response(HTTPStatus.OK, self._robots_body(), "text/plain; charset=utf-8")
                return
            if path == "/sitemap.xml":
                self._text_response(HTTPStatus.OK, self._sitemap_body(), "application/xml; charset=utf-8")
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
            if path == "/api/inventory/availability":
                self._rate_limit(path, 60)
                query = parse_qs(parsed.query, keep_blank_values=True)
                variant_values = query.get("variantId", [])
                product_values = query.get("productId", [])
                variant_id = variant_values[0] if len(variant_values) == 1 else None
                product_ids = product_values or None
                if len(variant_values) > 1:
                    raise ApiError(HTTPStatus.BAD_REQUEST, "Invalid product option.", "invalid_variant")
                self._json_response(
                    HTTPStatus.OK,
                    self.payment_service.public_inventory_availability(variant_id, product_ids),
                )
                return
            if path == "/api/stores/active":
                self._rate_limit(path, 60)
                self._json_response(HTTPStatus.OK, {"success": True, "stores": self._shops().list_active_stores()})
                return
            if path == "/api/shop-products/published":
                self._rate_limit(path, 60)
                products = self._shops().list_published_products()
                live_inventory = self.payment_service.shop_inventory_snapshot(
                    [product["id"] for product in products]
                )
                for product in products:
                    for variant in product.get("variants", []):
                        stock = live_inventory.get(variant["id"])
                        if stock is not None:
                            variant["stock"] = stock
                self._json_response(
                    HTTPStatus.OK,
                    {"success": True, "products": products},
                )
                return
            if path == f"/api/payment-test-product/{PAYMENT_TEST_PRODUCT_SLUG}":
                self._rate_limit(path, 30)
                user = self._payment_test_user()
                self._json_response(HTTPStatus.OK, self.payment_service.payment_test_product(user))
                return
            if path == "/api/reviews":
                self._rate_limit("reviews:list", 120)
                query = parse_qs(parsed.query, keep_blank_values=True)
                product_values = query.get("productId", [])
                sort_values = query.get("sort", ["newest"])
                if len(product_values) != 1 or len(sort_values) != 1:
                    raise SecurityError(400, "Invalid review request.", "invalid_review_request")
                result = self._reviews().list_product(product_values[0], sort_values[0])
                self._json_response(HTTPStatus.OK, {"success": True, **result})
                return
            if path == "/api/reviews/summaries":
                self._rate_limit("reviews:summaries", 240)
                query = parse_qs(parsed.query, keep_blank_values=True)
                product_values = query.get("productId", [])
                result = self._reviews().summaries(product_values)
                self._json_response(HTTPStatus.OK, {"success": True, "summaries": result})
                return
            if path == "/api/reviews/eligibility":
                self._rate_limit("reviews:eligibility", 60)
                user, _session = self._current_user()
                query = parse_qs(parsed.query, keep_blank_values=True)
                product_values = query.get("productId", [])
                if len(product_values) != 1:
                    raise SecurityError(400, "Invalid product.", "invalid_product")
                result = self._reviews().eligibility(self.payment_service.store, user["id"], product_values[0])
                self._json_response(HTTPStatus.OK, {"success": True, **result})
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
                display_orders = [self.payment_service.order_for_display(order) for order in orders]
                self._json_response(HTTPStatus.OK, {"success": True, "orders": display_orders})
                return
            if path == "/api/profile":
                user, _session = self._current_user()
                self._json_response(HTTPStatus.OK, {"success": True, "profile": self._security().profile(user["id"])})
                return
            if path == "/api/vendor-applications/me":
                user, _session = self._current_user()
                self._json_response(
                    HTTPStatus.OK,
                    {"success": True, "application": self._shops().get_application(user["id"])},
                )
                return
            if path == "/api/shop-products":
                user, _session = self._current_user()
                products = self._shops().list_products(user["id"])
                live_inventory = self.payment_service.shop_inventory_snapshot(
                    [product["id"] for product in products if product["status"] == "PUBLISHED"]
                )
                for product in products:
                    for variant in product.get("variants", []):
                        stock = live_inventory.get(variant["id"])
                        if stock is not None:
                            variant["inventory"] = stock
                    if product.get("variants"):
                        product["inventory"] = sum(item["inventory"] for item in product["variants"])
                self._json_response(
                    HTTPStatus.OK,
                    {"success": True, "products": products},
                )
                return
            if path == "/api/shop-product-requests":
                user, _session = self._current_user()
                self._json_response(
                    HTTPStatus.OK,
                    {
                        "success": True,
                        "requests": self._shops().list_product_change_requests(user["id"]),
                    },
                )
                return
            if path.startswith("/api/orders/") and path.endswith("/receipt"):
                user, _session = self._current_user()
                order_id = unquote(path.removeprefix("/api/orders/").removesuffix("/receipt"))
                order = self._security().get_order(self.payment_service.store, order_id, user["id"])
                pdf = self.payment_service.receipt_pdf(order)
                safe_id = re.sub(r"[^A-Za-z0-9_-]+", "-", order_id)[:80] or "order"
                self._binary_response(HTTPStatus.OK, pdf, "application/pdf", {"Content-Disposition": f'attachment; filename="vibe4you-receipt-{safe_id}.pdf"'})
                return
            if path.startswith("/api/orders/"):
                user, _session = self._current_user()
                order_id = unquote(path.removeprefix("/api/orders/"))
                order = self._security().get_order(self.payment_service.store, order_id, user["id"])
                self._json_response(HTTPStatus.OK, {"success": True, "order": self.payment_service.order_for_display(order)})
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
        if self._redirect_to_canonical_host():
            return
        if self._sensitive_path(path):
            self._json_response(HTTPStatus.NOT_FOUND, {"success": False, "error": "Not found.", "code": "not_found"}, head_only=True)
            return
        if path.startswith("/media/product-images/"):
            try:
                self._serve_product_image(path, head_only=True)
            except ApiError as error:
                self._json_response(error.status, {"success": False, "error": error.message, "code": error.code}, head_only=True)
            return
        if path == "/payment-test" or path.startswith("/payment-test/"):
            if path != PAYMENT_TEST_ROUTE:
                self._json_response(HTTPStatus.NOT_FOUND, {"success": False, "error": "Not found.", "code": "not_found"}, head_only=True)
                return
            try:
                self._payment_test_user()
            except (ApiError, SecurityError):
                self._json_response(HTTPStatus.NOT_FOUND, {"success": False, "error": "Not found.", "code": "not_found"}, head_only=True)
                return
            super().do_HEAD()
            return
        if path == "/robots.txt":
            self._text_response(HTTPStatus.OK, self._robots_body(), "text/plain; charset=utf-8", head_only=True)
            return
        if path == "/sitemap.xml":
            try:
                body = self._sitemap_body()
            except ApiError as error:
                self._json_response(error.status, {"success": False, "error": error.message, "code": error.code}, head_only=True)
                return
            self._text_response(HTTPStatus.OK, body, "application/xml; charset=utf-8", head_only=True)
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
            if path == f"/api/payment-test-product/{PAYMENT_TEST_PRODUCT_SLUG}/create-order":
                self._rate_limit(path, 5)
                user = self._payment_test_user()
                self._csrf()
                result = self.payment_service.create_payment_test_order(
                    user,
                    self._read_json(),
                    self.headers.get("Idempotency-Key"),
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

                if not result.get("idempotent"):
                    order = result.get("order") or {}
                    grand_total = order.get("grandTotal")

                    amount_text = (
                        f"?{grand_total}"
                        if isinstance(grand_total, (int, float))
                        and not isinstance(grand_total, bool)
                        else "-"
                    )

                    owner_notifier().send(
                        event="cod_order_placed",
                        title="New Vibe4You Order",
                        message=(
                            f"Order: {order.get('id') or '-'}\n"
                            f"Amount: {amount_text}\n"
                            f"Payment: COD\n"
                            f"Status: Placed"
                        ),
                        priority=5,
                        tags=["shopping_cart"],
                    )

                self._json_response(HTTPStatus.CREATED, result)
                return
            if path == "/api/reviews":
                self._rate_limit("reviews:create", 10)
                user, _session = self._current_user()
                self._csrf()
                review = self._reviews().create(self.payment_service.store, user["id"], self._read_json())
                self._json_response(HTTPStatus.CREATED, {"success": True, "review": review})
                return
            if path.startswith("/api/reviews/") and path.endswith("/edit"):
                self._rate_limit("reviews:edit", 10)
                user, _session = self._current_user()
                self._csrf()
                review_id = unquote(path.removeprefix("/api/reviews/").removesuffix("/edit"))
                if not review_id or "/" in review_id:
                    raise SecurityError(404, "Review not found.", "review_not_found")
                review = self._reviews().edit(user["id"], review_id, self._read_json())
                self._json_response(HTTPStatus.OK, {"success": True, "review": review})
                return
            if path.startswith("/api/reviews/") and path.endswith("/delete"):
                self._rate_limit("reviews:delete", 10)
                user, _session = self._current_user()
                self._csrf()
                review_id = unquote(path.removeprefix("/api/reviews/").removesuffix("/delete"))
                if not review_id or "/" in review_id:
                    raise SecurityError(404, "Review not found.", "review_not_found")
                self._reviews().delete(user["id"], review_id)
                self._json_response(HTTPStatus.OK, {"success": True})
                return
            if path == "/api/auth/register":
                self._rate_limit(path, 5)
                user, raw, csrf = self._security().register(self._read_json())

                owner_notifier().send(
                    event="customer_registered",
                    title="New Vibe4You Registration",
                    message=(
                        f"Name: {user.get('name') or '-'}\n"
                        f"Email: {mask_email(user.get('email') or '')}\n"
                        f"Customer ID: {user.get('id') or '-'}"
                    ),
                    priority=5,
                    tags=["bust_in_silhouette"],
                )

                self._json_response(
                    HTTPStatus.CREATED,
                    {
                        "success": True,
                        "user": user,
                        "csrfToken": csrf,
                    },
                    headers={
                        "Set-Cookie": self._security().cookie(raw)
                    },
                )
                return
            if path == "/api/auth/login":
                self._rate_limit(path, 12)
                user, raw, csrf = self._security().login(self._read_json(), self._client_key("login"))
                self._json_response(HTTPStatus.OK, {"success": True, "user": user, "csrfToken": csrf}, headers={"Set-Cookie": self._security().cookie(raw)})
                return
            if path in ("/api/auth/federated/google", "/api/auth/federated/phone"):
                self._rate_limit(path, 10)
                provider = "google" if path.endswith("google") else "phone"
                user, raw, csrf, created = self._security().federated_session(provider, self._read_json())

                if created:
                    contact = (
                        f"Email: {mask_email(user.get('email') or '')}"
                        if provider == "google"
                        else f"Mobile: {mask_phone(user.get('phone') or '')}"
                    )
                    owner_notifier().send(
                        event="customer_registered",
                        title="New Vibe4You Registration",
                        message=(
                            f"Name: {user.get('name') or '-'}\n"
                            f"{contact}\n"
                            f"Method: {'Google' if provider == 'google' else 'Mobile OTP'}\n"
                            f"Customer ID: {user.get('id') or '-'}"
                        ),
                        priority=5,
                        tags=["bust_in_silhouette"],
                    )

                self._json_response(
                    HTTPStatus.OK if not created else HTTPStatus.CREATED,
                    {
                        "success": True,
                        "user": user,
                        "csrfToken": csrf,
                        "needsProfile": bool(user.get("needsProfile")),
                    },
                    headers={"Set-Cookie": self._security().cookie(raw)},
                )
                return
            if path in (
                "/api/auth/federated/google/link",
                "/api/auth/federated/phone/link",
                "/api/auth/federated/link/google",
                "/api/auth/federated/link/phone",
            ):
                self._rate_limit(path, 10)
                raw = self._session_token()
                self._security().verify_csrf(raw, self.headers.get("X-CSRF-Token"))
                provider = "google" if "/google" in path else "phone"
                profile = self._security().link_federated_identity(
                    raw or "", provider, self._read_json()
                )
                self._json_response(HTTPStatus.OK, {"success": True, "profile": profile})
                return
            if path == "/api/auth/password-reset/request":
                payload = self._read_json()
                self._password_reset_rate_limit(payload)
                self._security().request_password_reset(payload)
                self._json_response(HTTPStatus.OK, {"success": True, "message": "If an account exists, reset instructions will be sent shortly."})
                return
            if path == "/api/auth/password-reset/confirm":
                self._rate_limit(path, 10)
                self._security().confirm_password_reset(self._read_json())
                self._json_response(HTTPStatus.OK, {"success": True, "message": "Your password has been reset. Please sign in."})
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
                vendor_payload = self._read_json()
                legacy_submit = "email" in vendor_payload or "phone" in vendor_payload
                safe_payload = {
                    key: value
                    for key, value in vendor_payload.items()
                    if key not in {"email", "phone"}
                }
                if "storeName" in safe_payload and "shopName" not in safe_payload:
                    safe_payload["shopName"] = safe_payload.pop("storeName")
                if legacy_submit:
                    # The original form represented an immediate submission
                    # and was Neemuch-only. Preserve that behavior while the
                    # new UI uses explicit draft + submit endpoints.
                    safe_payload.setdefault("city", "Neemuch")
                    safe_payload.setdefault("state", "Madhya Pradesh")
                result = self._shops().create_draft(user["id"], safe_payload)
                if legacy_submit:
                    result = self._shops().submit_application(user["id"])
                    owner_notifier().send(
                        event="vendor_application",
                        title="New Vendor Application",
                        message=(
                            f"Application: {result.get('id') or '-'}\n"
                            f"Store: {' '.join(str(result.get('shopName') or '-').split())[:100]}\n"
                            f"Category: {' '.join(str(result.get('category') or '-').split())[:80]}\n"
                            "Status: Submitted"
                        ),
                        priority=5,
                        tags=["briefcase"],
                    )
                self._json_response(
                    HTTPStatus.CREATED,
                    {"success": True, "application": result},
                )
                return
            if path == "/api/vendor-applications/me/submit":
                self._rate_limit(path, 5)
                user, _session = self._current_user()
                self._csrf()
                result = self._shops().submit_application(user["id"])
                owner_notifier().send(
                    event="vendor_application",
                    title="New Vendor Application",
                    message=(
                        f"Application: {result.get('id') or '-'}\n"
                        f"Store: {' '.join(str(result.get('shopName') or '-').split())[:100]}\n"
                        f"Category: {' '.join(str(result.get('category') or '-').split())[:80]}\n"
                        "Status: Submitted"
                    ),
                    priority=5,
                    tags=["briefcase"],
                )
                self._json_response(
                    HTTPStatus.OK, {"success": True, "application": result}
                )
                return
            if path in {"/api/shop-product-images", "/api/shop-branding-images"}:
                self._rate_limit(path, 8)
                self._require_product_image_seller()
                image = self._store_product_image(self._read_json(PRODUCT_IMAGE_REQUEST_MAX_BYTES))
                self._json_response(HTTPStatus.CREATED, {"success": True, "image": image})
                return
            if path == "/api/shop-products":
                self._rate_limit(path, 10)
                user, _session = self._current_user()
                self._csrf()
                result = self._shops().create_product_draft(user["id"], self._read_json())
                self._json_response(
                    HTTPStatus.CREATED, {"success": True, "product": result}
                )
                return
            if path.startswith("/api/shop-products/") and path.endswith("/submit"):
                self._rate_limit("/api/shop-products/submit", 10)
                user, _session = self._current_user()
                self._csrf()
                product_id = unquote(
                    path.removeprefix("/api/shop-products/").removesuffix("/submit")
                )
                if not product_id or "/" in product_id:
                    raise SecurityError(404, "Product submission not found.", "product_not_found")
                result = self._shops().submit_product(user["id"], product_id)
                self._json_response(
                    HTTPStatus.OK, {"success": True, "product": result}
                )
                return
            if path.startswith("/api/shop-products/") and path.endswith("/edit-request"):
                self._rate_limit("/api/shop-products/edit-request", 10)
                user, _session = self._current_user()
                self._csrf()
                product_id = unquote(
                    path.removeprefix("/api/shop-products/").removesuffix("/edit-request")
                )
                if not product_id or "/" in product_id:
                    raise SecurityError(404, "Product submission not found.", "product_not_found")
                live_inventory = self.payment_service.shop_inventory_snapshot([product_id])
                result = self._shops().create_product_edit_request(
                    user["id"], product_id, self._read_json(), live_inventory
                )
                self._json_response(
                    HTTPStatus.CREATED, {"success": True, "request": result}
                )
                return
            if path.startswith("/api/shop-products/") and path.endswith("/unpublish-request"):
                self._rate_limit("/api/shop-products/unpublish-request", 10)
                user, _session = self._current_user()
                self._csrf()
                product_id = unquote(
                    path.removeprefix("/api/shop-products/").removesuffix("/unpublish-request")
                )
                if not product_id or "/" in product_id:
                    raise SecurityError(404, "Product submission not found.", "product_not_found")
                payload = self._read_json()
                if payload:
                    raise SecurityError(
                        400,
                        "Unpublish requests do not accept product fields.",
                        "invalid_product_change",
                    )
                result = self._shops().create_product_unpublish_request(
                    user["id"], product_id
                )
                self._json_response(
                    HTTPStatus.CREATED, {"success": True, "request": result}
                )
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

    def do_OPTIONS(self) -> None:  # noqa: N802 - stdlib override name
        self.do_PUT()

    def do_TRACE(self) -> None:  # noqa: N802 - stdlib override name
        self.do_PUT()

    def do_DELETE(self) -> None:  # noqa: N802 - stdlib override name
        self.do_PUT()

    def do_PATCH(self) -> None:  # noqa: N802 - stdlib override name
        path = urlsplit(self.path).path
        try:
            if self._sensitive_path(path):
                self._json_response(HTTPStatus.NOT_FOUND, {"success": False, "error": "Not found.", "code": "not_found"})
                return
            if path == "/api/profile":
                self._rate_limit(path, 30)
                user, _session = self._current_user()
                self._csrf()
                profile = self._security().update_profile(user["id"], self._read_json())
                self._json_response(HTTPStatus.OK, {"success": True, "profile": profile})
                return
            if path == "/api/vendor-applications/me/branding":
                self._rate_limit(path, 20)
                user, _session = self._current_user()
                self._csrf()
                payload = self._read_json()
                self._require_uploaded_store_branding(payload)
                application = self._shops().update_store_branding(user["id"], payload)
                self._json_response(
                    HTTPStatus.OK, {"success": True, "application": application}
                )
                return
            if path == "/api/vendor-applications/me":
                self._rate_limit(path, 20)
                user, _session = self._current_user()
                self._csrf()
                application = self._shops().update_draft(user["id"], self._read_json())
                self._json_response(
                    HTTPStatus.OK, {"success": True, "application": application}
                )
                return
            if path.startswith("/api/shop-products/") and path.endswith("/stock"):
                self._rate_limit("/api/shop-products/stock", 30)
                user, _session = self._current_user()
                self._csrf()
                product_id = unquote(
                    path.removeprefix("/api/shop-products/").removesuffix("/stock")
                )
                if not product_id or "/" in product_id:
                    raise SecurityError(404, "Product submission not found.", "product_not_found")
                payload = self._read_json()
                if not isinstance(payload, dict) or set(payload) not in ({"stock"}, {"variantId", "stock"}):
                    raise SecurityError(
                        400,
                        "Provide the new stock value and, for multi-size products, its variantId.",
                        "invalid_inventory_adjustment",
                    )
                self._shops().require_seller_stock_update_allowed(user["id"], product_id)
                inventory = self.payment_service.set_shop_inventory(
                    product_id, payload.get("stock"), payload.get("variantId")
                )
                self._json_response(
                    HTTPStatus.OK, {"success": True, "inventory": inventory}
                )
                return
            if path.startswith("/api/shop-products/"):
                self._rate_limit("/api/shop-products", 20)
                user, _session = self._current_user()
                self._csrf()
                product_id = unquote(path.removeprefix("/api/shop-products/"))
                if not product_id or "/" in product_id:
                    raise SecurityError(404, "Product submission not found.", "product_not_found")
                product = self._shops().update_product_draft(
                    user["id"], product_id, self._read_json()
                )
                self._json_response(HTTPStatus.OK, {"success": True, "product": product})
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
        decoded = unquote(path).replace("\\", "/")
        lowered = ("/" + posixpath.normpath(decoded).lstrip("/")).casefold()
        return (
            lowered.startswith(("/backups/", "/logs/", "/.config/", "/admin", "/api/admin/", "/api/internal-admin/", "/admin-api/"))
            or lowered.startswith(("/tools/", "/payment-data/"))
            or lowered in ("/.env", "/secrets.env", "/styledash.db", "/firebase-service-account.json", "/serve.py", "/styledash_security.py")
            or lowered.endswith((".db", ".db-wal", ".db-shm", ".log", ".py", ".pyc"))
        )

    def log_message(self, format: str, *args: Any) -> None:
        # Request bodies and environment configuration are never logged. Redact
        # token-shaped query parameters as defense in depth for stale/manual URLs.
        redacted = tuple(
            ACCESS_LOG_TOKEN_PATTERN.sub(r"\1[redacted]", value)
            if isinstance(value, str)
            else value
            for value in args
        )
        super().log_message(format, *redacted)


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
    delivery_queue: PasswordResetDeliveryQueue | None = None
    if service is None:
        encryption_key = os.environ.get("STYLEDASH_TOTP_ENCRYPTION_KEY", "").strip()
        if not encryption_key:
            raise RuntimeError("STYLEDASH_TOTP_ENCRYPTION_KEY is required")
        database_path = Path(
            os.environ.get("STYLEDASH_DATABASE_PATH", str(data_directory.parent / "styledash.db"))
        ).resolve()
        mailer = SmtpPasswordResetSender.from_environment()
        delivery_queue = PasswordResetDeliveryQueue(mailer) if mailer is not None else None
        security_store = SecurityStore(
            database_path,
            encryption_key,
            password_reset_dispatcher=delivery_queue.dispatch if delivery_queue is not None else None,
        )
        payment_service = PaymentService(
            catalog_path, settings_path, data_directory, security_store=security_store
        )
    else:
        payment_service = service
    class BoundStyleDashRequestHandler(StyleDashRequestHandler):
        pass

    data_root = data_directory.parent if data_directory.name == "runtime" else data_directory
    product_image_directory = (data_root / "product-images").resolve()
    product_image_directory.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(product_image_directory, 0o700)
    except OSError:
        pass
    BoundStyleDashRequestHandler.payment_service = payment_service
    BoundStyleDashRequestHandler.product_image_directory = product_image_directory
    BoundStyleDashRequestHandler.review_workflow = (
        ReviewWorkflow(payment_service.security.path) if payment_service.security is not None else None
    )
    BoundStyleDashRequestHandler.rate_limiter = RateLimiter()
    handler = partial(BoundStyleDashRequestHandler, directory=str(directory))
    server = ThreadingHTTPServer((bind, port), handler)
    if service is None and delivery_queue is not None:
        original_server_close = server.server_close

        def close_server() -> None:
            delivery_queue.close()
            original_server_close()

        server.server_close = close_server  # type: ignore[method-assign]
    return server


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
    print(f"Serving Vibe4You at http://{args.bind}:{args.port}", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
