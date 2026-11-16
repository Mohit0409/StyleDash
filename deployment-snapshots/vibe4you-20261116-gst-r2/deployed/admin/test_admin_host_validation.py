import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "admin"))
SPEC = importlib.util.spec_from_file_location("candidate_admin_serve", ROOT / "admin" / "serve.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class AdminHostValidationTests(unittest.TestCase):
    def setUp(self):
        self.allowed = MODULE._parse_admin_allowed_hosts("127.0.0.1:28081,localhost:28081")

    def test_mobile_compatibility_default(self):
        self.assertEqual(
            MODULE._parse_admin_allowed_hosts(""),
            frozenset({"127.0.0.1:8081", "localhost:8081"}),
        )

    def test_candidate_exact_authorities_are_allowed(self):
        self.assertTrue(MODULE._host_values_allowed(["127.0.0.1:28081"], self.allowed))
        self.assertTrue(MODULE._host_values_allowed(["LOCALHOST:28081"], self.allowed))

    def test_legacy_and_unapproved_authorities_are_rejected(self):
        for value in [
            "127.0.0.1:8081", "localhost:8081", "evil.example",
            "evil.example:28081", "127.0.0.1:9999", "localhost.evil:28081",
            "127.0.0.1:28081.evil.example", "127.0.0.1@evil.example",
        ]:
            self.assertFalse(MODULE._host_values_allowed([value], self.allowed), value)

    def test_multiple_or_malformed_host_values_are_rejected(self):
        self.assertFalse(MODULE._host_values_allowed([], self.allowed))
        self.assertFalse(MODULE._host_values_allowed(["127.0.0.1:28081", "evil.example"], self.allowed))
        self.assertFalse(MODULE._host_values_allowed([" 127.0.0.1:28081"], self.allowed))
        self.assertFalse(MODULE._host_values_allowed(["127.0.0.1:28081 "], self.allowed))

    def test_invalid_configuration_is_rejected(self):
        for value in ["*", "localhost", "localhost:0", "localhost:70000", "localhost.evil:28081", "127.0.0.1:28081,"]:
            with self.assertRaises(RuntimeError):
                MODULE._parse_admin_allowed_hosts(value)


if __name__ == "__main__":
    unittest.main()
