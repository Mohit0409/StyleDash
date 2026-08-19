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
import threading
from typing import Any


class FirebaseUnavailable(Exception):
    """Raised when Firebase Admin credentials/SDK are not configured."""


class FirebaseTokenInvalid(Exception):
    """Raised for any verification failure. Message is deliberately generic."""


_lock = threading.Lock()
_app: Any = None


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
        credential_path = os.environ.get("STYLEDASH_FIREBASE_CREDENTIALS", "").strip()
        project_id = os.environ.get("STYLEDASH_FIREBASE_PROJECT_ID", "").strip()
        if not credential_path or not project_id:
            raise FirebaseUnavailable("Firebase Admin credentials are not configured")
        try:
            cred = credentials.Certificate(credential_path)
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
