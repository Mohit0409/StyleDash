"""Byte-for-byte selected production source target assembly tests.

This is not a deployment test or production release authorization.
"""
from __future__ import annotations
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import assemble_pinned_server_code as assembly


class PinnedTargetAssemblyTests(unittest.TestCase):
    def test_exact_target_coverage_and_generated_homepage_excluded(self):
        verified, mapping = assembly.validate()
        self.assertEqual(len(verified), 60)
        self.assertEqual(len({str(item[0]) for item in verified}), 60)
        self.assertNotIn("server/index.html", {item["target"] for item in mapping["verified_targets"]})
        self.assertEqual(mapping["generated_exclusions"], ["server/index.html"])
        self.assertEqual(
            sum(item["kind"] == "target-specific-source"
                for item in mapping["verified_targets"]), 16
        )

    def test_divergent_admin_and_public_targets_remain_distinct(self):
        verified, _ = assembly.validate()
        staged = {p.as_posix(): (src, digest)
                  for p, src, digest in verified}
        for filename in (
            "catalog_normalization.py",
            "store_categories.py",
            "styledash_security.py",
            "styledash_shops.py",
            "invoice_admin_gateway.py",
            "tax_classification_registry.py",
            "serve.py",
        ):
            with self.subTest(module=filename):
                admin, public = ("admin/" + filename, "server/" + filename)
                self.assertIn(admin, staged)
                self.assertIn(public, staged)
                self.assertNotEqual(staged[admin][1], staged[public][1])
                self.assertNotEqual(staged[admin][0], staged[public][0])

    def test_authentic_gst_phase1_source_is_pinned_to_both_targets(self):
        verified, _ = assembly.validate()
        records = {p.as_posix(): (src, sha) for p, src, sha in verified}
        for path in ("admin/gst_phase1_registry.py",
                     "server/gst_phase1_registry.py"):
            source, sha = records[path]
            self.assertEqual(source.name, "gst_phase1_registry.py")
            self.assertEqual(sha, assembly.GST_REGISTRY_SHA256)

    def test_temp_bundle_has_exactly_60_verified_code_files(self):
        with tempfile.TemporaryDirectory(prefix="v4y-sync-assembly-test-") as tmp:
            dest = Path(tmp) / "staged-code"
            assembly.assemble_temp(dest)
            self.assertTrue(dest.is_dir())
            self.assertEqual(len([x for x in dest.rglob("*") if x.is_file()]), 60)
            records, _ = assembly.validate()
            for target, original, sha in records:
                with self.subTest(target=str(target)):
                    result = dest / target
                    self.assertTrue(result.is_file())
                    self.assertEqual(hashlib.sha256(result.read_bytes()).hexdigest(), sha)
                    self.assertEqual(result.read_bytes(), original.read_bytes())
            self.assertFalse((dest / "server/index.html").exists())

    def test_all_mapped_python_target_files_compile(self):
        verified, _ = assembly.validate()
        checked = 0
        for target, source, _ in verified:
            if target.suffix == ".py":
                with self.subTest(target=target.as_posix()):
                    compile(source.read_bytes(), target.as_posix(), "exec")
                    checked += 1
        self.assertGreaterEqual(checked, 30)

    def test_assembly_never_includes_private_runtime_files(self):
        entries, _ = assembly.validate()
        for target, _source, _hash in entries:
            name = target.as_posix().lower()
            self.assertNotIn("payment-data", name)
            self.assertNotIn("customer-data", name)
            self.assertNotIn("secret", name)
            self.assertNotIn("credentials", name)
            self.assertNotIn("orders.json", name)
            self.assertNotIn(".db", name)
            self.assertNotIn(".sqlite", name)

    def test_existing_or_outside_temp_output_is_refused(self):
        with tempfile.TemporaryDirectory(prefix="v4y-sync-refuse-") as tmp:
            with self.assertRaises(assembly.PinnedSourceError):
                assembly.assemble_temp(Path(tmp))
            with self.assertRaises(assembly.PinnedSourceError):
                assembly.assemble_temp(assembly.ROOT / "unsafe-staging")
        self.assertFalse((assembly.ROOT / "unsafe-staging").exists())

    def test_path_traversal_and_sensitive_destinations_refused(self):
        for item in ("../outside.py", "admin/../../private.json",
                     "admin/secret.key", "payment-data/orders.json",
                     "server/private.db", "C:/outside.py"):
            with self.subTest(path=item):
                with self.assertRaises(assembly.PinnedSourceError):
                    assembly.safe_target(item)
        for item in ("../private", "secrets/token.json",
                     "deployment-targets/vibe4you-20261116-r2/../../nope.py",
                     "C:/test.py"):
            with self.subTest(source=item):
                with self.assertRaises(assembly.PinnedSourceError):
                    assembly.safe_repo_source(item)

    def test_source_drift_is_denied_before_assembly_writes(self):
        with patch.object(assembly, "safe_repo_source",
                          return_value=Path(__file__)):
            with self.assertRaisesRegex(assembly.PinnedSourceError,
                                        "Source byte SHA mismatch"):
                assembly.validate()

    def test_map_drift_is_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            local = Path(tmp) / "tampered-map.json"
            content = assembly.MAP.read_text(encoding="utf-8")
            local.write_text(content + " ", encoding="utf-8")
            with patch.object(assembly, "MAP", local):
                with self.assertRaisesRegex(assembly.PinnedSourceError,
                                            "Source map pinned hash changed"):
                    assembly.validate()


if __name__ == "__main__":
    unittest.main()
