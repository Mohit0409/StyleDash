"""Synthetic, non-production fixtures for role-source preflight."""
from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from ci_role_source_preflight import inspect


class RoleSourcePreflightTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.public = self.root / "public"
        self.admin = self.root / "admin"
        self.public.mkdir()
        self.admin.mkdir()
        self.manifest = self.root / "artifact-files.sha256"
        self.rows: list[str] = []
        self.add("server", "serve.py", "import styledash_shops\nVALUE = 1\n")
        self.add("server", "styledash_shops.py", "VALUE = 'public'\n")
        self.add("admin", "serve.py", "from styledash_shops import VALUE\n")
        self.add("admin", "styledash_shops.py", "VALUE = 'admin'\n")

    def add(self, role: str, name: str, source: str) -> None:
        dst = (self.public if role == "server" else self.admin) / name
        payload = source.encode("utf-8")
        dst.write_bytes(payload)
        digest = hashlib.sha256(payload).hexdigest()
        self.rows.append(f"{digest}  {role}/{name}")

    def evaluate(self) -> dict:
        self.manifest.write_text("\n".join(self.rows) + "\n", encoding="utf-8")
        return inspect(self.manifest, self.public, self.admin)

    def test_two_roles_preserve_distinct_source_hashes(self) -> None:
        result = self.evaluate()
        self.assertTrue(result["passed"])
        self.assertEqual(result["roles"]["server"]["verified"], 2)
        self.assertEqual(result["roles"]["admin"]["verified"], 2)
        self.assertEqual(result["divergent_shared_modules"],
                         ["serve.py", "styledash_shops.py"])
        self.assertEqual(result["warnings"], [])

    def test_checksum_mismatch_is_blocking(self) -> None:
        self.public.joinpath("serve.py").write_text("VALUE = 'unexpected'\n")
        result = self.evaluate()
        self.assertFalse(result["passed"])
        self.assertIn("checksum mismatch: server/serve.py", result["errors"])

    def test_missing_source_is_blocking(self) -> None:
        self.admin.joinpath("styledash_shops.py").unlink()
        result = self.evaluate()
        self.assertFalse(result["passed"])
        self.assertIn("missing or symlinked source: admin/styledash_shops.py",
                      result["errors"])

    def test_import_gap_warns_without_pretending_runtime_is_broken(self) -> None:
        # Conditional imports are flagged but may be intentional.
        self.add("admin", "styledash_security.py",
                 "try:\n    import styledash_firebase\nexcept ImportError:\n    pass\n")
        result = self.evaluate()
        self.assertTrue(result["passed"])
        self.assertIn(
            "unresolved role-local import: admin/styledash_security.py -> styledash_firebase",
            result["warnings"],
        )

    def test_syntax_error_is_blocking(self) -> None:
        self.add("admin", "broken.py", "def no( :\n")
        result = self.evaluate()
        self.assertFalse(result["passed"])
        self.assertIn("Python syntax/decode failure: admin/broken.py",
                      result["errors"])

    def test_invalid_manifest_entry_is_rejected(self) -> None:
        self.rows.append("0" * 64 + "  server/../outside.py")
        result = self.evaluate()
        self.assertFalse(result["passed"])
        self.assertIn("invalid role Python path in manifest", result["errors"])

    def test_duplicate_source_record_is_rejected(self) -> None:
        self.rows.append(self.rows[0])
        result = self.evaluate()
        self.assertFalse(result["passed"])
        self.assertIn("duplicate source manifest entry: server/serve.py",
                      result["errors"])

    def test_no_admin_entries_is_blocking(self) -> None:
        self.rows = [r for r in self.rows if "  server/" in r]
        result = self.evaluate()
        self.assertFalse(result["passed"])
        self.assertIn("no admin Python entries in manifest", result["errors"])


if __name__ == "__main__":
    unittest.main()
