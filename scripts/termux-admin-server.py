#!/usr/bin/env python3
"""Loopback-only StyleDash administrator UI/API. Never tunnel through ngrok."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
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


class AdminApplication:
    def __init__(self, database: Path, encryption_key: str, catalog: Path, settings: Path, data_dir: Path) -> None:
        public = load_public_module()
        self.identity = AdminStore(database, encryption_key)
        self.payments = public.PaymentService(
            catalog, settings, data_dir, key_id="", key_secret="", webhook_secret="",
            mode=os.environ.get("RAZORPAY_MODE", "test"), gateway=None,
        )

    def list_orders(self, query: str = "") -> list[dict[str, Any]]:
        needle = query.strip().casefold()[:100]
        with self.payments.store.lock:
            orders = list(self.payments.store.state["orders"].values())
            if needle:
                orders = [order for order in orders if needle in str(order.get("id", "")).casefold()]
            return [dict(order) for order in sorted(orders, key=lambda item: item.get("createdAt", ""), reverse=True)[:250]]

    def get_order(self, order_id: str) -> dict[str, Any]:
        with self.payments.store.lock:
            order = self.payments.store.state["orders"].get(order_id)
            if order is None:
                raise SecurityError(404, "Order not found.", "order_not_found")
            return dict(order)

    def update_order_status(self, admin_id: str, order_id: str, requested: Any) -> dict[str, Any]:
        transitions = {
            "placed": {"confirmed", "cancelled"},
            "confirmed": {"preparing", "packed", "cancelled"},
            "preparing": {"out_for_delivery", "cancelled"},
            "packed": {"out_for_delivery", "cancelled"},
            "out_for_delivery": {"delivered"},
            "delivered": set(), "cancelled": set(),
        }
        if not isinstance(requested, str):
            raise SecurityError(400, "Invalid order status.", "invalid_status")
        with self.payments.store.lock:
            order = self.payments.store.state["orders"].get(order_id)
            if order is None:
                raise SecurityError(404, "Order not found.", "order_not_found")
            current = order.get("status", "placed")
            if requested not in transitions.get(current, set()):
                raise SecurityError(409, "Invalid order status transition.", "invalid_transition")
            now = iso(utc_now())
            order["status"] = requested
            order["updatedAt"] = now
            order.setdefault("statusHistory", []).append({"status": requested, "timestamp": now, "note": "Updated by local administrator"})
            self.payments.store.save()
            result = dict(order)
        self.identity.record_action(admin_id, "order_status", "order", order_id, "success", {"from": current, "to": requested})
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

    def adjust_inventory(self, admin_id: str, variant_id: str, delta: Any) -> dict[str, Any]:
        if isinstance(delta, bool) or not isinstance(delta, int) or delta == 0 or not -10000 <= delta <= 10000:
            raise SecurityError(400, "Inventory adjustment must be a non-zero whole number.", "invalid_inventory_adjustment")
        variant = None
        product = None
        for item in self.payments.products.values():
            match = next((candidate for candidate in item["variants"] if candidate["id"] == variant_id), None)
            if match:
                variant, product = match, item
                break
        if variant is None or product is None:
            raise SecurityError(404, "Product variant not found.", "variant_not_found")
        with self.payments.store.lock:
            before = self.payments._inventory(self.payments.store.state, variant)
            after = before + delta
            if after < 0:
                raise SecurityError(409, "Inventory cannot become negative.", "negative_inventory")
            self.payments.store.state["inventory"][variant_id] = after
            self.payments.store.save()
        self.identity.record_action(admin_id, "inventory_adjustment", "product_variant", variant_id, "success", {"delta": delta, "before": before, "after": after})
        return {"productId": product["id"], "variantId": variant_id, "before": before, "after": after}

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
                self._admin(); query = self._query().get("q", [""])[0]
                self._json(200, {"success": True, "orders": self.application.list_orders(query)}); return
            if path.startswith("/api/admin/orders/"):
                self._admin(); order_id = unquote(path.removeprefix("/api/admin/orders/"))
                self._json(200, {"success": True, "order": self.application.get_order(order_id)}); return
            if path == "/api/admin/vendors":
                self._admin(); self._json(200, {"success": True, "applications": self.application.identity.vendor_applications()}); return
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
            if path.startswith("/api/admin/orders/") and path.endswith("/status"):
                order_id = unquote(path.removeprefix("/api/admin/orders/").removesuffix("/status"))
                result = self.application.update_order_status(admin["id"], order_id, payload.get("status"))
                self._json(200, {"success": True, "order": result}); return
            if path.startswith("/api/admin/vendors/"):
                application_id = unquote(path.removeprefix("/api/admin/vendors/"))
                result = self.application.identity.review_vendor(admin["id"], application_id, payload.get("status"))
                self._json(200, {"success": True, "application": result}); return
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
