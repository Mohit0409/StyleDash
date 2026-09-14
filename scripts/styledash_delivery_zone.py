from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

SUPPORTED_MODES = {"pincode", "polygon"}


class DeliveryZoneConfigError(ValueError):
    pass


@dataclass(frozen=True)
class DeliveryZone:
    zone_id: str
    name: str
    ring: tuple[tuple[float, float], ...]  # GeoJSON order: longitude, latitude


def _is_finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _same_point(a: tuple[float, float], b: tuple[float, float]) -> bool:
    return abs(a[0] - b[0]) <= 1e-12 and abs(a[1] - b[1]) <= 1e-12


def _normalize_ring(raw_ring: Any) -> tuple[tuple[float, float], ...]:
    if not isinstance(raw_ring, list) or len(raw_ring) < 4:
        raise DeliveryZoneConfigError("Delivery-zone polygon needs at least three points plus closure.")
    points: list[tuple[float, float]] = []
    for raw_point in raw_ring:
        if not isinstance(raw_point, list) or len(raw_point) != 2:
            raise DeliveryZoneConfigError("Each delivery-zone point must be [longitude, latitude].")
        longitude, latitude = raw_point
        if not _is_finite_number(longitude) or not _is_finite_number(latitude):
            raise DeliveryZoneConfigError("Delivery-zone coordinates must be finite numbers.")
        longitude = float(longitude)
        latitude = float(latitude)
        if not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
            raise DeliveryZoneConfigError("Delivery-zone coordinates are outside valid earth bounds.")
        points.append((longitude, latitude))
    if not _same_point(points[0], points[-1]):
        raise DeliveryZoneConfigError("Delivery-zone polygon ring must be closed.")
    if len({point for point in points[:-1]}) < 3:
        raise DeliveryZoneConfigError("Delivery-zone polygon needs at least three distinct points.")
    return tuple(points)


def _point_on_segment(
    point: tuple[float, float], start: tuple[float, float], end: tuple[float, float]
) -> bool:
    px, py = point
    ax, ay = start
    bx, by = end
    cross = (px - ax) * (by - ay) - (py - ay) * (bx - ax)
    if abs(cross) > 1e-10:
        return False
    return min(ax, bx) - 1e-10 <= px <= max(ax, bx) + 1e-10 and min(ay, by) - 1e-10 <= py <= max(ay, by) + 1e-10


def point_in_ring(latitude: float, longitude: float, ring: Iterable[tuple[float, float]]) -> bool:
    if not _is_finite_number(latitude) or not _is_finite_number(longitude):
        return False
    x = float(longitude)
    y = float(latitude)
    if not -180 <= x <= 180 or not -90 <= y <= 90:
        return False
    points = tuple(ring)
    inside = False
    for index in range(len(points) - 1):
        start = points[index]
        end = points[index + 1]
        if _point_on_segment((x, y), start, end):
            return True
        x1, y1 = start
        x2, y2 = end
        crosses = (y1 > y) != (y2 > y)
        if crosses:
            intersection_x = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < intersection_x:
                inside = not inside
    return inside


class DeliveryZoneIndex:
    def __init__(self, mode: str = "pincode", zones: Iterable[DeliveryZone] = ()):
        normalized_mode = str(mode).strip().casefold()
        if normalized_mode not in SUPPORTED_MODES:
            raise DeliveryZoneConfigError(f"Unsupported delivery-zone mode: {mode!r}")
        self.mode = normalized_mode
        self.zones = tuple(zones)
        if self.mode == "polygon" and not self.zones:
            raise DeliveryZoneConfigError("Polygon delivery mode requires at least one active zone.")

    @classmethod
    def from_geojson(cls, payload: dict[str, Any]) -> "DeliveryZoneIndex":
        if not isinstance(payload, dict) or payload.get("type") != "FeatureCollection":
            raise DeliveryZoneConfigError("Delivery-zone config must be a GeoJSON FeatureCollection.")
        mode = payload.get("enforcementMode", "pincode")
        zones: list[DeliveryZone] = []
        features = payload.get("features", [])
        if not isinstance(features, list):
            raise DeliveryZoneConfigError("Delivery-zone features must be a list.")
        for feature in features:
            if not isinstance(feature, dict) or feature.get("type") != "Feature":
                raise DeliveryZoneConfigError("Delivery-zone entries must be GeoJSON Features.")
            properties = feature.get("properties") or {}
            if properties.get("active") is not True:
                continue
            geometry = feature.get("geometry") or {}
            if geometry.get("type") != "Polygon":
                raise DeliveryZoneConfigError("Only Polygon delivery zones are supported.")
            coordinates = geometry.get("coordinates")
            if not isinstance(coordinates, list) or len(coordinates) != 1:
                raise DeliveryZoneConfigError("Delivery zones must contain one outer polygon ring and no holes.")
            zone_id = str(properties.get("id") or "").strip()
            name = str(properties.get("name") or "").strip()
            if not zone_id or not name:
                raise DeliveryZoneConfigError("Active delivery zones require id and name properties.")
            zones.append(DeliveryZone(zone_id=zone_id, name=name, ring=_normalize_ring(coordinates[0])))
        return cls(mode=mode, zones=zones)

    @classmethod
    def load(cls, path: str | Path) -> "DeliveryZoneIndex":
        config_path = Path(path)
        try:
            payload = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise DeliveryZoneConfigError(f"Unable to read delivery-zone config: {config_path}") from exc
        return cls.from_geojson(payload)

    def locate(self, latitude: Any, longitude: Any) -> DeliveryZone | None:
        if not _is_finite_number(latitude) or not _is_finite_number(longitude):
            return None
        for zone in self.zones:
            if point_in_ring(float(latitude), float(longitude), zone.ring):
                return zone
        return None
    def check(
        self,
        pincode: str,
        supported_pincodes: Iterable[str],
        *,
        latitude: Any = None,
        longitude: Any = None,
    ) -> dict[str, Any]:
        supported = {str(item).strip() for item in supported_pincodes}
        if pincode not in supported:
            return {"serviceable": False, "serviceabilityMethod": "pincode", "reason": "unsupported_pincode"}
        if self.mode == "pincode":
            return {"serviceable": True, "serviceabilityMethod": "pincode", "requiresLocation": False}
        if latitude is None or longitude is None:
            return {"serviceable": False, "serviceabilityMethod": "polygon", "requiresLocation": True, "reason": "location_required"}
        zone = self.locate(latitude, longitude)
        if zone is None:
            return {"serviceable": False, "serviceabilityMethod": "polygon", "requiresLocation": False, "reason": "outside_delivery_zone"}
        return {
            "serviceable": True,
            "serviceabilityMethod": "polygon",
            "requiresLocation": False,
            "zoneId": zone.zone_id,
            "zoneName": zone.name,
        }

    def public_geojson(self) -> dict[str, Any]:
        return {
            "type": "FeatureCollection",
            "enforcementMode": self.mode,
            "features": [
                {
                    "type": "Feature",
                    "properties": {"id": zone.zone_id, "name": zone.name},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[list(point) for point in zone.ring]],
                    },
                }
                for zone in self.zones
            ],
        }
