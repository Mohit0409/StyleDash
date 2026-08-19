"""Firebase ID token verification used only as an external identity check.

StyleDash never treats Firebase as the authorization source for orders,
payments, inventory, refunds, or admin actions. This module's sole job is to
cryptographically verify a Google/Phone Firebase ID token (signature, issuer,
audience/project, expiry, and — best effort — revocation) before
``styledash_security.SecurityStore.federated_session`` creates StyleDash's own
server-side session. Verification failures are never distinguished to
callers; see ``FirebaseTokenInvalid``.

Configuration (production secrets, never committed):

  STYLEDASH_FIREBASE_PROJECT_ID   Firebase project ID (e.g. styledash-auth)
  STYLEDASH_FIREBASE_CREDENTIALS  Absolute path to the service-account JSON
                                  file, mode 600, outside the repository
                                  (e.g. ~/.config/styledash/firebase-admin.json)
"""

from __future__ import annotations

import os
import json
import stat
import threading
from pathlib import Path
from typing import Any


class FirebaseUnavailable(Exception):
    """Raised when Firebase Admin credentials/SDK are not configured."""


class FirebaseTokenInvalid(Exception):
    """Raised for any verification failure. Message is deliberately generic."""


_lock = threading.Lock()
_app: Any = None


def validate_firebase_runtime_config(home: Path | None = None) -> tuple[str, Path]:
    """Return the project and credential path only when private storage is safe."""
    project_id = os.environ.get("STYLEDASH_FIREBASE_PROJECT_ID", "").strip()
    credential_value = os.environ.get("STYLEDASH_FIREBASE_CREDENTIALS", "").strip()
    if not project_id or not credential_value:
        raise FirebaseUnavailable("Firebase Admin credentials are not configured")

    raw_credential = Path(credential_value)
    if not raw_credential.is_absolute():
        raise FirebaseUnavailable("Firebase Admin credentials are not in private storage")

    try:
        home_root = (home or Path.home()).resolve(strict=True)
        private_root = home_root / ".config" / "styledash"
        if private_root.resolve(strict=True) != private_root or not private_root.is_dir():
            raise FirebaseUnavailable("Firebase Admin credentials are not in private storage")
        credential_path = raw_credential.resolve(strict=True)
        credential_path.relative_to(private_root)
    except (OSError, RuntimeError, ValueError) as exc:
        raise FirebaseUnavailable("Firebase Admin credentials are not in private storage") from exc

    private_stat = private_root.stat()
    credential_stat = credential_path.stat()
    if not stat.S_ISDIR(private_stat.st_mode) or not stat.S_ISREG(credential_stat.st_mode):
        raise FirebaseUnavailable("Firebase Admin credentials have unsafe ownership or permissions")
    if os.name == "posix" and (
        stat.S_IMODE(private_stat.st_mode) != 0o700
        or private_stat.st_uid != os.getuid()
        or stat.S_IMODE(credential_stat.st_mode) != 0o600
        or credential_stat.st_uid != os.getuid()
    ):
        raise FirebaseUnavailable("Firebase Admin credentials have unsafe ownership or permissions")

    try:
        with credential_path.open("r", encoding="utf-8") as handle:
            credential_data = json.load(handle)
    except (OSError, ValueError) as exc:
        raise FirebaseUnavailable("Firebase Admin credentials are invalid") from exc
    if not isinstance(credential_data, dict) or credential_data.get("project_id") != project_id:
        raise FirebaseUnavailable("Firebase Admin project configuration does not match")
    return project_id, credential_path


def _initialize_app() -> Any:
    global _app
    if _app is not None:
        return _app
    with _lock:
        if _app is not None:
            return _app
        try:
            import firebase_admin
            from firebase_admin import credentials
        except ImportError as exc:
            raise FirebaseUnavailable("firebase-admin is not installed") from exc
        project_id, credential_path = validate_firebase_runtime_config()
        try:
            cred = credentials.Certificate(str(credential_path))
            _app = firebase_admin.initialize_app(cred, {"projectId": project_id})
        except Exception as exc:  # noqa: BLE001 - collapsed into one generic failure mode
            raise FirebaseUnavailable("Firebase Admin failed to initialize") from exc
        return _app


def verify_firebase_id_token(id_token: str) -> dict[str, Any]:
    """Verify signature, issuer, audience/project, expiry, and revocation."""
    if not isinstance(id_token, str) or not 20 <= len(id_token) <= 4096:
        raise FirebaseTokenInvalid("malformed token")
    app = _initialize_app()
    from firebase_admin import auth as firebase_auth

    try:
        claims = firebase_auth.verify_id_token(id_token, app=app, check_revoked=True)
    except Exception as exc:  # noqa: BLE001 - never leak which check failed
        raise FirebaseTokenInvalid("token verification failed") from exc
    if not isinstance(claims, dict):
        raise FirebaseTokenInvalid("token verification failed")
    return claims


def reset_app_for_tests() -> None:
    """Test-only hook to force re-initialization between isolated test cases."""
    global _app
    _app = None
