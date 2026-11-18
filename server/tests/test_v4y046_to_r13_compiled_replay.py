"""Pinned historical V4Y-046 -> V4Y-056 R13 patch-build regression."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import replay_v4y046_to_r13_offline as replay


class V4Y046R13ReplayTests(unittest.TestCase):
    def test_public_compiled_inputs_and_builder_are_sha_pinned(self):
        proof=replay.verify_inputs()
        self.assertEqual(len(proof["v4y046_base_files"]),54)
        self.assertEqual(len(proof["r13_expected_files"]),56)
        self.assertEqual(proof["r13_builder_sha256"],replay.PIN_BUILDER_SHA)
        self.assertEqual(proof["r13_backend_sha256"],replay.PIN_BACKEND_SHA)
        self.assertFalse(proof["editable_react_source_to_v4y046_reproduced"])

    def test_rebuild_r13_release_exactly_from_v4y046_archive(self):
        result=replay.replay()
        self.assertEqual(result["v4y046_compiled_inputs"],54)
        self.assertEqual(result["r13_verified_code_config_outputs"],56)
        self.assertEqual(result["r13_storefront_inputs_for_r3_replay"],54)
        self.assertTrue(result["r13_stored_candidate_sha256_reproduced"])
        self.assertFalse(result["editable_react_source_to_v4y046_reproduced"])

    def test_expected_r13_output_matches_pinned_search_chain_inputs(self):
        proof=replay.load()
        root=replay.R13_ROOT
        for name,sha in proof["r13_expected_files"].items():
            if name=="server/index.html" or name.startswith("server/assets/"):
                with self.subTest(target=name):
                    file=root/name.removeprefix("server/")
                    self.assertEqual(hashlib.sha256(file.read_bytes()).hexdigest(),sha)

    def test_r13_has_separate_service_config_and_backend_provenance(self):
        proof=replay.load()
        self.assertEqual(
            proof["r13_expected_files"]["server/serve.py"],replay.PIN_BACKEND_SHA)
        self.assertIn("systemd/zz-public-origin.conf",proof["r13_expected_files"])

    def test_proof_byte_tampering_is_denied(self):
        with tempfile.TemporaryDirectory(prefix="v4y046-proof-tamper-") as tmp:
            altered=Path(tmp)/"proof.json"
            altered.write_bytes(replay.PROOF.read_bytes()+b" ")
            with patch.object(replay,"PROOF",altered):
                with self.assertRaisesRegex(replay.V4Y046ReplayError,
                                            "replay proof changed"):
                    replay.load()

    def test_baseline_manifest_tampering_is_denied(self):
        with tempfile.TemporaryDirectory(prefix="v4y046-manifest-tamper-") as tmp:
            altered=Path(tmp)/"archive"
            (altered/"live-baseline").mkdir(parents=True)
            source=replay.ARCHIVE/"live-baseline/manifest.sha256"
            (altered/"live-baseline/manifest.sha256").write_bytes(source.read_bytes()+b" ")
            with patch.object(replay,"ARCHIVE",altered):
                with self.assertRaisesRegex(replay.V4Y046ReplayError,
                                            "manifest changed"):
                    replay.verify_inputs()

    def test_unsafe_paths_and_private_files_denied(self):
        for name in ("../orders.sqlite","C:/admin/private.ini",
                     "/etc/passwd","assets/../../customer.json"):
            with self.subTest(path=name):
                with self.assertRaises(replay.V4Y046ReplayError):
                    replay.path(name)


if __name__=="__main__":
    unittest.main()
