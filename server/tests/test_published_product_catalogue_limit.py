import unittest

from scripts.styledash_shops import ShopWorkflow


class _FakeCursor:
    def fetchall(self):
        return []


class _FakeDb:
    def __init__(self):
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params=()):
        self.calls.append((query, params))
        return _FakeCursor()


class PublishedCatalogueLimitTests(unittest.TestCase):
    def test_default_has_no_catalogue_cap(self):
        workflow = ShopWorkflow.__new__(ShopWorkflow)
        db = _FakeDb()
        workflow.connect = lambda: db
        self.assertEqual(workflow._published_rows(), [])
        query, params = db.calls[-1]
        self.assertNotIn("LIMIT", query.upper())
        self.assertEqual(params, ())

    def test_explicit_limit_is_still_bounded(self):
        workflow = ShopWorkflow.__new__(ShopWorkflow)
        db = _FakeDb()
        workflow.connect = lambda: db
        workflow._published_rows(50_000)
        query, params = db.calls[-1]
        self.assertIn("LIMIT ?", query.upper())
        self.assertEqual(params, (10_000,))
