#!/usr/bin/env python3
"""Read-only Vibe4You isolated-staging API contracts.

No credentials, cookies, payment actions, order creation, or data writes.
All URLs must be exact loopback origin; staging marker must match, otherwise fail closed.
This is evidence about the isolated staging dataset, not customer production integrity.
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone

IDENTITY_PATH = "/vibe4you-regression-staging-identity.txt"
IDENTITY = "VIBE4YOU_ISOLATED_STAGING_TEST_ONLY_20261016"
BASE = "http://127.0.0.1:41891"
ALLOWED = {
    IDENTITY_PATH, "/api/health", "/api/shop-products/published",
    "/api/shop-products/homepage", "/api/inventory/availability",
    "/api/orders", "/api/auth/me", "/robots.txt", "/sitemap.xml",
}
MAX_BYTES = 5_000_000

def request(path: str):
    if path not in ALLOWED:
        raise ValueError("Path not allowlisted")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    url = BASE + path
    req = urllib.request.Request(url, method="GET",
        headers={"User-Agent":"Vibe4You-Isolated-Staging-Contract/1.0","Accept":"application/json,text/plain,application/xml"})
    start = time.monotonic()
    try:
        resp = opener.open(req, timeout=13)
    except urllib.error.HTTPError as exc:
        resp = exc
    with resp:
        if resp.geturl() != url:
            raise RuntimeError("Redirect detected; fail closed")
        body = resp.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            raise RuntimeError("Excessive response size")
        return resp.status, body, round((time.monotonic()-start)*1000)

def fetch_json(path):
    status, body, ms = request(path)
    try: parsed = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        parsed = None
    return status, parsed, ms

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    a = parser.parse_args()
    result = {"created_at":datetime.now(timezone.utc).isoformat(),
              "scope":"isolated staging anonymous read-only API contracts",
              "identity": "isolated-staging-only",
              "checks":[], "limits":[
                "No admin, authenticated, checkout, payment, or mutating API exercised.",
                "Pricing audit compares published customer price with originalPrice; flagged records require fixture and business-rule investigation.",
                "This does not prove complete production pricing or transaction behavior.",
              ]}
    def check(name, status, detail, evidence=None):
        item = {"id":"contract."+name, "section":"Staging API contracts",
                "title":name.replace("_"," ").capitalize(), "status":status,
                "detail":str(detail)[:430],"origin":"Isolated staging API contract"}
        if evidence is not None: item["evidence"]=evidence
        result["checks"].append(item)
        print(f"[{status}] {item['id']}: {item['detail']}", flush=True)
    try:
        status, body, ms = request(IDENTITY_PATH)
        if status != 200 or body.strip().decode("utf-8") != IDENTITY:
            raise RuntimeError("Positive isolated staging identity mismatch")
        check("staging_identity", "PASS", "Dedicated marker matches; this marker is absent from production", {"ms":ms})
        status, health, ms = fetch_json("/api/health")
        ok = status==200 and isinstance(health,dict) and health.get("status")=="ok" and health.get("database")=="ok"
        check("health_database", "PASS" if ok else "FAIL",
              "Health and DB status ok" if ok else "Staging or database health not healthy", {"ms":ms})
        status, pub, ms = fetch_json("/api/shop-products/published")
        published=pub.get("products") if isinstance(pub,dict) else None
        ok = status==200 and isinstance(published,list) and len(published)>0
        check("published_catalogue", "PASS" if ok else "FAIL",
              f"HTTP {status}; {len(published) if isinstance(published,list) else 'invalid'} published records", {"ms":ms})
        if not ok: raise RuntimeError("No valid published catalog for further assertions")
        status, home, ms = fetch_json("/api/shop-products/homepage")
        homepage=home.get("products") if isinstance(home,dict) else None
        home_ok=status==200 and isinstance(homepage,list) and len(homepage)>0
        check("homepage_catalogue", "PASS" if home_ok else "FAIL",
              f"HTTP {status}; {len(homepage) if isinstance(homepage,list) else 'invalid'} homepage records", {"ms":ms})
        ids=[x.get("id") for x in published if isinstance(x,dict)]
        slugs=[x.get("slug") for x in published if isinstance(x,dict)]
        valid_ids=all(isinstance(i,str) and i.strip() for i in ids)
        valid_slugs=all(isinstance(i,str) and i.strip() for i in slugs)
        unique=(valid_ids and valid_slugs and len(ids)==len(published) and
                len(set(ids))==len(ids) and len(set(slugs))==len(slugs))
        check("published_unique_ids_slugs", "PASS" if unique else "FAIL",
              f"Published={len(published)}; duplicate IDs={len(ids)-len(set(ids))}; duplicate slugs={len(slugs)-len(set(slugs))}")
        active=all(x.get("active") is True for x in published)
        check("published_active_only", "PASS" if active else "FAIL",
              f"Published products active={sum(x.get('active') is True for x in published)}/{len(published)}")
        def number(value):
            return (type(value) in (int,float)) and math.isfinite(value)
        priced=[x for x in published if number(x.get("price")) and x.get("price")>=0]
        check("published_valid_prices", "PASS" if len(priced)==len(published) else "FAIL",
              f"Nonnegative finite selling prices={len(priced)}/{len(published)}")
        with_images=sum(bool(x.get("images") or x.get("thumbnail")) for x in published)
        check("published_image_metadata", "PASS" if with_images==len(published) else "WARN",
              f"Published products with image metadata={with_images}/{len(published)}; image URLs not fetched")
        if home_ok:
            ids_home={x.get("id") for x in homepage if isinstance(x,dict)}
            missing=len(ids_home-set(ids))
            check("homepage_subset_published", "PASS" if missing==0 else "FAIL",
                  f"Homepage={len(homepage)}; distinct homepage IDs not in published catalogue={missing}")
        inflated=sum(number(x.get("originalPrice")) and number(x.get("price")) and
                     x["price"] > x["originalPrice"]+0.001 for x in published)
        check("mrp_customer_price", "WARN" if inflated else "PASS",
              f"Customer price greater than originalPrice/MRP: {inflated}/{len(published)} staging records; investigate pricing/commission contract before production release")
        status, stock, ms=fetch_json("/api/inventory/availability")
        entries=stock.get("availability") if isinstance(stock,dict) else None
        schema_ok=(status==200 and isinstance(entries,list) and len(entries)>0 and
                   all(isinstance(x,dict) and isinstance(x.get("productId"),str)
                   and type(x.get("available")) is bool for x in entries))
        check("inventory_schema", "PASS" if schema_ok else "FAIL",
              f"HTTP {status}; inventory entries={len(entries) if isinstance(entries,list) else 'invalid'}; productId and available:boolean")
        if schema_ok:
            keys=[(e.get("productId"),e.get("variantId")) for e in entries]
            check("inventory_distinct_variants", "PASS" if len(keys)==len(set(keys)) else "FAIL",
                  f"Duplicate product-variant availability pairs={len(keys)-len(set(keys))}")
        for path,name in [("/api/orders","anonymous_orders_denied"),
                          ("/api/auth/me","anonymous_session_denied")]:
            status, body, ms=request(path)
            check(name, "PASS" if status in (401,403) else "FAIL",
                  f"Anonymous GET {path} HTTP {status}; expected 401 or 403", {"ms":ms})
        for path,name,token in [("/robots.txt","robots_route",b"User-agent"),
                                 ("/sitemap.xml","sitemap_route",b"<")]:
            status, body, ms=request(path)
            valid=status==200 and token.lower() in body[:500].lower()
            check(name,"PASS" if valid else "WARN",
                  f"{path} HTTP {status}; basic content {'present' if valid else 'unverified'}", {"ms":ms})
    except Exception as exc:
        check("harness_integrity", "FAIL",f"Aborted safely: {type(exc).__name__}: {str(exc)[:220]}")
    counts=dict(Counter(x["status"] for x in result["checks"]))
    result["summary"]=counts
    result["total"]=len(result["checks"])
    result["verdict"]="FAIL" if counts.get("FAIL",0)>0 else "WARNINGS_REQUIRE_REVIEW" if counts.get("WARN",0)>0 else "PASS"
    path=pathlib.Path(a.output)
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+".tmp")
    temp.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    temp.replace(path)
    print("CONTRACT_VERDICT",result["verdict"],"COUNTS",counts,flush=True)
    return 2 if counts.get("FAIL",0)>0 else 0

if __name__ == "__main__":
    sys.exit(main())
