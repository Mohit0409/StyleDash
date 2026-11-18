"""Fail-closed GST Phase 1 registry for twelve owner-approved Casio watches.

This is deliberately an exact product-ID allowlist.  It never classifies a
product from its category, brand, name fragment, seller metadata, or browser
payload.  The pinned identity fields prevent a recycled product ID from
silently inheriting an old tax classification.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import MappingProxyType
from typing import Any


POLICY_ID = "gst-phase1-casio-watch-9102-v1"
OWNER_APPROVAL_DATE = "2026-10-24"
RATE_EFFECTIVE_FROM = "2025-09-22"
OFFICIAL_SOURCE = (
    "CBIC Notification No. 09/2025-Integrated Tax (Rate), effective "
    "2025-09-22; HSN 9102 conventional wrist-watches; GST 18%"
)
GST_RATE = Decimal("18")
HSN_CODE = "9102"


_APPROVED_IDENTITIES = {
    "shopprod_1507cb213bf775842ae2fad2": ("Casio Vintage A158WA - Blue", "casio"),
    "shopprod_183096bb0658765e0141da2a": ("Casio F-91W Black Green Digital Watch", "casio"),
    "shopprod_2b1efe9e84eba0f8b24e3598": ("Casio Vintage A158WA - Black", "casio"),
    "shopprod_37779dd646fccc94b0e3b777": ("Casio F-91W - Green", "casio"),
    "shopprod_5444942086d2a14b04b6c01d": ("Casio F-91W - Rosegold", "casio"),
    "shopprod_72f3567efee25c71955b610f": ("Casio F-91W - Black Gold", "casio"),
    "shopprod_7fdb84f9f0febc112ffc25f4": ("Casio F-91W - Black", "casio"),
    "shopprod_91219ce9c0133880cfc1339d": ("Casio F-91W - Blue", "casio"),
    "shopprod_91f977ea7ca0d30394704338": ("Casio F-91W - Bio Blue", "casio"),
    "shopprod_ae22bb23b2f524dd2ce14ac0": ("Casio F-91W - Grey", "casio"),
    "shopprod_ca08d5013accf705112bce13": ("Casio F-91W - Golden", "casio"),
    "shopprod_d625456ab326720660b964f0": ("Casio F-91W - Silver", "casio"),
}
APPROVED_PRODUCT_IDS = frozenset(_APPROVED_IDENTITIES)
APPROVED_IDENTITIES = MappingProxyType(_APPROVED_IDENTITIES)


class GstPhase1ClassificationError(ValueError):
    """The product is outside the approved scope or its identity has drifted."""


def classification_for_product(
    product: dict[str, Any], *, as_of: date | None = None
) -> dict[str, str]:
    """Return the immutable Phase 1 tax snapshot or fail closed.

    ``product`` must be the server-authoritative catalogue object.  Caller data
    must never be passed here as a substitute.
    """
    product_id = str(product.get("id") or "")
    expected = APPROVED_IDENTITIES.get(product_id)
    if expected is None:
        raise GstPhase1ClassificationError("product is not in the GST Phase 1 allowlist")

    expected_name, expected_brand = expected
    actual_name = str(product.get("name") or "").strip()
    actual_brand = str(product.get("brand") or "").strip().casefold()
    actual_category = str(product.get("category") or "").strip()
    actual_subcategory = str(product.get("subcategory") or "").strip()
    if (
        actual_name != expected_name
        or actual_brand != expected_brand
        or actual_category != "Accessories"
        or actual_subcategory != "Watches"
    ):
        raise GstPhase1ClassificationError("approved product identity no longer matches")

    effective = date.fromisoformat(RATE_EFFECTIVE_FROM)
    if effective > (as_of or date.today()):
        raise GstPhase1ClassificationError("approved GST rate is not effective yet")

    return {
        "policyId": POLICY_ID,
        "productId": product_id,
        "hsnCode": HSN_CODE,
        "gstRate": str(GST_RATE),
        "supplyType": "taxable",
        "priceTreatment": "GST_INCLUSIVE",
        "effectiveFrom": RATE_EFFECTIVE_FROM,
        "approvedBy": "Vibe4You owner",
        "approvedOn": OWNER_APPROVAL_DATE,
        "evidence": OFFICIAL_SOURCE,
    }
