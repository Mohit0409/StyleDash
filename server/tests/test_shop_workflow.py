import json
import sqlite3
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
                [1, 2, 4, 5, 6],
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
            [(1, 1), (2, 1), (4, 1), (5, 1), (6, 1)],
        )
        self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        db.close()

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

    def test_seller_fulfillment_isolated_by_shop_and_forward_only(self) -> None:
        app_a = self.create_active_shop("user-a", "Shop A")
        app_b = self.create_active_shop("user-b", "Shop B")
        product_a = self.store.create_product_draft("user-a", self.complete_product("Product A"))
        product_b = self.store.create_product_draft("user-b", self.complete_product("Product B"))
        self.assertEqual(self.store.seller_fulfillment("user-a", "SD-MIXED")["status"], "NEW")
        self.assertEqual(self.store.seller_fulfillment("user-b", "SD-MIXED")["status"], "NEW")
        updated = self.store.update_seller_fulfillment("user-a", "SD-MIXED", {"status": "PROCESSING"})
        self.assertEqual(updated["status"], "PROCESSING")
        self.assertEqual(updated["allowedNextStatuses"], ["READY"])
        self.assertIsNone(updated["shipping"])
        self.assertEqual(self.store.seller_fulfillment("user-b", "SD-MIXED")["status"], "NEW")
        self.assert_error(
            "invalid_fulfillment_transition",
            lambda: self.store.update_seller_fulfillment("user-a", "SD-MIXED", {"status": "SHIPPED"}),
        )
        self.store.update_seller_fulfillment("user-a", "SD-MIXED", {"status": "READY"})
        self.assert_error(
            "invalid_shipping_details",
            lambda: self.store.update_seller_fulfillment(
                "user-a", "SD-MIXED", {"status": "SHIPPED", "carrier": "Delhivery"}
            ),
        )
        self.assert_error(
            "invalid_shipping_details",
            lambda: self.store.update_seller_fulfillment(
                "user-a", "SD-MIXED",
                {"status": "SHIPPED", "carrier": "Bad\nCarrier", "trackingNumber": "DLV-123456"},
            ),
        )
        shipped = self.store.update_seller_fulfillment(
            "user-a", "SD-MIXED",
            {"status": "SHIPPED", "carrier": "Delhivery", "trackingNumber": "DLV-123456"},
        )
        self.assertEqual(shipped["shipping"], {"carrier": "Delhivery", "trackingNumber": "DLV-123456"})
        changed = self.store.update_seller_fulfillment(
            "user-a", "SD-MIXED",
            {"status": "SHIPPED", "carrier": "Delhivery", "trackingNumber": "DLV-654321"},
        )
        self.assertFalse(changed["changed"])
        self.assertTrue(changed["shippingChanged"])
        self.assertEqual(changed["shipping"]["trackingNumber"], "DLV-654321")
        summary = self.store.order_fulfillments("SD-MIXED", [product_a["id"], product_b["id"]])
        self.assertEqual(
            [(row["shopName"], row["status"]) for row in summary],
            [("Shop A", "SHIPPED"), ("Shop B", "NEW")],
        )
        self.assertEqual(
            summary[0]["shipping"],
            {"carrier": "Delhivery", "trackingNumber": "DLV-654321"},
        )
        self.assertIsNone(summary[1]["shipping"])
        self.assertTrue(all("applicationId" not in row for row in summary))
        self.assertNotEqual(app_a["id"], app_b["id"])

    def test_return_request_core_is_scoped_validated_and_audited(self) -> None:
        app_a = self.create_active_shop("user-a", "Return Shop A")
        self.create_active_shop("user-b", "Return Shop B")
        product_a = self.store.create_product_draft("user-a", self.complete_product("Return Product A"))
        product_b = self.store.create_product_draft("user-b", self.complete_product("Return Product B"))
        item_a = {
            "productId": product_a["id"], "productName": "Return Product A",
            "variantId": f"{product_a['id']}-var-1",
            "quantity": 2, "unitPrice": 1599,
        }
        context_a = {
            "applicationId": app_a["id"],
            "shopName": "Return Shop A",
        }
        created = self.store.create_return_request(
            "user-a", "SD-RETURN-1", item_a, context_a,
            {"requestType": "SIZE_EXCHANGE", "reason": "SIZE_ISSUE", "quantity": 1},
        )
        self.assertEqual(created["status"], "REQUESTED")
        self.assertEqual(created["shopName"], "Return Shop A")
        self.assertEqual(created["itemSubtotal"], 1599)
        self.assertNotIn("customerUserId", created)
        self.assertNotIn("applicationId", created)
        self.assert_error(
            "return_request_exists",
            lambda: self.store.create_return_request(
                "user-a", "SD-RETURN-1", item_a, context_a,
                {"requestType": "SIZE_EXCHANGE", "reason": "SIZE_ISSUE", "quantity": 1},
            ),
        )
        self.assert_error(
            "invalid_return_quantity",
            lambda: self.store.create_return_request(
                "user-a", "SD-RETURN-2", item_a, context_a,
                {"requestType": "SIZE_EXCHANGE", "reason": "SIZE_ISSUE", "quantity": 3},
            ),
        )
        self.assert_error(
            "invalid_return_reason",
            lambda: self.store.create_return_request(
                "user-a", "SD-RETURN-3", item_a, context_a,
                {"requestType": "ISSUE_RETURN", "reason": "CUSTOMER_REQUEST", "quantity": 1},
            ),
        )
        seller_a = self.store.seller_return_requests("user-a")
        seller_b = self.store.seller_return_requests("user-b")
        self.assertEqual([row["id"] for row in seller_a], [created["id"]])
        self.assertEqual(seller_b, [])
        noted = self.store.seller_note_return_request(
            "user-a", created["id"], "Customer requested a smaller size."
        )
        self.assertEqual(noted["sellerNote"], "Customer requested a smaller size.")
        self.assert_error(
            "return_request_not_found",
            lambda: self.store.seller_note_return_request(
                "user-b", created["id"], "Must not cross seller boundary."
            ),
        )
        reviewing = self.store.admin_transition_return_request(
            "admin-a", created["id"], "UNDER_REVIEW", "Reviewing exchange eligibility"
        )
        self.assertEqual(reviewing["status"], "UNDER_REVIEW")
        approved = self.store.admin_transition_return_request(
            "admin-a", created["id"], "APPROVED", "Eligible size exchange"
        )
        self.assertEqual(approved["status"], "APPROVED")
        self.assert_error(
            "invalid_return_transition",
            lambda: self.store.admin_transition_return_request(
                "admin-a", created["id"], "REFUND_PENDING"
            ),
        )
        pickup = self.store.admin_transition_return_request(
            "admin-a", created["id"], "PICKUP_PENDING"
        )
        received = self.store.admin_transition_return_request(
            "admin-a", created["id"], "RECEIVED"
        )
        exchanged = self.store.admin_transition_return_request(
            "admin-a", created["id"], "EXCHANGED", "Replacement handed to customer",
            "exchange-local-001",
        )
        self.assertEqual((pickup["status"], received["status"], exchanged["status"]),
                         ("PICKUP_PENDING", "RECEIVED", "EXCHANGED"))
        self.assert_error(
            "return_request_closed",
            lambda: self.store.seller_note_return_request(
                "user-a", created["id"], "Too late to change notes."
            ),
        )
        admin_rows = self.store.admin_return_requests("admin-a")
        self.assertEqual(admin_rows[0]["applicationId"], app_a["id"])
        self.assertEqual(admin_rows[0]["customerUserId"], "user-a")
        with self.store.connect() as db:
            actions = {row[0] for row in db.execute(
                "SELECT action FROM local_admin_audit_log WHERE target_id=?", (created["id"],)
            )}
        self.assertIn("return_request_status", actions)
        self.assertNotEqual(product_a["id"], product_b["id"])

    def test_admin_fulfillment_override_is_scoped_and_audited(self) -> None:
        app_a = self.create_active_shop("user-a", "Shop A")
        app_b = self.create_active_shop("user-b", "Shop B")
        product_a = self.store.create_product_draft("user-a", self.complete_product("Product A"))
        self.store.create_product_draft("user-b", self.complete_product("Product B"))
        self.store.update_seller_fulfillment("user-a", "SD-ADMIN", {"status": "PROCESSING"})
        segments = self.store.admin_order_fulfillments("admin-a", "SD-ADMIN", [product_a["id"]])
        self.assertEqual([(row["shopName"], row["status"]) for row in segments], [("Shop A", "PROCESSING")])
        self.assertEqual(segments[0]["applicationId"], app_a["id"])
        overridden = self.store.admin_override_fulfillment(
            "admin-a", "SD-ADMIN", app_a["id"], [product_a["id"]],
            {"status": "SHIPPED", "carrier": "Delhivery", "trackingNumber": "DLV-ADMIN-1", "reason": "Correct seller dispatch state"},
        )
        self.assertEqual(overridden["status"], "SHIPPED")
        self.assertEqual(overridden["shipping"]["trackingNumber"], "DLV-ADMIN-1")
        corrected = self.store.admin_override_fulfillment(
            "admin-a", "SD-ADMIN", app_a["id"], [product_a["id"]],
            {"status": "PROCESSING", "reason": "Seller marked shipment by mistake"},
        )
        self.assertEqual(corrected["status"], "PROCESSING")
        self.assertIsNone(corrected["shipping"])
        self.assert_error(
            "order_shop_segment_not_found",
            lambda: self.store.admin_override_fulfillment(
                "admin-a", "SD-ADMIN", app_b["id"], [product_a["id"]],
                {"status": "READY", "reason": "Wrong shop must not be writable"},
            ),
        )
        self.assert_error(
            "admin_authorization_required",
            lambda: self.store.admin_order_fulfillments("user-a", "SD-ADMIN", [product_a["id"]]),
        )
        with self.store.connect() as db:
            rows = db.execute(
                "SELECT action,metadata_json FROM local_admin_audit_log WHERE action='shop_fulfillment_override' ORDER BY id"
            ).fetchall()
        self.assertEqual(len(rows), 2)
        metadata = json.loads(rows[-1]["metadata_json"])
        self.assertEqual((metadata["from"], metadata["to"]), ("SHIPPED", "PROCESSING"))
        self.assertEqual(metadata["reason"], "Seller marked shipment by mistake")

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


if __name__ == "__main__":
    unittest.main()
