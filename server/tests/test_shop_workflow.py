import sqlite3
import json
import tempfile
import threading
import unittest
from pathlib import Path

from scripts.styledash_security import SecurityError
from scripts.styledash_shops import ShopWorkflow


OLD_VENDOR_SCHEMA = """
CREATE TABLE vendor_applications(
  id TEXT PRIMARY KEY,
  submitted_by_user_id TEXT NOT NULL REFERENCES users(id),
  shop_name TEXT NOT NULL,
  owner_name TEXT NOT NULL,
  email TEXT NOT NULL,
  phone TEXT NOT NULL,
  category TEXT NOT NULL,
  address TEXT NOT NULL,
  pincode TEXT NOT NULL,
  description TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK(status IN ('pending','approved','rejected')),
  reviewed_by TEXT REFERENCES users(id),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
"""


def create_base_database(path: Path, *, old_vendor_table: bool = True) -> None:
    db = sqlite3.connect(path)
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript(
        """
        CREATE TABLE users(
          id TEXT PRIMARY KEY,
          email TEXT,
          phone TEXT,
          name TEXT NOT NULL,
          is_active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE admin_users(
          id TEXT PRIMARY KEY,
          is_active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE local_admin_audit_log(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          admin_user_id TEXT REFERENCES admin_users(id),
          action TEXT NOT NULL,
          target_type TEXT,
          target_id TEXT,
          result TEXT NOT NULL,
          metadata_json TEXT NOT NULL DEFAULT '{}',
          created_at TEXT NOT NULL
        );
        INSERT INTO users(id,email,phone,name,is_active)
          VALUES('user-a','owner@example.test','+919876543210','Owner A',1);
        INSERT INTO users(id,email,phone,name,is_active)
          VALUES('user-b','other@example.test','+919876543211','Owner B',1);
        INSERT INTO admin_users(id,is_active) VALUES('admin-a',1);
        """
    )
    if old_vendor_table:
        db.executescript(OLD_VENDOR_SCHEMA)
    db.commit()
    db.close()


class ShopWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / "styledash.db"
        create_base_database(self.path)
        self.store = ShopWorkflow(self.path)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def assert_error(self, code: str, callback) -> SecurityError:
        with self.assertRaises(SecurityError) as caught:
            callback()
        self.assertEqual(caught.exception.code, code)
        return caught.exception

    @staticmethod
    def complete_application(name: str = "Neemuch Fashion House") -> dict:
        return {
            "shopName": name,
            "ownerName": "Registered Owner",
            "category": "Clothing & Fashion",
            "description": "Locally curated clothing and fashion products.",
            "address": "12 Main Market Road",
            "city": "Neemuch",
            "state": "Madhya Pradesh",
            "pincode": "458441",
            "businessInformation": "Independent local retail shop.",
        }

    @staticmethod
    def complete_product(name: str = "Handloom Cotton Kurta") -> dict:
        return {
            "name": name,
            "description": "A locally stocked cotton kurta submitted for review.",
            "brand": "Local Loom",
            "department": "women",
            "category": "Clothing & Fashion",
            "pricePaise": 159900,
            "originalPricePaise": 179900,
            "inventory": 8,
            "imageUrls": ["https://images.example.test/kurta.jpg"],
            "attributes": {"material": "Cotton", "color": "Blue"},
            "size": "M",
            "colourName": "Blue",
            "colourHex": "#0000FF",
        }

    def create_active_shop(self, user_id: str, name: str) -> dict:
        application = self.store.create_draft(
            user_id, self.complete_application(name)
        )
        application = self.store.submit_application(user_id)
        application = self.store.admin_transition_application(
            "admin-a", application["id"], "UNDER_REVIEW"
        )
        application = self.store.admin_transition_application(
            "admin-a", application["id"], "APPROVED"
        )
        return self.store.admin_transition_application(
            "admin-a", application["id"], "ACTIVE"
        )

    def test_migration_maps_legacy_status_and_is_idempotent(self) -> None:
        legacy_path = Path(self.temporary.name) / "legacy.db"
        create_base_database(legacy_path)
        db = sqlite3.connect(legacy_path)
        db.execute(
            """
            INSERT INTO vendor_applications(
              id,submitted_by_user_id,shop_name,owner_name,email,phone,category,
              address,pincode,description,status,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                "legacy-one",
                "user-a",
                "Legacy Shop",
                "Owner A",
                "owner@example.test",
                "+919876543210",
                "Clothing & Fashion",
                "Old Main Market",
                "458441",
                "Legacy submitted application.",
                "pending",
                "2026-08-01T00:00:00+00:00",
                "2026-08-01T00:00:00+00:00",
            ),
        )
        db.commit()
        db.close()

        migrated = ShopWorkflow(legacy_path)
        application = migrated.get_application("user-a")
        self.assertEqual(application["status"], "SUBMITTED")
        self.assertEqual(application["city"], "Neemuch")
        self.assertEqual(application["state"], "Madhya Pradesh")
        ShopWorkflow(legacy_path)
        with migrated.connect() as db:
            self.assertEqual(
                [row[0] for row in db.execute(
                    "SELECT version FROM shop_schema_migrations ORDER BY version"
                )],
                [1, 2, 3, 4, 5],
            )
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_migration_refuses_duplicate_customer_applications(self) -> None:
        duplicate_path = Path(self.temporary.name) / "duplicate.db"
        create_base_database(duplicate_path)
        db = sqlite3.connect(duplicate_path)
        for index in range(2):
            db.execute(
                """
                INSERT INTO vendor_applications(
                  id,submitted_by_user_id,shop_name,owner_name,email,phone,category,
                  address,pincode,description,created_at,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    f"legacy-{index}",
                    "user-a",
                    f"Legacy {index}",
                    "Owner A",
                    "owner@example.test",
                    "+919876543210",
                    "Clothing & Fashion",
                    "Old Main Market",
                    "458441",
                    "Legacy duplicate application.",
                    "2026-08-01T00:00:00+00:00",
                    "2026-08-01T00:00:00+00:00",
                ),
            )
        db.commit()
        db.close()

        with self.assertRaisesRegex(RuntimeError, "duplicate applications"):
            ShopWorkflow(duplicate_path)
        db = sqlite3.connect(duplicate_path)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM vendor_applications").fetchone()[0], 2)
        db.close()

    def test_concurrent_public_private_startup_migrates_once(self) -> None:
        concurrent_path = Path(self.temporary.name) / "concurrent.db"
        create_base_database(concurrent_path)
        # SecurityStore/AdminStore establish WAL before ShopWorkflow is
        # constructed in production. Exercise the actual concurrent shop DDL
        # path without conflating it with simultaneous journal-mode setup.
        prepared = sqlite3.connect(concurrent_path)
        self.assertEqual(prepared.execute("PRAGMA journal_mode=WAL").fetchone()[0], "wal")
        prepared.close()
        barrier = threading.Barrier(2)
        errors: list[Exception] = []

        def initialize() -> None:
            try:
                barrier.wait(timeout=5)
                ShopWorkflow(concurrent_path)
            except Exception as exc:  # pragma: no cover - assertion reports details
                errors.append(exc)

        threads = [threading.Thread(target=initialize) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(errors, [])
        db = sqlite3.connect(concurrent_path)
        self.assertEqual(
            db.execute("SELECT version,COUNT(*) FROM shop_schema_migrations GROUP BY version").fetchall(),
            [(1, 1), (2, 1), (3, 1), (4, 1), (5, 1)],
        )
        self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(), [])
        db.close()


    def test_store_branding_migration_repairs_marker_schema_mismatch(self) -> None:
        self.create_active_shop("user-a", "Branding Repair Shop")
        with self.store.connect() as db:
            self.assertIsNotNone(db.execute("SELECT 1 FROM shop_schema_migrations WHERE version=5").fetchone())
            db.execute("ALTER TABLE vendor_applications DROP COLUMN banner_image_url")
            db.execute("ALTER TABLE vendor_applications DROP COLUMN logo_image_url")
        repaired = ShopWorkflow(self.path)
        with repaired.connect() as db:
            columns = {row[1] for row in db.execute("PRAGMA table_info(vendor_applications)")}
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(), [])
        self.assertTrue({"banner_image_url", "logo_image_url"}.issubset(columns))

    def test_approved_owner_can_manage_store_branding_with_safe_fallbacks(self) -> None:
        draft = self.store.create_draft("user-a", self.complete_application("Branding Shop"))
        self.assert_error(
            "approved_shop_required",
            lambda: self.store.update_store_branding("user-a", {"bannerImage": None}),
        )
        self.store.submit_application("user-a")
        self.store.admin_transition_application("admin-a", draft["id"], "UNDER_REVIEW")
        approved = self.store.admin_transition_application("admin-a", draft["id"], "APPROVED")
        banner = "/media/product-images/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.webp"
        logo = "/media/product-images/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb.png"
        branded = self.store.update_store_branding("user-a", {"bannerImage": banner, "logoImage": logo})
        self.assertEqual((branded["bannerImage"], branded["logoImage"]), (banner, logo))
        self.assert_error(
            "invalid_store_branding",
            lambda: self.store.update_store_branding("user-a", {"logoImage": "https://example.test/logo.png"}),
        )
        self.assert_error(
            "invalid_store_branding",
            lambda: self.store.update_store_branding(
                "user-a", {"applicationId": approved["id"], "logoImage": logo}
            ),
        )
        self.store.admin_transition_application("admin-a", approved["id"], "ACTIVE")
        public = self.store.list_active_stores()[0]
        self.assertEqual((public["bannerImage"], public["logoImage"]), (banner, logo))
        cleared = self.store.update_store_branding("user-a", {"logoImage": None})
        self.assertIsNone(cleared["logoImage"])
        self.assertEqual(cleared["bannerImage"], banner)

        other = self.create_active_shop("user-b", "Other Owner Shop")
        other_banner = "/media/product-images/cccccccccccccccccccccccccccccccc.jpg"
        self.store.update_store_branding("user-b", {"bannerImage": other_banner})
        self.assertEqual(self.store.get_application("user-b")["bannerImage"], other_banner)
        self.assertEqual(self.store.get_application("user-a")["bannerImage"], banner)
        self.assertNotEqual(other["id"], approved["id"])

    def test_variant_migration_repairs_marker_schema_mismatch(self) -> None:
        self.create_active_shop("user-a", "Repair Shop")
        product = self.store.create_product_draft("user-a", self.complete_product("Legacy Variant Product"))
        with self.store.connect() as db:
            self.assertIsNotNone(db.execute("SELECT 1 FROM shop_schema_migrations WHERE version=4").fetchone())
            db.execute("ALTER TABLE shop_product_submissions DROP COLUMN variants_json")
        repaired = ShopWorkflow(self.path)
        with repaired.connect() as db:
            columns = {row[1] for row in db.execute("PRAGMA table_info(shop_product_submissions)")}
            self.assertIn("variants_json", columns)
            raw = db.execute("SELECT variants_json FROM shop_product_submissions WHERE id=?", (product["id"],)).fetchone()[0]
        self.assertEqual(json.loads(raw), [{"size": "M", "inventory": 8}])
        payload = self.complete_product("Repaired Multi Size Product")
        payload.pop("inventory")
        payload.pop("size")
        payload["variants"] = [{"size": "M", "inventory": 2}, {"size": "L", "inventory": 3}]
        created = repaired.create_product_draft("user-a", payload)
        self.assertEqual([(item["size"], item["inventory"]) for item in created["variants"]], [("M", 2), ("L", 3)])

    def test_edit_with_uploaded_image_discards_legacy_webpage_url(self) -> None:
        self.create_active_shop("user-a", "Legacy Image Shop")
        product = self.store.create_product_draft("user-a", self.complete_product("Legacy Image Product"))
        self.store.submit_product("user-a", product["id"])
        for target in ("UNDER_REVIEW", "APPROVED", "PUBLISHED"):
            product = self.store.admin_transition_product("admin-a", product["id"], target)
        legacy_url = "https://pngtree.com/freepng/stacked-jeans_3160982.html"
        uploaded_url = "/media/product-images/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.webp"
        with self.store.connect() as db:
            db.execute("UPDATE shop_product_submissions SET image_urls_json=? WHERE id=?", (json.dumps([legacy_url]), product["id"]))
        self.assert_error(
            "invalid_product",
            lambda: self.store.create_product_edit_request("user-a", product["id"], {"name": "Still Invalid", "imageUrls": [legacy_url]}),
        )
        request = self.store.create_product_edit_request(
            "user-a",
            product["id"],
            {"name": "Repaired Image Product", "imageUrls": [legacy_url, uploaded_url]},
        )
        self.assertEqual(request["proposedProduct"]["imageUrls"], [uploaded_url])

    def test_incremental_draft_rejection_resubmission_and_suspension(self) -> None:
        draft = self.store.create_draft("user-a", {"shopName": "Partial Shop"})
        self.assertEqual(draft["status"], "DRAFT")
        self.assertEqual(draft["ownerName"], "")
        self.assertEqual(draft["registeredEmail"], "owner@example.test")
        self.assertEqual(draft["registeredMobile"], "+919876543210")
        self.assert_error("invalid_vendor_application", lambda: self.store.submit_application("user-a"))
        self.assert_error(
            "invalid_vendor_application",
            lambda: self.store.update_draft("user-a", {"status": "APPROVED"}),
        )

        completed = self.store.update_draft("user-a", self.complete_application())
        self.assertEqual(completed["status"], "DRAFT")
        submitted = self.store.submit_application("user-a")
        self.assertEqual(submitted["status"], "SUBMITTED")
        self.assert_error(
            "vendor_application_exists",
            lambda: self.store.create_draft("user-a", self.complete_application()),
        )
        self.assert_error(
            "invalid_vendor_transition",
            lambda: self.store.update_draft("user-a", {"description": "Cannot edit now."}),
        )
        self.assert_error(
            "admin_authorization_required",
            lambda: self.store.admin_transition_application(
                "user-a", submitted["id"], "UNDER_REVIEW"
            ),
        )
        self.assert_error(
            "invalid_vendor_transition",
            lambda: self.store.admin_transition_application(
                "admin-a", submitted["id"], "APPROVED"
            ),
        )

        reviewing = self.store.admin_transition_application(
            "admin-a", submitted["id"], "UNDER_REVIEW"
        )
        self.assertEqual(reviewing["status"], "UNDER_REVIEW")
        self.assert_error(
            "rejection_reason_required",
            lambda: self.store.admin_transition_application(
                "admin-a", submitted["id"], "REJECTED"
            ),
        )
        rejected = self.store.admin_transition_application(
            "admin-a", submitted["id"], "REJECTED", "Clarify the shop address."
        )
        self.assertEqual(rejected["rejectionReason"], "Clarify the shop address.")
        customer_view = self.store.get_application("user-a")
        self.assertEqual(customer_view["rejectionReason"], "Clarify the shop address.")

        corrected = self.store.update_draft(
            "user-a", {"address": "14 Corrected Main Market Road"}
        )
        self.assertEqual(corrected["status"], "DRAFT")
        self.assertIsNone(corrected["rejectionReason"])
        resubmitted = self.store.submit_application("user-a")
        self.store.admin_transition_application(
            "admin-a", resubmitted["id"], "UNDER_REVIEW"
        )
        self.store.admin_transition_application(
            "admin-a", resubmitted["id"], "APPROVED"
        )
        active = self.store.admin_transition_application(
            "admin-a", resubmitted["id"], "ACTIVE"
        )
        self.assertEqual(active["status"], "ACTIVE")
        suspended = self.store.admin_transition_application(
            "admin-a", resubmitted["id"], "SUSPENDED", "Private risk review."
        )
        self.assertEqual(suspended["suspensionReason"], "Private risk review.")
        customer_suspended = self.store.get_application("user-a")
        self.assertEqual(customer_suspended["status"], "SUSPENDED")
        self.assertNotIn("suspensionReason", customer_suspended)
        reactivated = self.store.admin_transition_application(
            "admin-a", resubmitted["id"], "ACTIVE"
        )
        self.assertEqual(reactivated["status"], "ACTIVE")
        self.assertGreaterEqual(len(self.store.admin_list_applications("admin-a")), 1)
        self.assert_error(
            "admin_authorization_required",
            lambda: self.store.admin_list_applications("user-a"),
        )
        with self.store.connect() as db:
            audit_actions = {
                row[0] for row in db.execute("SELECT action FROM local_admin_audit_log")
            }
        self.assertIn("shop_rejected", audit_actions)
        self.assertIn("shop_suspended", audit_actions)

    def test_customer_application_and_product_idor(self) -> None:
        self.create_active_shop("user-a", "Shop A")
        self.create_active_shop("user-b", "Shop B")
        product = self.store.create_product_draft(
            "user-a", self.complete_product("Owner A Product")
        )
        self.assert_error(
            "product_not_found",
            lambda: self.store.update_product_draft(
                "user-b", product["id"], {"name": "Stolen Product"}
            ),
        )
        self.assert_error(
            "product_not_found",
            lambda: self.store.submit_product("user-b", product["id"]),
        )
        self.assertEqual(self.store.get_application("missing-user"), None)

    def test_only_admin_can_publish_and_public_requires_active_shop(self) -> None:
        application = self.create_active_shop("user-a", "Publishing Shop")
        image_less = self.store.create_product_draft(
            "user-a", {**self.complete_product("Image-less Product"), "imageUrls": []}
        )
        self.assert_error(
            "product_image_required",
            lambda: self.store.submit_product("user-a", image_less["id"]),
        )
        self.assert_error(
            "invalid_product",
            lambda: self.store.create_product_draft(
                "user-a", {**self.complete_product(), "status": "PUBLISHED"}
            ),
        )
        product = self.store.create_product_draft("user-a", self.complete_product())
        self.assertEqual(product["status"], "DRAFT")
        self.assertEqual(self.store.list_published_products(), [])
        submitted = self.store.submit_product("user-a", product["id"])
        self.assertEqual(submitted["status"], "SUBMITTED")
        self.assert_error(
            "invalid_product_transition",
            lambda: self.store.update_product_draft(
                "user-a", product["id"], {"inventory": 9}
            ),
        )
        self.assert_error(
            "admin_authorization_required",
            lambda: self.store.admin_transition_product(
                "user-a", product["id"], "UNDER_REVIEW"
            ),
        )
        self.assert_error(
            "invalid_product_transition",
            lambda: self.store.admin_transition_product(
                "admin-a", product["id"], "PUBLISHED"
            ),
        )
        self.store.admin_transition_product(
            "admin-a", product["id"], "UNDER_REVIEW"
        )
        self.store.admin_transition_product("admin-a", product["id"], "APPROVED")
        published = self.store.admin_transition_product(
            "admin-a", product["id"], "PUBLISHED"
        )
        self.assertEqual(published["status"], "PUBLISHED")
        public_products = self.store.list_published_products()
        self.assertEqual([item["id"] for item in public_products], [product["id"]])
        self.assertEqual(public_products[0]["variants"][0]["id"], f"{product['id']}-var-1")
        self.assertFalse(public_products[0]["variants"][0]["available"])
        self.assertNotIn("submittedByUserId", public_products[0])
        self.assertNotIn("registeredEmail", public_products[0])
        payment_products = self.store.payment_catalog_products()
        payment_product = next(item for item in payment_products if item["id"] == product["id"])
        self.assertEqual(payment_product["id"], public_products[0]["id"])
        self.assertEqual(
            payment_product["variants"][0]["id"],
            public_products[0]["variants"][0]["id"],
        )
        self.assertEqual(payment_product["price"], public_products[0]["price"])

        self.store.admin_transition_application(
            "admin-a", application["id"], "SUSPENDED", "Private suspension detail."
        )
        self.assertEqual(self.store.list_published_products(), [])
        self.store.admin_transition_application(
            "admin-a", application["id"], "ACTIVE"
        )
        self.assertEqual(len(self.store.list_published_products()), 1)
        unpublished = self.store.admin_transition_product(
            "admin-a", product["id"], "APPROVED"
        )
        self.assertEqual(unpublished["status"], "APPROVED")
        self.assertEqual(self.store.list_published_products(), [])
        self.assertEqual(
            {item["id"] for item in self.store.admin_list_products("admin-a")},
            {image_less["id"], product["id"]},
        )

    def test_private_admin_size_replacement_never_reuses_retired_variant_identity(self) -> None:
        self.create_active_shop("user-a", "Immutable Variant Shop")
        product = self.store.create_product_draft(
            "user-a", self.complete_product("Immutable Variant Kurta")
        )
        self.store.submit_product("user-a", product["id"])
        for target in ("UNDER_REVIEW", "APPROVED", "PUBLISHED"):
            product = self.store.admin_transition_product(
                "admin-a", product["id"], target
            )

        original_id = product["variants"][0]["id"]
        self.store.admin_transition_product("admin-a", product["id"], "APPROVED")
        replaced = self.store.admin_update_product(
            "admin-a",
            product["id"],
            {"variants": [{"size": "XL", "inventory": 4}]},
        )
        active = replaced["variants"][0]
        replacement_catalog = next(
            item
            for item in self.store.payment_catalog_products()
            if item["id"] == product["id"]
        )["variants"]
        retired = next(
            item for item in replacement_catalog if item["id"] == original_id
        )
        self.assertEqual((active["size"], active["inventory"]), ("XL", 4))
        self.assertTrue(active["id"].startswith("shopvar_"))
        self.assertNotEqual(active["id"], original_id)
        self.assertEqual(
            (
                retired["id"],
                retired["size"],
                retired["colourName"],
                retired["stock"],
                retired["active"],
            ),
            (original_id, "M", "Blue", 8, False),
        )

        self.store.admin_transition_product("admin-a", product["id"], "PUBLISHED")
        public_variant = self.store.list_published_products()[0]["variants"][0]
        self.assertEqual(
            (public_variant["id"], public_variant["size"], public_variant["stock"]),
            (active["id"], "XL", 4),
        )
        catalog = self.store.payment_catalog_products()[0]["variants"]
        self.assertFalse(
            next(item for item in catalog if item["id"] == original_id)["active"]
        )

    def test_published_product_change_requests_preserve_live_version_until_approval(self) -> None:
        self.create_active_shop("user-a", "Managed Publishing Shop")
        self.create_active_shop("user-b", "Other Seller Shop")
        product = self.store.create_product_draft(
            "user-a", self.complete_product("Original Live Kurta")
        )
        self.store.submit_product("user-a", product["id"])
        for target in ("UNDER_REVIEW", "APPROVED", "PUBLISHED"):
            product = self.store.admin_transition_product("admin-a", product["id"], target)

        original_public = self.store.list_published_products()[0]
        self.assertEqual((original_public["name"], original_public["price"]), ("Original Live Kurta", 1599))
        self.assert_error(
            "product_not_found",
            lambda: self.store.create_product_edit_request(
                "user-b", product["id"], {"name": "Stolen Rename"}
            ),
        )
        self.assert_error(
            "invalid_product_change",
            lambda: self.store.create_product_edit_request("user-a", product["id"], {"inventory": 99}),
        )
        self.assert_error(
            "no_product_changes",
            lambda: self.store.create_product_edit_request(
                "user-a", product["id"], {"name": "Original Live Kurta"}
            ),
        )
        first = self.store.create_product_edit_request(
            "user-a", product["id"], {"name": "Reviewed Live Kurta", "pricePaise": 149900}
        )
        self.assertEqual((first["action"], first["status"]), ("EDIT", "SUBMITTED"))
        still_live = self.store.list_published_products()[0]
        self.assertEqual((still_live["name"], still_live["price"]), ("Original Live Kurta", 1599))
        self.assert_error(
            "product_change_pending",
            lambda: self.store.create_product_unpublish_request("user-a", product["id"]),
        )
        self.assert_error(
            "invalid_product_change_transition",
            lambda: self.store.admin_transition_product_change_request("admin-a", first["id"], "APPROVED"),
        )
        self.store.admin_transition_product_change_request("admin-a", first["id"], "UNDER_REVIEW")
        self.assert_error(
            "rejection_reason_required",
            lambda: self.store.admin_transition_product_change_request("admin-a", first["id"], "REJECTED"),
        )
        rejected = self.store.admin_transition_product_change_request(
            "admin-a", first["id"], "REJECTED", "Use the approved catalogue wording."
        )
        self.assertEqual(rejected["rejectionReason"], "Use the approved catalogue wording.")
        self.assertEqual(self.store.list_published_products()[0]["name"], "Original Live Kurta")

        original_variant = self.store.list_published_products()[0]["variants"][0]
        original_variant_id = original_variant["id"]
        self.assert_error(
            "published_variant_has_stock",
            lambda: self.store.create_product_edit_request(
                "user-a", product["id"], {"variants": [{"size": "XL", "inventory": 4}]},
                {original_variant_id: 8},
            ),
        )
        self.assert_error(
            "published_variant_rename_blocked",
            lambda: self.store.create_product_edit_request(
                "user-a", product["id"],
                {"variants": [{"id": original_variant_id, "size": "M Tall", "inventory": 0}]},
                {original_variant_id: 0},
            ),
        )
        variant_change = self.store.create_product_edit_request(
            "user-a", product["id"], {"variants": [{"size": "XL", "inventory": 4}]},
            {original_variant_id: 0},
        )
        proposed_variants = variant_change["proposedProduct"]["variants"]
        active_variant = next(item for item in proposed_variants if item["active"])
        retired_variant = next(item for item in proposed_variants if not item["active"])
        self.assertEqual((active_variant["size"], active_variant["inventory"]), ("XL", 4))
        self.assertTrue(active_variant["id"].startswith("shopvar_"))
        self.assertEqual(
            retired_variant,
            {"id": original_variant_id, "size": "M", "inventory": 0, "active": False},
        )
        self.assertEqual(
            [item["size"] for item in self.store.list_published_products()[0]["variants"]],
            ["M"],
        )
        self.store.admin_transition_product_change_request(
            "admin-a", variant_change["id"], "UNDER_REVIEW"
        )
        self.store.admin_transition_product_change_request(
            "admin-a",
            variant_change["id"],
            "APPROVED",
            live_inventory={original_variant_id: 0},
        )
        resized_public = self.store.list_published_products()[0]
        self.assertEqual(
            [(item["size"], item["stock"]) for item in resized_public["variants"]],
            [("XL", 4)],
        )
        catalog_variants = self.store.payment_catalog_products()[0]["variants"]
        self.assertEqual(
            next(item for item in catalog_variants if item["id"] == original_variant_id)["active"],
            False,
        )
        self.assertEqual(
            next(item for item in catalog_variants if item["size"] == "XL")["active"],
            True,
        )

        second = self.store.create_product_edit_request(
            "user-a", product["id"], {"name": "Approved Live Kurta", "pricePaise": 149900}
        )
        self.store.admin_transition_product_change_request("admin-a", second["id"], "UNDER_REVIEW")
        self.store.admin_transition_product_change_request("admin-a", second["id"], "APPROVED")
        changed_public = self.store.list_published_products()[0]
        self.assertEqual((changed_public["name"], changed_public["price"]), ("Approved Live Kurta", 1499))

        unpublish = self.store.create_product_unpublish_request("user-a", product["id"])
        self.store.admin_transition_product_change_request("admin-a", unpublish["id"], "UNDER_REVIEW")
        self.store.admin_transition_product_change_request("admin-a", unpublish["id"], "APPROVED")
        self.assertEqual(self.store.list_published_products(), [])
        product_after = next(
            item for item in self.store.admin_list_products("admin-a") if item["id"] == product["id"]
        )
        self.assertEqual(product_after["status"], "APPROVED")

    def test_multi_size_product_keeps_independent_stock_variants(self) -> None:
        self.create_active_shop("user-a", "Multi Size Shop")
        payload = self.complete_product("Variant Kurta")
        payload.pop("inventory")
        payload.pop("size")
        payload["variants"] = [
            {"size": "S", "inventory": 3},
            {"size": "M", "inventory": 7},
            {"size": "L", "inventory": 2},
            {"size": "XL", "inventory": 1},
        ]
        product = self.store.create_product_draft("user-a", payload)
        self.assertEqual(product["inventory"], 13)
        self.assertEqual([item["size"] for item in product["variants"]], ["S", "M", "L", "XL"])
        self.assertEqual([item["inventory"] for item in product["variants"]], [3, 7, 2, 1])
        self.store.submit_product("user-a", product["id"])
        for target in ("UNDER_REVIEW", "APPROVED", "PUBLISHED"):
            self.store.admin_transition_product("admin-a", product["id"], target)
        public = self.store.list_published_products()[0]
        self.assertEqual([item["size"] for item in public["variants"]], ["S", "M", "L", "XL"])
        self.assertEqual([item["stock"] for item in public["variants"]], [3, 7, 2, 1])
        self.assertEqual([item["id"] for item in public["variants"]], [f"{product['id']}-var-{index}" for index in range(1, 5)])

    def test_admin_bulk_create_products_is_atomic_and_publishes_all_rows(self) -> None:
        application = self.create_active_shop("user-a", "Bulk Upload Shop")
        first = self.complete_product("Bulk Kurta One")
        second = self.complete_product("Bulk Kurta Two")
        second["pricePaise"] = 129900
        second["originalPricePaise"] = 149900
        created = self.store.admin_bulk_create_products("admin-a", application["id"], [first, second])
        self.assertEqual([item["status"] for item in created], ["PUBLISHED", "PUBLISHED"])
        self.assertEqual(set(item["name"] for item in self.store.list_published_products()), {"Bulk Kurta One", "Bulk Kurta Two"})

        duplicate_a = self.complete_product("Duplicate Name")
        duplicate_b = self.complete_product("duplicate name")
        self.assert_error("invalid_bulk_products", lambda: self.store.admin_bulk_create_products("admin-a", application["id"], [duplicate_a, duplicate_b]))
        self.assertNotIn("Duplicate Name", [item["name"] for item in self.store.list_published_products()])

    def test_admin_bulk_create_products_rejects_existing_name_without_partial_insert(self) -> None:
        application = self.create_active_shop("user-a", "Existing Product Shop")
        self.store.admin_create_product("admin-a", application["id"], self.complete_product("Existing Kurta"))
        fresh = self.complete_product("Fresh Kurta")
        duplicate = self.complete_product("existing kurta")
        self.assert_error("duplicate_product", lambda: self.store.admin_bulk_create_products("admin-a", application["id"], [fresh, duplicate]))
        self.assertEqual([item["name"] for item in self.store.list_published_products()], ["Existing Kurta"])

    def test_catalog_normalization_applies_to_seller_create_and_public_dto(self) -> None:
        self.create_active_shop("user-a", "Normalized Seller Shop")
        payload = self.complete_product("Puma Slider for Men")
        payload.update({
            "brand": None,
            "department": "Mens",
            "category": "Clothing & Fashion",
            "variants": [{"size": "8", "inventory": 5}, {"size": "uk-9", "inventory": 4}],
            "deliveryType": "Weekend Express",
        })
        payload.pop("inventory", None)
        payload.pop("size", None)
        product = self.store.create_product_draft("user-a", payload)
        self.assertEqual((product["brand"], product["department"], product["category"]), ("Puma", "men", "Footwear"))
        self.assertEqual([item["size"] for item in product["variants"]], ["UK 8", "UK 9"])
        self.assertEqual((product["subcategory"], product["deliveryType"]), ("Sliders", "express"))
        self.store.submit_product("user-a", product["id"])
        for target in ("UNDER_REVIEW", "APPROVED", "PUBLISHED"):
            self.store.admin_transition_product("admin-a", product["id"], target)
        public = self.store.list_published_products()[0]
        self.assertEqual((public["subcategory"], public["deliveryType"], public["expressDelivery"]), ("Sliders", "express", True))
        payment_product = self.store.payment_catalog_products()[0]
        self.assertEqual((payment_product["deliveryType"], payment_product["expressDelivery"]), ("express", True))

    def test_catalog_normalization_applies_to_admin_bulk_and_edit(self) -> None:
        application = self.create_active_shop("user-a", "Normalized Admin Shop")
        payload = self.complete_product("Skechers Slider for Men")
        payload.update({"brand": "skechers", "department": "male", "category": "Footwear", "variants": [{"size": "10", "inventory": 5}]})
        payload.pop("inventory", None)
        payload.pop("size", None)
        created = self.store.admin_bulk_create_products("admin-a", application["id"], [payload])[0]
        self.assertEqual((created["brand"], created["department"], created["category"], created["subcategory"]), ("Skechers", "men", "Footwear", "Sliders"))
        self.assertEqual(created["variants"][0]["size"], "UK 10")
        self.store.admin_transition_product("admin-a", created["id"], "APPROVED")
        edited = self.store.admin_update_product("admin-a", created["id"], {"department": "gents", "deliveryType": "both"})
        self.assertEqual((edited["department"], edited["deliveryType"]), ("men", "both"))

    def test_new_products_reject_legacy_merchandise_class_as_department_when_ambiguous(self) -> None:
        self.create_active_shop("user-a", "Ambiguous Shop")
        payload = self.complete_product("Premium Everyday Sneakers")
        payload.update({"department": "footwear", "category": "Footwear"})
        self.assert_error("invalid_product", lambda: self.store.create_product_draft("user-a", payload))

if __name__ == "__main__":
    unittest.main()
