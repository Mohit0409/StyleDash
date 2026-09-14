from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.styledash_delivery_zone import DeliveryZoneConfigError
from scripts.styledash_delivery_zone_store import DeliveryZoneStore


def polygon_payload():
    return {
        "type": "FeatureCollection",
        "enforcementMode": "polygon",
        "features": [{
            "type": "Feature",
            "properties": {"id": "neemuch-core", "name": "Neemuch Core", "active": True},
            "geometry": {"type": "Polygon", "coordinates": [[
                [74.84, 24.45], [74.89, 24.45], [74.89, 24.50],
                [74.84, 24.50], [74.84, 24.45],
            ]]},
        }],
    }


class DeliveryZoneStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "styledash.sqlite3"
        self.store = DeliveryZoneStore(self.db)

    def tearDown(self):
        self.temp.cleanup()

    def test_defaults_to_pincode_mode_with_no_zones(self):
        self.assertEqual(self.store.configuration(), {
            "type": "FeatureCollection",
            "enforcementMode": "pincode",
            "features": [],
        })

    def test_polygon_configuration_persists_and_is_queryable(self):
        saved = self.store.replace_configuration(polygon_payload(), updated_by="admin-1")
        self.assertEqual(saved["enforcementMode"], "polygon")
        self.assertEqual(saved["features"][0]["properties"]["id"], "neemuch-core")

        reopened = DeliveryZoneStore(self.db)
        result = reopened.policy().check(
            "458441", {"458441"}, latitude=24.47, longitude=74.86,
        )
        self.assertTrue(result["serviceable"])
        self.assertEqual(result["zoneId"], "neemuch-core")

    def test_empty_polygon_mode_is_rejected_without_mutating_existing_config(self):
        self.store.replace_configuration(polygon_payload())
        bad = {
            "type": "FeatureCollection",
            "enforcementMode": "polygon",
            "features": [],
        }
        with self.assertRaises(DeliveryZoneConfigError):
            self.store.replace_configuration(bad)
        self.assertEqual(self.store.configuration()["features"][0]["properties"]["id"], "neemuch-core")

    def test_cannot_switch_empty_store_to_polygon_mode(self):
        with self.assertRaises(DeliveryZoneConfigError):
            self.store.set_enforcement_mode("polygon")
        self.assertEqual(self.store.configuration()["enforcementMode"], "pincode")

    def test_switching_back_to_pincode_retains_the_saved_polygon_draft(self):
        self.store.replace_configuration(polygon_payload())
        saved = self.store.set_enforcement_mode("pincode", updated_by="admin-1")
        self.assertEqual(saved["enforcementMode"], "pincode")
        self.assertEqual(saved["features"], polygon_payload()["features"])
        self.assertEqual(self.store.policy().mode, "pincode")

    def test_public_configuration_does_not_expose_admin_metadata(self):
        self.store.replace_configuration(polygon_payload(), updated_by="private-admin")
        public = self.store.public_configuration()
        feature = public["features"][0]
        self.assertEqual(feature["properties"], {
            "id": "neemuch-core",
            "name": "Neemuch Core",
        })
        self.assertNotIn("updated_by", str(public))


if __name__ == "__main__":
    unittest.main()
