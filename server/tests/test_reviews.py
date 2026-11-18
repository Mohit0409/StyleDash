import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace

from cryptography.fernet import Fernet

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.styledash_admin import AdminStore
from scripts.styledash_reviews import ReviewWorkflow
from scripts.styledash_security import SecurityError, SecurityStore
from scripts.styledash_shops import ShopWorkflow


class ReviewWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.key = Fernet.generate_key().decode()
        self.security = SecurityStore(self.root / 'styledash.db', self.key)
        self.user, _raw, _csrf = self.security.register({
            'name': 'Review Customer',
            'email': 'review@example.test',
            'password': 'StrongPass123!',
            'phone': '9876543210',
        })
        self.other, _raw2, _csrf2 = self.security.register({
            'name': 'Other Customer',
            'email': 'other@example.test',
            'password': 'StrongPass123!',
            'phone': '9876543211',
        })
        self.owner, _raw3, _csrf3 = self.security.register({
            'name': 'Store Owner', 'email': 'owner@example.test',
            'password': 'StrongPass123!', 'phone': '9876543212',
        })
        self.shops = ShopWorkflow(self.security.path)
        self.store = self.shops.create_draft(self.owner['id'], {
            'shopName': 'Verified Review Store', 'ownerName': 'Store Owner',
            'category': 'Clothing & Fashion', 'description': 'A local shop for review tests.',
            'address': '1 Test Market', 'city': 'Neemuch', 'state': 'Madhya Pradesh',
            'pincode': '458441', 'businessInformation': 'Review test business',
        })
        self.reviews = ReviewWorkflow(self.security.path)
        self.admins = AdminStore(self.security.path, self.key)
        self.admin = self.admins.create_admin(
            'review-moderator', 'long administrator password 123', 'JBSWY3DPEHPK3PXP', ['ABCDEF123456']
        )
        self.payment_store = SimpleNamespace(lock=threading.RLock(), state={'orders': {}})

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def add_order(self, *, user_id=None, status='delivered', product_id='sd-prod-001', store_id=None, order_id='order-1') -> None:
        self.payment_store.state['orders'][order_id] = {
            'id': order_id,
            'userId': user_id or self.user['id'],
            'status': status,
            'createdAt': '2026-09-01T01:00:00+00:00',
            'updatedAt': '2026-09-01T02:00:00+00:00',
            'fulfillmentRequired': True,
            'items': [{'productId': product_id, 'productName': 'Test Product', **({'storeId': store_id} if store_id else {})}],
        }

    def assert_security_code(self, code: str, callback) -> None:
        with self.assertRaises(SecurityError) as caught:
            callback()
        self.assertEqual(caught.exception.code, code)

    def test_signed_in_unverified_product_review_is_private_until_approved(self) -> None:
        self.add_order(status='placed')
        eligibility = self.reviews.eligibility(self.payment_store, self.user['id'], 'sd-prod-001')
        self.assertTrue(eligibility['eligible'])
        self.assertIsNone(eligibility['orderId'])
        review = self.reviews.create(self.payment_store, self.user['id'], {
            'productId': 'sd-prod-001', 'rating': 5, 'comment': 'Great product',
        })
        self.assertFalse(review['verifiedPurchase'])
        self.assertEqual(review['status'], 'pending')
        self.assertEqual(self.reviews.list_product('sd-prod-001')['reviewCount'], 0)
        self.assertEqual(self.reviews.admin_list_product_reviews(self.admin['id'])[0]['id'], review['id'])
        self.reviews.moderate_product_review(self.admin['id'], review['id'], 'approved')
        self.assertEqual(self.reviews.list_product('sd-prod-001')['reviewCount'], 1)

    def test_verified_review_create_summary_edit_delete(self) -> None:
        self.add_order()
        created = self.reviews.create(self.payment_store, self.user['id'], {
            'productId': 'sd-prod-001',
            'rating': 5,
            'title': 'Excellent',
            'comment': 'Fits well and matches the listing.',
        })
        self.assertTrue(created['verifiedPurchase'])
        self.assertEqual(created['userName'], 'Review C.')
        self.assertEqual(created['status'], 'pending')
        self.assertEqual(self.reviews.list_product('sd-prod-001')['reviewCount'], 0)
        self.reviews.moderate_product_review(self.admin['id'], created['id'], 'approved')

        summary = self.reviews.list_product('sd-prod-001')
        self.assertEqual(summary['rating'], 5.0)
        self.assertEqual(summary['reviewCount'], 1)
        self.assertEqual(summary['distribution']['5'], 1)

        updated = self.reviews.edit(self.user['id'], created['id'], {
            'rating': 4,
            'title': '',
            'comment': 'Still good after using it for a few days.',
        })
        self.assertEqual(updated['rating'], 4)
        self.assertIsNone(updated['title'])
        self.assertEqual(updated['status'], 'pending')
        self.assertEqual(self.reviews.summaries(['sd-prod-001'])['sd-prod-001']['reviewCount'], 0)
        self.reviews.moderate_product_review(self.admin['id'], created['id'], 'approved')
        self.assertEqual(self.reviews.summaries(['sd-prod-001'])['sd-prod-001']['rating'], 4.0)

        self.reviews.delete(self.user['id'], created['id'])
        self.assertEqual(self.reviews.list_product('sd-prod-001')['reviewCount'], 0)

    def test_one_review_per_customer_and_product(self) -> None:
        self.add_order()
        payload = {'productId': 'sd-prod-001', 'rating': 5, 'comment': 'Verified purchase review'}
        self.reviews.create(self.payment_store, self.user['id'], payload)
        self.assert_security_code(
            'review_exists',
            lambda: self.reviews.create(self.payment_store, self.user['id'], payload),
        )

    def test_customer_cannot_edit_or_delete_another_review(self) -> None:
        self.add_order()
        created = self.reviews.create(self.payment_store, self.user['id'], {
            'productId': 'sd-prod-001', 'rating': 5, 'comment': 'Private ownership test',
        })
        self.assert_security_code(
            'review_not_found',
            lambda: self.reviews.edit(self.other['id'], created['id'], {
                'rating': 1, 'comment': 'Tampered review',
            }),
        )
        self.assert_security_code(
            'review_not_found',
            lambda: self.reviews.delete(self.other['id'], created['id']),
        )

    def test_payment_test_order_never_grants_verified_purchase_status(self) -> None:
        self.add_order()
        self.payment_store.state['orders']['order-1']['isPaymentTestOrder'] = True
        eligibility = self.reviews.eligibility(self.payment_store, self.user['id'], 'sd-prod-001')
        self.assertTrue(eligibility['eligible'])
        self.assertIsNone(eligibility['orderId'])
        created = self.reviews.create(self.payment_store, self.user['id'], {
            'productId': 'sd-prod-001', 'rating': 4, 'comment': 'A review without verified purchase',
        })
        self.assertFalse(created['verifiedPurchase'])
        self.assertEqual(created['status'], 'pending')
        self.assertEqual(self.reviews.list_product('sd-prod-001')['reviewCount'], 0)

    def test_verified_store_review_create_summary_edit_delete(self) -> None:
        self.add_order(store_id=self.store['id'])
        created = self.reviews.create_store(self.payment_store, self.user['id'], {
            'storeId': self.store['id'], 'rating': 5, 'title': 'Helpful team',
            'comment': 'The local store handled the delivered order very well.',
        })
        self.assertTrue(created['verifiedPurchase'])
        self.assertEqual(created['userName'], 'Verified local customer')
        summary = self.reviews.list_store(self.store['id'])
        self.assertEqual((summary['rating'], summary['reviewCount']), (0, 0))
        queued = self.reviews.admin_list_store_reviews(self.admin['id'])
        self.assertEqual((len(queued), queued[0]['id'], queued[0]['status']), (1, created['id'], 'pending'))
        self.reviews.moderate_store_review(self.admin['id'], created['id'], 'approved')
        summary = self.reviews.list_store(self.store['id'])
        self.assertEqual((summary['rating'], summary['reviewCount']), (5.0, 1))
        updated = self.reviews.edit_store(self.user['id'], created['id'], {
            'rating': 4, 'title': '', 'comment': 'Still a reliable neighbourhood store.',
        })
        self.assertEqual((updated['rating'], updated['title'], updated['status']), (4, None, 'pending'))
        self.assertEqual(self.reviews.list_store(self.store['id'])['reviewCount'], 0)
        self.reviews.moderate_store_review(self.admin['id'], created['id'], 'approved')
        self.reviews.delete_store(self.user['id'], created['id'])
        self.assertEqual(self.reviews.list_store(self.store['id'])['reviewCount'], 0)

    def test_store_review_moderation_requires_an_administrator_and_persists_schema_version(self) -> None:
        self.add_order(store_id=self.store['id'])
        created = self.reviews.create_store(self.payment_store, self.user['id'], {
            'storeId': self.store['id'], 'rating': 5, 'comment': 'Awaiting private review approval.',
        })
        self.assert_security_code(
            'admin_required', lambda: self.reviews.admin_list_store_reviews(self.user['id'])
        )
        self.assert_security_code(
            'invalid_store_review_status',
            lambda: self.reviews.moderate_store_review(self.admin['id'], created['id'], 'published'),
        )
        with self.reviews.connect() as db:
            versions = {row['version'] for row in db.execute('SELECT version FROM review_schema_migrations')}
            schema = db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='store_reviews'").fetchone()['sql']
        self.assertTrue({3, 4}.issubset(versions))
        self.assertIn("'pending'", schema)
        self.assertIn("'published'", schema)

    def test_store_review_migration_preserves_legacy_published_reviews_as_approved(self) -> None:
        self.add_order(store_id=self.store['id'])
        created = self.reviews.create_store(self.payment_store, self.user['id'], {
            'storeId': self.store['id'], 'rating': 5, 'comment': 'Legacy public review retained after upgrade.',
        })
        with self.reviews.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('ALTER TABLE store_reviews RENAME TO store_reviews_current')
            db.execute("""CREATE TABLE store_reviews(
                id TEXT PRIMARY KEY, store_id TEXT NOT NULL REFERENCES vendor_applications(id) ON DELETE CASCADE,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, order_id TEXT NOT NULL,
                rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5), title TEXT, comment TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'published' CHECK(status IN ('published','hidden')),
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE(user_id, store_id)
            )""")
            db.execute(
                """INSERT INTO store_reviews(id,store_id,user_id,order_id,rating,title,comment,status,created_at,updated_at)
                   SELECT id,store_id,user_id,order_id,rating,title,comment,'published',created_at,updated_at
                   FROM store_reviews_current"""
            )
            db.execute('DROP TABLE store_reviews_current')
            # Simulate an original v2 database before both moderation and
            # v5 photo/open-review migrations, not an already-v5 database.
            db.execute('DELETE FROM review_schema_migrations WHERE version IN (3, 4, 5)')
            db.commit()
        upgraded = ReviewWorkflow(self.security.path)
        summary = upgraded.list_store(self.store['id'])
        self.assertEqual((summary['reviewCount'], summary['reviews'][0]['id'], summary['reviews'][0]['status']), (1, created['id'], 'approved'))
        with upgraded.connect() as db:
            versions = {row['version'] for row in db.execute('SELECT version FROM review_schema_migrations')}
        self.assertTrue({3, 4}.issubset(versions))

    def test_v4_migration_maps_v3_approved_reviews_to_the_rollback_safe_storage_value(self) -> None:
        self.add_order(store_id=self.store['id'])
        created = self.reviews.create_store(self.payment_store, self.user['id'], {
            'storeId': self.store['id'], 'rating': 5, 'comment': 'A v3 approved review remains visible after the compatibility migration.',
        })
        with self.reviews.connect() as db:
            # Model a database that was already migrated by the first v3
            # release, before the v4 rollback-compatibility patch is applied.
            db.execute('BEGIN IMMEDIATE')
            db.execute('ALTER TABLE store_reviews RENAME TO store_reviews_current')
            db.execute("""CREATE TABLE store_reviews(
                id TEXT PRIMARY KEY, store_id TEXT NOT NULL REFERENCES vendor_applications(id) ON DELETE CASCADE,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, order_id TEXT NOT NULL,
                rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5), title TEXT, comment TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected','hidden')),
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE(user_id, store_id)
            )""")
            db.execute(
                """INSERT INTO store_reviews(id,store_id,user_id,order_id,rating,title,comment,status,created_at,updated_at)
                   SELECT id,store_id,user_id,order_id,rating,title,comment,'approved',created_at,updated_at
                   FROM store_reviews_current"""
            )
            db.execute('DROP TABLE store_reviews_current')
            # Simulate a v3 database; v5 photo schema is not installed yet.
            db.execute('DELETE FROM review_schema_migrations WHERE version IN (4, 5)')
            db.commit()
        upgraded = ReviewWorkflow(self.security.path)
        with upgraded.connect() as db:
            stored_status = db.execute(
                'SELECT status FROM store_reviews WHERE id=?', (created['id'],)
            ).fetchone()['status']
            versions = {row['version'] for row in db.execute('SELECT version FROM review_schema_migrations')}
        summary = upgraded.list_store(self.store['id'])
        self.assertEqual(stored_status, 'published')
        self.assertIn(4, versions)
        self.assertEqual((summary['reviewCount'], summary['reviews'][0]['status']), (1, 'approved'))

    def test_moderation_schema_keeps_the_v2_published_rollback_contract(self) -> None:
        self.add_order(store_id=self.store['id'])
        created = self.reviews.create_store(self.payment_store, self.user['id'], {
            'storeId': self.store['id'], 'rating': 5, 'comment': 'Approved review remains rollback compatible.',
        })
        self.reviews.moderate_store_review(self.admin['id'], created['id'], 'approved')
        self.add_order(user_id=self.other['id'], store_id=self.store['id'], order_id='legacy-rollback-order')
        now = '2026-09-22T12:00:00+00:00'
        with self.reviews.connect() as db:
            # This is the status and insert shape used by the v2 rollback
            # code. It must remain valid after the v4 migration.
            self.assertEqual(
                db.execute('SELECT status FROM store_reviews WHERE id=?', (created['id'],)).fetchone()['status'],
                'published',
            )
            db.execute(
                """INSERT INTO store_reviews(id,store_id,user_id,order_id,rating,title,comment,status,created_at,updated_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?)""",
                ('legacy-rollback-review', self.store['id'], self.other['id'], 'legacy-rollback-order', 4,
                 None, 'A review created while the v2 rollback code is active.', 'published', now, now),
            )
            db.commit()
        summary = self.reviews.list_store(self.store['id'])
        self.assertEqual(summary['reviewCount'], 2)
        self.assertEqual({item['status'] for item in summary['reviews']}, {'approved'})

    def test_unverified_store_review_is_private_and_blocks_idor_and_owner(self) -> None:
        payload = {'storeId': self.store['id'], 'rating': 5, 'comment': 'Review without delivery'}
        created = self.reviews.create_store(self.payment_store, self.user['id'], payload)
        self.assertFalse(created['verifiedPurchase'])
        self.assertEqual(created['status'], 'pending')
        self.assertEqual(self.reviews.list_store(self.store['id'])['reviewCount'], 0)
        self.assert_security_code(
            'store_review_not_found',
            lambda: self.reviews.edit_store(self.other['id'], created['id'], {
                'rating': 1, 'comment': 'Cross-account edit',
            }),
        )
        self.add_order(user_id=self.owner['id'], store_id=self.store['id'], order_id='owner-order')
        self.assert_security_code(
            'own_store_review_forbidden',
            lambda: self.reviews.create_store(self.payment_store, self.owner['id'], {
                'storeId': self.store['id'], 'rating': 5, 'comment': 'Owner review attempt',
            }),
        )

    def test_store_review_rejects_unsupported_fields(self) -> None:
        self.add_order(store_id=self.store['id'])
        self.assert_security_code('invalid_store_review', lambda: self.reviews.create_store(
            self.payment_store, self.user['id'],
            {'storeId': self.store['id'], 'rating': 5, 'comment': 'A valid comment', 'userId': self.other['id']},
        ))


    def test_v5_migration_adds_private_photo_columns(self) -> None:
        with self.reviews.connect() as db:
            versions = {row['version'] for row in db.execute(
                'SELECT version FROM review_schema_migrations'
            )}
            product_cols = {row['name'] for row in db.execute(
                'PRAGMA table_info(product_reviews)'
            )}
            store_cols = {row['name'] for row in db.execute(
                'PRAGMA table_info(store_reviews)'
            )}
        self.assertTrue({3, 4, 5}.issubset(versions))
        self.assertIn('photo_webp', product_cols)
        self.assertIn('photo_webp', store_cols)

    def test_synthetic_webp_photo_private_until_moderated_and_after_edit(self) -> None:
        import base64
        # Original 2x2 test-only WebP image; no real user photo.
        image_data_url = 'data:image/webp;base64,UklGRiQAAABXRUJQVlA4IBgAAAAwAQCdASoCAAIAAkA4JaQAA3AA/vucwAA='
        expected_photo = base64.b64decode(image_data_url.split(',', 1)[1])
        self.add_order()
        created = self.reviews.create(self.payment_store, self.user['id'], {
            'productId': 'sd-prod-001', 'rating': 5,
            'comment': 'Small synthetic photo privacy test.',
            'photoDataUrl': image_data_url,
        })
        self.assertEqual(created['status'], 'pending')
        self.assertTrue(created['hasPhoto'])
        self.assertIsNone(created['photoUrl'])
        self.assertEqual(self.reviews.list_product('sd-prod-001')['reviewCount'], 0)
        self.assert_security_code('photo_not_found', lambda:
            self.reviews.review_photo(created['id']))
        self.assertEqual(
            self.reviews.review_photo(created['id'], admin_id=self.admin['id']),
            expected_photo,
        )
        self.reviews.moderate_product_review(self.admin['id'], created['id'], 'approved')
        public = self.reviews.list_product('sd-prod-001')
        self.assertEqual(public['reviewCount'], 1)
        self.assertEqual(public['reviews'][0]['photoUrl'], '/api/review-photo/' + created['id'])
        self.assertEqual(self.reviews.review_photo(created['id']), expected_photo)
        modified = self.reviews.edit(self.user['id'], created['id'], {
            'rating': 4, 'title': 'Updated privately',
            'comment': 'Editing hides the review and its photo again.',
        })
        self.assertEqual(modified['status'], 'pending')
        self.assertIsNone(modified['photoUrl'])
        self.assertEqual(self.reviews.list_product('sd-prod-001')['reviewCount'], 0)
        self.assert_security_code('photo_not_found', lambda:
            self.reviews.review_photo(created['id']))

    def test_invalid_review_photo_is_rejected_before_database_write(self) -> None:
        self.add_order()
        for value in ('data:image/jpeg;base64,AA==',
                      'data:image/webp;base64,***',
                      'data:image/webp;base64,AA=='):
            with self.subTest(value=value[:25]):
                self.assert_security_code('invalid_review_photo', lambda:
                    self.reviews.create(self.payment_store, self.user['id'], {
                        'productId': 'sd-prod-001', 'rating': 5,
                        'comment': 'Reject malformed image upload.',
                        'photoDataUrl': value,
                    }))
        self.assertEqual(self.reviews.list_product('sd-prod-001')['reviewCount'], 0)


if __name__ == '__main__':
    unittest.main()
