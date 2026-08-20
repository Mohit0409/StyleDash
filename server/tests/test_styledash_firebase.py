from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "styledash_firebase_config_test",
    ROOT / "scripts" / "styledash_firebase.py",
)
assert SPEC and SPEC.loader
FIREBASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FIREBASE)


class FirebaseRuntimeConfigurationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name).resolve()
        self.private = self.home / ".config" / "styledash"
        self.private.mkdir(parents=True)
        self.private.chmod(0o700)
        self.environment = {"STYLEDASH_FIREBASE_PROJECT_ID": "styledash-test"}

    def tearDown(self) -> None:
        self.temp.cleanup()

    def credential(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"project_id": "styledash-test"}), encoding="utf-8")
        path.chmod(0o600)
        return path.resolve()

    def validate(self, path: Path) -> tuple[str, Path]:
        environment = {**self.environment, "STYLEDASH_FIREBASE_CREDENTIALS": str(path)}
        with patch.dict(os.environ, environment, clear=False):
            return FIREBASE.validate_firebase_runtime_config(self.home)

    def test_accepts_owned_credentials_inside_private_configuration(self) -> None:
        credential = self.credential(self.private / "firebase-admin.json")
        self.assertEqual(self.validate(credential), ("styledash-test", credential))

    def test_rejects_credentials_under_public_or_admin_runtime(self) -> None:
        for directory in ("server", "admin"):
            credential = self.credential(self.home / directory / "firebase-admin.json")
            with self.subTest(directory=directory), self.assertRaises(FIREBASE.FirebaseUnavailable):
                self.validate(credential)

    def test_rejects_symlink_escape_and_project_mismatch(self) -> None:
        outside = self.credential(self.home / "private-elsewhere" / "firebase-admin.json")
        linked = self.private / "firebase-admin.json"
        try:
            linked.symlink_to(outside)
        except OSError:
            self.skipTest("symlinks are unavailable on this test host")
        with self.assertRaises(FIREBASE.FirebaseUnavailable):
            self.validate(linked)

        linked.unlink()
        linked.write_text(json.dumps({"project_id": "different-project"}), encoding="utf-8")
        linked.chmod(0o600)
        with self.assertRaises(FIREBASE.FirebaseUnavailable):
            self.validate(linked)


if __name__ == "__main__":
    unittest.main()
