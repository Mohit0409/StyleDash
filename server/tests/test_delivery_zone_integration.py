from __future__ import annotations

import json
import tempfile
import sys
import unittest
from pathlib import Path

from scripts.styledash_delivery_zone_store import DeliveryZoneStore

ROOT = Path(__file__).resolve().parents[2]
try:
    from test_styledash_server import SERVER, FakeGateway
except ModuleNotFoundError:
    tests_path = str(Path(__file__).resolve().parent)
    sys.path.insert(0, tests_path)
    try:
        from test_styledash_server import SERVER, FakeGateway
    finally:
        sys.path.remove(tests_path)

def polygon_configuration() -> dict:
    return {
        "type": "FeatureCollection",
        "enforcementMode": "polygon",
        "features": [{
            "type": "Feature",
            "properties": {
                "id": "neemuch-core",
                "name": "Neemuch Core",
                "active": True,
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [74.84, 24.45], [74.89, 24.45],
                    [74.89, 24.50], [74.84, 24.50],
                    [74.84, 24.45],
                ]],
            },
        }],
    }


class DeliveryZoneIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.gateway = FakeGateway()
        self.zone_store = DeliveryZoneStore(self.root / "zones.sqlite3")
        self.zone_store.replace_configuration(polygon_configuration())
        self.service = SERVER.PaymentService(
            ROOT / "server" / "payment-data" / "catalog.json",
            ROOT / "server" / "payment-data" / "settings.json",
            self.root / "orders",
            key_id="rzp_test_placeholder",
            key_secret="test_secret_placeholder",
            webhook_secret="webhook_secret_placeholder",
            mode="test",
            gateway=self.gateway,
            ordering_enabled=True,
            delivery_zone_store=self.zone_store,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def payload(self, *, latitude=None, longitude=None, payment_method="cod") -> dict:
        address = {
            "name": "Test Customer",
            "phone": "9999999999",
            "street": "123 Test Street",
            "city": "Neemuch",
            "pincode": "458441",
        }
        if latitude is not None:
            address["latitude"] = latitude
        if longitude is not None:
            address["longitude"] = longitude
        return {
            "items": [{
                "productId": "sd-prod-001",
                "variantId": "sd-prod-001-var-2",
                "quantity": 1,
            }],
            "address": address,
            "userId": "test-user",
            "deliveryMethod": "standard",
            "couponCode": None,
            "paymentMethod": payment_method,
        }

    def assert_api_error(self, code: str, callback) -> None:
        with self.assertRaises(SERVER.ApiError) as caught:
            callback()
        self.assertEqual(caught.exception.code, code)

    def test_serviceability_requires_location_and_accepts_inside_pin(self) -> None:
        missing = self.service.check_serviceability("458441")
        self.assertFalse(missing["serviceable"])
        self.assertTrue(missing["locationRequired"])
        self.assertEqual(missing["enforcementMode"], "polygon")
        inside = self.service.check_serviceability(
            "458441", latitude=24.47, longitude=74.86,
        )
        self.assertTrue(inside["serviceable"])
        self.assertEqual(inside["zoneId"], "neemuch-core")
        self.assertEqual(inside["zoneName"], "Neemuch Core")

        outside = self.service.check_serviceability(
            "458441", latitude=24.60, longitude=74.95,
        )
        self.assertFalse(outside["serviceable"])
        self.assertEqual(outside["reason"], "outside_delivery_zone")

    def test_calculate_order_enforces_and_persists_delivery_zone(self) -> None:
        self.assert_api_error(
            "delivery_location_required",
            lambda: self.service.calculate_order(self.payload()),
        )
        self.assert_api_error(
            "outside_delivery_zone",
            lambda: self.service.calculate_order(
                self.payload(latitude=24.60, longitude=74.95)
            ),
        )

        quote = self.service.calculate_order(
            self.payload(latitude=24.47, longitude=74.86)
        )
        self.assertEqual(quote["address"]["deliveryZoneId"], "neemuch-core")
        self.assertEqual(quote["address"]["deliveryZoneName"], "Neemuch Core")
        self.assertEqual(quote["address"]["latitude"], 24.47)
        self.assertEqual(quote["address"]["longitude"], 74.86)

    def test_rejected_cod_location_does_not_mutate_order_state(self) -> None:
        before = json.loads(json.dumps(self.service.store.state))
        self.assert_api_error(
            "outside_delivery_zone",
            lambda: self.service.place_cod_order(
                self.payload(latitude=24.60, longitude=74.95),
                "geo-cod-outside",
            ),
        )
        self.assertEqual(self.service.store.state, before)
        self.assertEqual(self.gateway.calls, [])

    def test_rejected_online_location_never_calls_gateway(self) -> None:
        before = json.loads(json.dumps(self.service.store.state))
        self.assert_api_error(
            "outside_delivery_zone",
            lambda: self.service.create_razorpay_order(
                self.payload(
                    latitude=24.60,
                    longitude=74.95,
                    payment_method="upi",
                ),
                "geo-online-outside",
            ),
        )
        self.assertEqual(self.service.store.state, before)
        self.assertEqual(self.gateway.calls, [])


if __name__ == "__main__":
    unittest.main()
