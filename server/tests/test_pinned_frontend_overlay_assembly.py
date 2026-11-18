"""Offline regression tests for the pinned public overlay/PWA assembly."""
from collections import Counter
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import assemble_pinned_frontend_overlays as overlays


class PinnedFrontendOverlayAssemblyTests(unittest.TestCase):
    def test_all_25_targets_validate_with_explicit_source_classification(self):
        entries, mapping = overlays.validate()
        self.assertEqual(len(entries), 25)
        self.assertEqual(
            Counter(item["kind"] for item in mapping["files"]),
            Counter(overlays.EXPECTED_KINDS),
        )
        targets = {item["target"] for item in mapping["files"]}
        self.assertNotIn("server/index.html", targets)
        self.assertFalse(any("index-MMTPd8z_" in item for item in targets))

    def test_pwa_graph_contains_offline_fallback_and_all_static_outputs(self):
        _, mapping = overlays.validate()
        pwa = {
            item["target"] for item in mapping["files"]
            if item["kind"] == "reproducible-static-pwa"
        }
        self.assertEqual(pwa, overlays.PWA_TARGETS)
        worker = (
            overlays.ROOT
            / "deployment-snapshots/vibe4you-20261116-gst-r2/frontend-runtime/site/sw.js"
        ).read_text("utf-8")
        self.assertIn("/vibe4you-app/offline.html", worker)

    def test_temp_assembly_copies_only_the_25_pinned_public_files(self):
        entries, _ = overlays.validate()
        expected = {target.as_posix(): sha for target, _, sha in entries}
        with tempfile.TemporaryDirectory(prefix="v4y-overlay-stage-parent-") as temp:
            output = Path(temp) / "bundle"
            overlays.assemble_temp(output)
            actual = {
                item.relative_to(output).as_posix(): overlays.digest(item.read_bytes())
                for item in output.rglob("*") if item.is_file()
            }
            self.assertEqual(actual, expected)

    def test_existing_or_non_temp_output_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="v4y-overlay-existing-") as temp:
            with self.assertRaisesRegex(overlays.FrontendOverlayError, "new directory"):
                overlays.assemble_temp(Path(temp))
        with self.assertRaisesRegex(overlays.FrontendOverlayError, "new directory"):
            overlays.assemble_temp(overlays.ROOT / "forbidden-output")

    def test_source_map_tampering_is_rejected_before_use(self):
        with tempfile.TemporaryDirectory(prefix="v4y-overlay-map-tamper-") as temp:
            changed = Path(temp) / "frontend-overlay-source-map.json"
            changed.write_bytes(overlays.MAP.read_bytes() + b" ")
            with patch.object(overlays, "MAP", changed):
                with self.assertRaisesRegex(overlays.FrontendOverlayError, "pinned hash changed"):
                    overlays.validate()

    def test_source_byte_drift_is_rejected(self):
        mapping = json.loads(overlays.MAP.read_text("utf-8"))
        row = mapping["files"][0]
        with tempfile.TemporaryDirectory(prefix="v4y-overlay-source-drift-") as temp:
            changed = Path(temp) / Path(row["target"]).name
            changed.write_bytes(b"changed public asset")
            with self.assertRaisesRegex(overlays.FrontendOverlayError, "byte/hash mismatch"):
                overlays.check_source_file(row, changed)

    def test_private_traversal_and_generated_entrypoints_are_denied(self):
        for target in (
            "../server/assets/x.js",
            "server/../../data/orders.json",
            "server/.env",
            "server/admin/index.html",
            "server/index.html",
            "server/assets/private.key",
            "C:/windows/system32.dll",
            "/etc/passwd",
        ):
            with self.subTest(target=target):
                with self.assertRaises(overlays.FrontendOverlayError):
                    overlays.safe_target(target)

    def test_sources_cannot_depend_on_external_workspace_archives(self):
        target = "server/assets/v4y-social-buttons-20261024.js"
        with self.assertRaisesRegex(overlays.FrontendOverlayError, "pinned capsule path"):
            overlays.safe_source(
                "Vibe4You/tests/fixtures/current-graph/v4y-social-buttons-20261024.js",
                target,
            )


if __name__ == "__main__":
    unittest.main()
