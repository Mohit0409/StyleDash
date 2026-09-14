from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "styledash_delivery_zone.py"

spec = importlib.util.spec_from_file_location("styledash_delivery_zone", MODULE_PATH)
assert spec and spec.loader
ZONE = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = ZONE
spec.loader.exec_module(ZONE)


def square_payload(mode="polygon"):
    return {
        "type": "FeatureCollection",
        "enforcementMode": mode,
        "features": [{
            "type": "Feature",
            "properties": {"id": "neemuch-core", "name": "Neemuch Core", "active": True},
            "geometry": {"type": "Polygon", "coordinates": [[
                [74.85, 24.45], [74.90, 24.45], [74.90, 24.50], [74.85, 24.50], [74.85, 24.45],
            ]]},
        }],
    }


class DeliveryZoneTests(unittest.TestCase):
    def test_pincode_mode_preserves_current_launch_behavior(self):
        index = ZONE.DeliveryZoneIndex.from_geojson({
            "type": "FeatureCollection", "enforcementMode": "pincode", "features": [],
        })
        self.assertEqual(index.check("458441", {"458441"}), {
            "serviceable": True,
            "serviceabilityMethod": "pincode",
            "requiresLocation": False,
        })

    def test_polygon_mode_requires_coordinates(self):
        index = ZONE.DeliveryZoneIndex.from_geojson(square_payload())
        result = index.check("458441", {"458441"})
        self.assertFalse(result["serviceable"])
        self.assertTrue(result["requiresLocation"])
        self.assertEqual(result["reason"], "location_required")

    def test_inside_polygon_is_serviceable(self):
        index = ZONE.DeliveryZoneIndex.from_geojson(square_payload())
        result = index.check("458441", {"458441"}, latitude=24.475, longitude=74.875)
        self.assertTrue(result["serviceable"])
        self.assertEqual(result["zoneId"], "neemuch-core")
        self.assertEqual(result["zoneName"], "Neemuch Core")

    def test_outside_polygon_is_rejected(self):
        index = ZONE.DeliveryZoneIndex.from_geojson(square_payload())
        result = index.check("458441", {"458441"}, latitude=24.60, longitude=74.875)
        self.assertFalse(result["serviceable"])
        self.assertEqual(result["reason"], "outside_delivery_zone")

    def test_polygon_boundary_counts_as_inside(self):
        index = ZONE.DeliveryZoneIndex.from_geojson(square_payload())
        result = index.check("458441", {"458441"}, latitude=24.45, longitude=74.875)
        self.assertTrue(result["serviceable"])

    def test_unsupported_pincode_stays_rejected_even_inside_polygon(self):
        index = ZONE.DeliveryZoneIndex.from_geojson(square_payload())
        result = index.check("458440", {"458441"}, latitude=24.475, longitude=74.875)
        self.assertFalse(result["serviceable"])
        self.assertEqual(result["reason"], "unsupported_pincode")

    def test_polygon_mode_fails_closed_without_active_zone(self):
        with self.assertRaises(ZONE.DeliveryZoneConfigError):
            ZONE.DeliveryZoneIndex.from_geojson({
                "type": "FeatureCollection", "enforcementMode": "polygon", "features": [],
            })

    def test_loads_geojson_file_and_exposes_public_shape(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "zones.geojson"
            path.write_text(json.dumps(square_payload()), encoding="utf-8")
            index = ZONE.DeliveryZoneIndex.load(path)
        public = index.public_geojson()
        self.assertEqual(public["enforcementMode"], "polygon")
        self.assertEqual(public["features"][0]["properties"], {
            "id": "neemuch-core", "name": "Neemuch Core",
        })
        self.assertEqual(public["features"][0]["geometry"]["type"], "Polygon")


if __name__ == "__main__":
    unittest.main()
