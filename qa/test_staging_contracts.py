"""Unit tests for fail-closed staging contract checker. Synthetic response fixtures only."""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from staging_contracts import main, IDENTITY, IDENTITY_PATH


class StagingContractsTests(unittest.TestCase):
    def make_responses(self, *, bad_price=False, auth_leak=False, bad_marker=False, duplicate=False):
        products = [
            {
                "id": "test1", "slug": "fixture-1", "name": "Test fixture 1",
                "active": True, "price": 100, "originalPrice": 150,
                "thumbnail": "https://example.invalid/test.png",
            },
            {
                "id": "test1" if duplicate else "test2",
                "slug": "fixture-2", "name": "Test fixture 2",
                "active": True, "price": 200 if bad_price else 125, "originalPrice": 150,
                "images": ["https://example.invalid/test2.png"],
            },
        ]
        bodies={
            IDENTITY_PATH:(200, (IDENTITY if not bad_marker else "PRODUCTION").encode()),
            "/api/health":(200, {"status":"ok", "service":"Vibe4You","database":"ok"}),
            "/api/shop-products/published":(200, {"products":products}),
            "/api/shop-products/homepage":(200, {"products":[products[0]]}),
            "/api/inventory/availability":(200, {"availability":[
                {"productId":"test1","variantId":"v1","available":True},
                {"productId":"test2","variantId":"v1","available":False}
            ]}),
            "/api/orders":(200 if auth_leak else 401, {"success": False}),
            "/api/auth/me":(401, {"success":False}),
            "/robots.txt":(200, b"User-agent: *\nDisallow: /admin\n"),
            "/sitemap.xml":(200, b"<?xml version='1.0'?><urlset></urlset>"),
        }
        def mock_request(path):
            status,body=bodies[path]
            if isinstance(body,dict): body=json.dumps(body).encode()
            return status,body,2
        return mock_request

    def run_contracts(self, mock_request):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/"report.json"
            with (patch("staging_contracts.request", side_effect=mock_request),
                  patch.object(sys,"argv",["staging_contracts.py","--output",str(out)]),
                  contextlib.redirect_stdout(io.StringIO())):
                rc=main()
            return rc, json.loads(out.read_text(encoding="utf8"))

    def test_valid_staging_contracts_pass(self):
        rc,report=self.run_contracts(self.make_responses())
        self.assertEqual(rc,0)
        self.assertEqual(report["summary"],{"PASS":16})
        self.assertEqual(report["verdict"],"PASS")

    def test_pricing_mrp_inversion_is_visible_warning_not_pass(self):
        rc,report=self.run_contracts(self.make_responses(bad_price=True))
        self.assertEqual(rc,0)
        warnings=[x for x in report["checks"] if x["status"]=="WARN"]
        self.assertEqual(len(warnings),1)
        self.assertEqual(warnings[0]["id"],"contract.mrp_customer_price")
        self.assertIn("1/2",warnings[0]["detail"])

    def test_anonymous_orders_accessible_fails(self):
        rc,report=self.run_contracts(self.make_responses(auth_leak=True))
        self.assertEqual(rc,2)
        self.assertEqual(report["verdict"],"FAIL")
        leaking=[x for x in report["checks"] if x["id"]=="contract.anonymous_orders_denied"]
        self.assertEqual(leaking[0]["status"],"FAIL")

    def test_duplicate_catalogue_ids_fail(self):
        rc,report=self.run_contracts(self.make_responses(duplicate=True))
        self.assertEqual(rc,2)
        self.assertEqual(next(x for x in report["checks"] if x["id"]=="contract.published_unique_ids_slugs")["status"],"FAIL")

    def test_missing_staging_identity_aborts_before_catalogue_queries(self):
        mock_request=self.make_responses(bad_marker=True)
        calls=[]
        def tracked(path):
            calls.append(path)
            return mock_request(path)
        rc,report=self.run_contracts(tracked)
        self.assertEqual(rc,2)
        self.assertEqual(calls,[IDENTITY_PATH])
        self.assertEqual(report["summary"],{"FAIL":1})


if __name__=="__main__":
    unittest.main()
