#!/usr/bin/env python3
"""Cloud-safe daily read-only price/MRP audit of publicly published Vibe4You products."""
from __future__ import annotations

import json
import math
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

CATALOGUE_URL = "https://vibe4you.in/api/shop-products/published"
OUT = Path("qa-results/ci-public-catalogue.json")
MAX_BYTES = 10_000_000


def catalogue_metrics(payload: object) -> dict:
    """Analyze public data without retaining names, IDs, or pricing per item."""
    if not isinstance(payload, dict) or payload.get("success") is not True:
        raise ValueError("Published catalogue returned unsuccessful or invalid JSON")
    products = payload.get("products")
    if not isinstance(products, list) or not products:
        raise ValueError("Published catalogue array is missing or empty")
    if len(products) > 50_000:
        raise ValueError("Unexpected catalogue size")
    ids, slugs = [], []
    missing_or_bad_price = 0
    over_mrp = 0
    inactive = 0
    for product in products:
        if not isinstance(product, dict):
            raise ValueError("Non-object product returned")
        ids.append(product.get("id"))
        slugs.append(product.get("slug"))
        price, mrp = product.get("price"), product.get("originalPrice")
        if (type(price) not in (int,float) or type(mrp) not in (int,float)
            or not math.isfinite(price) or not math.isfinite(mrp)
            or price < 0 or mrp <= 0):
            missing_or_bad_price += 1
        elif price > mrp + 0.001:
            over_mrp += 1
        if product.get("active") is not True:
            inactive += 1
    valid_ids = all(isinstance(x,str) and x.strip() for x in ids)
    valid_slugs = all(isinstance(x,str) and x.strip() for x in slugs)
    duplicates = ((len(ids)-len(set(ids))) if valid_ids else len(ids))
    duplicates += ((len(slugs)-len(set(slugs))) if valid_slugs else len(slugs))
    return {"published_products": len(products),
            "price_above_mrp": over_mrp,
            "missing_or_invalid_price_mrp": missing_or_bad_price,
            "duplicate_or_invalid_ids_slugs": duplicates,
            "not_active": inactive,
            "passed": all(x == 0 for x in (over_mrp, missing_or_bad_price, duplicates, inactive))}


def audit():
    req = urllib.request.Request(
        CATALOGUE_URL, headers={"User-Agent":"Vibe4You-Scheduled-ReadOnly-Catalogue-Audit/1.0",
                                "Accept":"application/json"}, method="GET")
    with urllib.request.urlopen(req,timeout=25) as resp:
        if resp.status!=200 or resp.geturl()!=CATALOGUE_URL:
            raise ValueError("Unexpected catalogue status or redirect")
        if "json" not in resp.headers.get("content-type",""):
            raise ValueError("Catalogue response not JSON")
        body=resp.read(MAX_BYTES+1)
        if len(body)>MAX_BYTES:
            raise ValueError("Catalogue size limit exceeded")
    metrics=catalogue_metrics(json.loads(body))
    return {"created_at":datetime.now(timezone.utc).isoformat(),
            "scope":"public catalog GET aggregate-only, no writes",
            "endpoint":CATALOGUE_URL,
            "metrics":metrics,
            "passed":metrics["passed"],
            "limitations":"API MRP comparison only; cannot independently validate printed MRP or checkout totals."}


def main():
    try:
        result=audit()
    except Exception as exc:
        result={"created_at":datetime.now(timezone.utc).isoformat(),
                "scope":"public catalog GET aggregate-only, no writes",
                "endpoint":CATALOGUE_URL,
                "passed":False,"reason":type(exc).__name__}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,indent=2))
    return 0 if result["passed"] else 2


if __name__=="__main__":
    sys.exit(main())
