"""Regression tests for the offline 60-target Ubuntu candidate boundary."""
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

from scripts import build_pinned_ubuntu_release_candidate as ubuntu


class PinnedUbuntuReleaseCandidateTests(unittest.TestCase):
    def test_contract_pins_all_60_separate_admin_public_targets(self):
        entries, contract = ubuntu.validate_contract()
        targets = {target.as_posix(): sha for target, _, sha in entries}
        self.assertEqual(len(targets), 60)
        self.assertEqual(sum(name.startswith("admin/") for name in targets), 33)
        self.assertEqual(sum(name.startswith("server/") for name in targets), 27)
        self.assertNotEqual(targets["admin/serve.py"], targets["server/serve.py"])
        self.assertEqual(contract["payload"]["generated_exclusions"], ["server/index.html"])
        self.assertNotIn("server/index.html", targets)

    def test_observed_service_contract_preserves_loopback_admin_isolation(self):
        _, contract = ubuntu.validate_contract()
        services = contract["service_contract"]
        self.assertEqual(
            (services["public"]["bind"], services["public"]["port"], services["public"]["public_ingress"]),
            ("127.0.0.1", 8080, True),
        )
        self.assertEqual(
            (services["admin"]["bind"], services["admin"]["port"], services["admin"]["public_ingress"]),
            ("127.0.0.1", 8081, False),
        )
        self.assertEqual(services["tunnel"]["public_ingress_must_target"], "127.0.0.1:8080")
        self.assertTrue(services["tunnel"]["admin_ingress_forbidden"])

    def test_activation_and_old_termux_installer_remain_disabled(self):
        _, contract = ubuntu.validate_contract()
        activation = contract["activation"]
        self.assertFalse(activation["implemented"])
        self.assertFalse(activation["authorized"])
        self.assertFalse(activation["old_termux_installer_allowed"])
        self.assertFalse(activation["database_rollback_allowed"])
        with redirect_stderr(StringIO()):
            with self.assertRaises(SystemExit):
                ubuntu.main(["--apply"])

    def test_temp_candidate_contains_exact_payload_and_four_metadata_files(self):
        with tempfile.TemporaryDirectory(prefix="v4y-ubuntu-parent-") as temp:
            output = Path(temp) / "candidate"
            ubuntu.build_temp(output)
            self.assertEqual(
                ubuntu.verify_candidate(output),
                {"payload_files": 60, "metadata_files": 4, "admin_targets": 33, "server_targets": 27},
            )
            manifest = json.loads((output / ubuntu.MANIFEST_NAME).read_text("utf-8"))
            self.assertFalse(manifest["activation_implemented"])
            self.assertEqual(len(manifest["files"]), 60)

    def test_candidate_payload_contains_no_runtime_state_or_generated_homepage(self):
        entries, _ = ubuntu.validate_contract()
        targets = [target.as_posix() for target, _, _ in entries]
        self.assertNotIn("server/index.html", targets)
        for target in targets:
            ubuntu._assert_public_target(target)
            lowered = target.lower()
            self.assertNotIn(".db", lowered)
            self.assertNotIn("private/", lowered)
            self.assertNotIn("secret", lowered)

    def test_contract_tampering_fails_before_candidate_build(self):
        with tempfile.TemporaryDirectory(prefix="v4y-ubuntu-contract-tamper-") as temp:
            changed = Path(temp) / "ubuntu-release-contract.json"
            changed.write_bytes(ubuntu.CONTRACT.read_bytes() + b" ")
            with patch.object(ubuntu, "CONTRACT", changed):
                with self.assertRaisesRegex(ubuntu.UbuntuCandidateError, "pinned hash changed"):
                    ubuntu.validate_contract()

    def test_payload_byte_tampering_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="v4y-ubuntu-tamper-parent-") as temp:
            output = Path(temp) / "candidate"
            ubuntu.build_temp(output)
            target = output / "payload/server/serve.py"
            target.write_bytes(target.read_bytes() + b"\n")
            with self.assertRaisesRegex(ubuntu.UbuntuCandidateError, "byte/hash mismatch"):
                ubuntu.verify_candidate(output)

    def test_unexpected_candidate_file_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="v4y-ubuntu-extra-parent-") as temp:
            output = Path(temp) / "candidate"
            ubuntu.build_temp(output)
            (output / "payload/server/unexpected.py").write_text("pass\n", encoding="utf-8")
            with self.assertRaisesRegex(ubuntu.UbuntuCandidateError, "Unexpected file"):
                ubuntu.verify_candidate(output)

    def test_private_and_credential_targets_are_denied(self):
        for target in (
            "server/private/orders.json",
            "server/styledash.db",
            "admin/.env",
            "server/cloudflare-token.txt",
            "server/key.pem",
            "../server/serve.py",
            "C:/windows/system32.dll",
        ):
            with self.subTest(target=target):
                with self.assertRaises(ubuntu.UbuntuCandidateError):
                    ubuntu._assert_public_target(target)

    def test_output_must_be_new_and_beneath_os_temp(self):
        with tempfile.TemporaryDirectory(prefix="v4y-ubuntu-existing-") as temp:
            with self.assertRaisesRegex(ubuntu.UbuntuCandidateError, "new directory"):
                ubuntu.build_temp(Path(temp))
        with self.assertRaisesRegex(ubuntu.UbuntuCandidateError, "new directory"):
            ubuntu.build_temp(ubuntu.ROOT / "forbidden-ubuntu-candidate")


if __name__ == "__main__":
    unittest.main()
