"""Synthetic unit tests for the production read-only aggregate catalogue audit."""
import unittest
from ci_public_catalogue import catalogue_metrics

def product(id, price=100, mrp=150):
    return {"id":id, "slug":"product-"+id,"price":price,
            "originalPrice":mrp,"active":True}

class TestPublicCatalogue(unittest.TestCase):
    def test_good_data(self):
        m=catalogue_metrics({"success":True,"products":[product("1"),product("2",125,125)]})
        self.assertTrue(m["passed"])
        self.assertEqual(m["published_products"],2)
        self.assertEqual(m["price_above_mrp"],0)

    def test_above_mrp_fails(self):
        m=catalogue_metrics({"success":True,"products":[product("1",200,150)]})
        self.assertFalse(m["passed"])
        self.assertEqual(m["price_above_mrp"],1)

    def test_duplicate_ids_fail(self):
        m=catalogue_metrics({"success":True,"products":[product("1"),product("1")]})
        self.assertFalse(m["passed"])
        self.assertGreater(m["duplicate_or_invalid_ids_slugs"],0)

    def test_invalid_price_and_inactive_fail(self):
        bad=product("1",float("inf"),150)
        bad["active"]=False
        m=catalogue_metrics({"success":True,"products":[bad]})
        self.assertFalse(m["passed"])
        self.assertEqual(m["missing_or_invalid_price_mrp"],1)
        self.assertEqual(m["not_active"],1)

    def test_empty_or_unsuccessful_catalogue_fails_closed(self):
        for p in (None,{},{"success":False,"products":[product("1")]},
                  {"success":True,"products":[]}, {"success":True,"products":None}):
            with self.subTest(p=p),self.assertRaises(ValueError):
                catalogue_metrics(p)

if __name__=="__main__":
    unittest.main()
