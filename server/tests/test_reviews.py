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

from scripts.styledash_reviews import ReviewWorkflow
from scripts.styledash_security import SecurityError, SecurityStore


class ReviewWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.security = SecurityStore(self.root / 'styledash.db', Fernet.generate_key().decode())
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
        self.reviews = ReviewWorkflow(self.security.path)
        self.payment_store = SimpleNamespace(lock=threading.RLock(), state={'orders': {}})

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def add_order(self, *, user_id=None, status='delivered', product_id='sd-prod-001', order_id='order-1') -> None:
        self.payment_store.state['orders'][order_id] = {
            'id': order_id,
            'userId': user_id or self.user['id'],
            'status': status,
            'createdAt': '2026-09-01T01:00:00+00:00',
            'updatedAt': '2026-09-01T02:00:00+00:00',
            'fulfillmentRequired': True,
            'items': [{'productId': product_id, 'productName': 'Test Product'}],
        }

    def assert_security_code(self, code: str, callback) -> None:
        with self.assertRaises(SecurityError) as caught:
            callback()
        self.assertEqual(caught.exception.code, code)

    def test_review_requires_delivered_purchase(self) -> None:
        self.add_order(status='placed')
        eligibility = self.reviews.eligibility(self.payment_store, self.user['id'], 'sd-prod-001')
        self.assertFalse(eligibility['eligible'])
        self.assert_security_code(
            'delivered_purchase_required',
            lambda: self.reviews.create(self.payment_store, self.user['id'], {
                'productId': 'sd-prod-001', 'rating': 5, 'comment': 'Great product',
            }),
        )

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

    def test_payment_test_order_does_not_grant_review_eligibility(self) -> None:
        self.add_order()
        self.payment_store.state['orders']['order-1']['isPaymentTestOrder'] = True
        self.assertFalse(
            self.reviews.eligibility(self.payment_store, self.user['id'], 'sd-prod-001')['eligible']
        )


if __name__ == '__main__':
    unittest.main()
