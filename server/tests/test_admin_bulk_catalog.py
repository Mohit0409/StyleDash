"""Safe admin bulk unpublish / archive regression tests (isolated, local SQLite)."""
import sqlite3
from contextlib import closing
import tempfile
import unittest
from pathlib import Path

from scripts.styledash_security import SecurityError
from scripts.styledash_shops import ShopWorkflow
from server.tests.test_shop_workflow import create_base_database


class AdminBulkProductManagementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "v4y-test.db"
        create_base_database(self.db_path)
        self.shop = ShopWorkflow(self.db_path)
        self.application = self.shop.admin_create_application(
            "admin-a", "user-a", {
                "shopName": "Bulk Safety Shop",
                "ownerName": "Registered Shop Owner",
                "category": "Clothing & Fashion",
                "description": "Test shop with two distinct products.",
                "address": "Main Market Road",
                "city": "Neemuch",
                "state": "Madhya Pradesh",
                "pincode": "458441",
                "businessInformation": "Local retail shop.",
            },
        )
        self.products = []
        for label in ("One", "Two"):
            self.products.append(self.shop.admin_create_product(
                "admin-a", self.application["id"], {
                    "name": f"Bulk Safe Tee {label}",
                    "description": "A local product with a complete audit record.",
                    "brand": "Local",
                    "department": "unisex",
                    "category": "Clothing & Fashion",
                    "pricePaise": 110000,
                    "originalPricePaise": 150000,
                    "variants": [{"size": "M", "inventory": 5}],
                    "colourName": "Black",
                    "colourHex": "#111111",
                    "imageUrls": ["https://images.example.test/product.jpg"],
                    "attributes": {},
                },
            ))

    def tearDown(self):
        self.temp.cleanup()

    def assert_security_error(self, code, callback):
        with self.assertRaises(SecurityError) as caught:
            callback()
        self.assertEqual(caught.exception.code, code)

    def test_bulk_unpublish_hides_selected_from_public_without_deleting_records(self):
        ids = [p["id"] for p in self.products]
        self.assertEqual(len(self.shop.list_published_products()), 2)
        result = self.shop.admin_bulk_manage_products("admin-a", ids, "UNPUBLISH")
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["updatedIds"], ids)
        self.assertEqual(self.shop.list_published_products(), [])
        self.assertEqual(len(self.shop.admin_list_products("admin-a")), 2)
        with closing(sqlite3.connect(self.db_path)) as db:
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM shop_product_submissions WHERE status='APPROVED' AND published_at IS NULL"
            ).fetchone()[0], 2)

    def test_failed_bulk_unpublish_is_atomic(self):
        first, second = (p["id"] for p in self.products)
        self.shop.admin_bulk_manage_products("admin-a", [first], "UNPUBLISH")
        self.assert_security_error(
            "bulk_product_not_published",
            lambda: self.shop.admin_bulk_manage_products("admin-a", [first, second], "UNPUBLISH"),
        )
        self.assertEqual({p["id"] for p in self.shop.list_published_products()}, {second})

    def test_remove_is_archive_not_delete_and_prevents_republishing(self):
        first, second = (p["id"] for p in self.products)
        result = self.shop.admin_bulk_manage_products("admin-a", [first], "REMOVE")
        self.assertEqual(result["count"], 1)
        self.assertEqual({p["id"] for p in self.shop.admin_list_products("admin-a")}, {second})
        self.assertEqual({p["id"] for p in self.shop.list_published_products()}, {second})
        self.assert_security_error(
            "product_removed", lambda: self.shop.admin_transition_product("admin-a", first, "PUBLISHED"),
        )
        with closing(sqlite3.connect(self.db_path)) as db:
            saved = db.execute(
                "SELECT status,price_paise,original_price_paise,inventory FROM shop_product_submissions WHERE id=?",
                (first,),
            ).fetchone()
            archived = db.execute(
                "SELECT removed_by FROM admin_removed_shop_products WHERE product_id=?", (first,)
            ).fetchone()
            self.assertEqual(saved, ("APPROVED", 110000, 150000, 5))
            self.assertEqual(archived, ("admin-a",))
            self.assertTrue(db.execute(
                "SELECT 1 FROM local_admin_audit_log WHERE action='shop_product_admin_removed' AND target_id=?",
                (first,),
            ).fetchone())

    def test_remove_batch_is_atomic_and_does_not_modify_other_products(self):
        first, second = (p["id"] for p in self.products)
        self.assert_security_error(
            "bulk_product_conflict",
            lambda: self.shop.admin_bulk_manage_products("admin-a", [first, "missing-product"], "REMOVE"),
        )
        self.assertEqual(len(self.shop.admin_list_products("admin-a")), 2)
        self.shop.admin_bulk_manage_products("admin-a", [first, second], "REMOVE")
        self.assertEqual(self.shop.admin_list_products("admin-a"), [])
        self.assertEqual(self.shop.list_published_products(), [])
        with closing(sqlite3.connect(self.db_path)) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM shop_product_submissions").fetchone()[0], 2)

    def test_bad_actions_duplicates_and_nonadmins_are_rejected(self):
        ids = [p["id"] for p in self.products]
        self.assert_security_error(
            "invalid_bulk_product_action",
            lambda: self.shop.admin_bulk_manage_products("admin-a", ids, "DELETE"),
        )
        self.assert_security_error(
            "invalid_bulk_product_ids",
            lambda: self.shop.admin_bulk_manage_products("admin-a", [ids[0], ids[0]], "REMOVE"),
        )
        self.assert_security_error(
            "invalid_bulk_product_ids",
            lambda: self.shop.admin_bulk_manage_products("admin-a", [], "REMOVE"),
        )
        self.assert_security_error(
            "admin_authorization_required",
            lambda: self.shop.admin_bulk_manage_products("not-an-admin", ids, "REMOVE"),
        )


if __name__ == "__main__":
    unittest.main()
