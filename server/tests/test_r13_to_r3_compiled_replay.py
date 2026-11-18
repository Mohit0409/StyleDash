"""Historical public V4Y-056 R13 to V4Y-055 R3 release replay tests."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import replay_r13_to_r3_offline as r13


class R13ToR3ReplayTests(unittest.TestCase):
    def test_original_builder_and_release_inputs_sha_pinned(self):
        proof, sources=r13.verified_inputs()
        self.assertEqual(len(sources),54)
        self.assertEqual(len(proof["r3_expected_files"]),56)
        self.assertEqual(proof["builder_sha256"],r13.PIN_BUILDER)
        self.assertFalse(proof["editable_react_source_to_r13_reproduced"])

    def test_output_exactly_matches_all_r3_release_assets(self):
        result=r13.replay()
        self.assertEqual(result["r13_compiled_input_files"],54)
        self.assertEqual(result["r3_verified_release_files"],56)
        self.assertEqual(result["r3_compiled_public_assets_matching_later_search_baseline"],54)
        self.assertFalse(result["r13_compiled_source_recreated_from_editable_react"])

    def test_r13_to_r3_home_and_payment_modules_are_really_changed(self):
        proof,sources=r13.verified_inputs()
        before=r13.R3/"live-baseline/assets"
        after=r13.CHAIN/"base-v4y055-r3/assets"
        for component in ("paymentApi-","Home-"):
            original=next(p for p in before.iterdir() if p.name.startswith(component))
            patched=after/original.name.replace(
                "-v4y056-storefront-hardening-r4.js","-v4y055-r3.js")
            self.assertTrue(patched.is_file())
            self.assertNotEqual(hashlib.sha256(original.read_bytes()).hexdigest(),
                                hashlib.sha256(patched.read_bytes()).hexdigest())

    def test_modified_replay_proof_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="v4y-r13-r3-tamper-") as temp:
            fake=Path(temp)/"tamper.json"
            fake.write_bytes(r13.PROOF.read_bytes()+b" ")
            with patch.object(r13,"PROOF",fake):
                with self.assertRaisesRegex(r13.R13ReplayError,"proof SHA mismatch"):
                    r13.verified_inputs()

    def test_bad_r13_sha_manifest_is_denied(self):
        with tempfile.TemporaryDirectory(prefix="v4y-r13-r3-input-tamper-") as temp:
            tempdir=Path(temp)
            src=r13.R3/"live-baseline"
            other=tempdir/"r13-to-r3"
            (other/"live-baseline").mkdir(parents=True)
            (other/"live-baseline/r13-candidate.sha256").write_bytes(
                (src/"r13-candidate.sha256").read_bytes()+b" ")
            with patch.object(r13,"R3",other):
                with self.assertRaisesRegex(r13.R13ReplayError,"R13 full release SHA manifest changed"):
                    r13.verified_inputs()

    def test_unsafe_paths_are_rejected(self):
        for path in ("../secret.json","C:/Windows/system.ini","/etc/passwd",
                     "assets/../../orders.json"):
            with self.subTest(path=path):
                with self.assertRaises(r13.R13ReplayError):
                    r13.safe_rel(path)

    def test_original_build_script_is_not_deployment_tool(self):
        source=(r13.R3/"tools/build_candidate.py").read_text(encoding="utf-8")
        self.assertIn("NEW_SUFFIX = \"-v4y055-r3.js\"",source)
        self.assertIn('PAYMENT_NEW = (',source)
        self.assertIn('NEW_ICONS = (',source)
        self.assertNotIn("systemctl restart",source)


if __name__=="__main__":
    unittest.main()
