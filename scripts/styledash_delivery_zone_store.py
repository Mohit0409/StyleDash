from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

try:
    from scripts.styledash_delivery_zone import DeliveryZoneIndex
except ModuleNotFoundError:
    from styledash_delivery_zone import DeliveryZoneIndex


DEFAULT_CONFIGURATION: dict[str, Any] = {
    "type": "FeatureCollection",
    "enforcementMode": "pincode",
    "features": [],
}


class DeliveryZoneStore:
    """Persistent delivery-zone configuration stored beside production business data."""

    def __init__(self, database_path: str | Path):
        self.path = Path(database_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._migrate()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _migrate(self) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS delivery_zone_configuration (
                    id INTEGER PRIMARY KEY CHECK(id = 1),
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    updated_by TEXT
                )
                """
            )
            existing = connection.execute(
                "SELECT id FROM delivery_zone_configuration WHERE id = 1"
            ).fetchone()
            if existing is None:
                connection.execute(
                    """
                    INSERT INTO delivery_zone_configuration(id, payload_json, updated_at, updated_by)
                    VALUES(1, ?, ?, NULL)
                    """,
                    (json.dumps(DEFAULT_CONFIGURATION, separators=(",", ":")), self._now()),
                )

    def configuration(self) -> dict[str, Any]:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT payload_json FROM delivery_zone_configuration WHERE id = 1"
            ).fetchone()
        if row is None:
            return dict(DEFAULT_CONFIGURATION)
        payload = json.loads(str(row["payload_json"]))
        if not isinstance(payload, dict):
            raise ValueError("Stored delivery-zone configuration is invalid.")
        return payload

    def policy(self) -> DeliveryZoneIndex:
        return DeliveryZoneIndex.from_geojson(self.configuration())

    def public_configuration(self) -> dict[str, Any]:
        return self.policy().public_geojson()

    def replace_configuration(
        self,
        payload: dict[str, Any],
        *,
        updated_by: str | None = None,
    ) -> dict[str, Any]:
        policy = DeliveryZoneIndex.from_geojson(payload)
        canonical = {
            "type": "FeatureCollection",
            "enforcementMode": policy.mode,
            "features": payload.get("features", []),
        }
        encoded = json.dumps(canonical, separators=(",", ":"))
        with self._connection() as connection:
            connection.execute(
                """
                UPDATE delivery_zone_configuration
                   SET payload_json = ?, updated_at = ?, updated_by = ?
                 WHERE id = 1
                """,
                (encoded, self._now(), updated_by),
            )
        return self.configuration()

    def set_enforcement_mode(
        self,
        mode: str,
        *,
        updated_by: str | None = None,
    ) -> dict[str, Any]:
        payload = self.configuration()
        payload["enforcementMode"] = str(mode).strip().casefold()
        return self.replace_configuration(payload, updated_by=updated_by)
