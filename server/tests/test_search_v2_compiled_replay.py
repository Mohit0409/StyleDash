"""Verify deterministic Search V2 R2 build transformations, offline only."""
from pathlib import Path
import hashlib
import tempfile
import unittest
from unittest.mock import patch

from scripts import replay_compiled_search_v2_r2 as replay


class SearchV2R2CompiledReplayTests(unittest.TestCase):
    def test_all_54_base_modules_are_sha_pinned(self):
        m=replay.manifest()
        replay.verify_inputs(m)
        self.assertEqual(len(m["base_files"]),54)
        self.assertEqual(sum(x["path"].startswith("assets/") for x in m["base_files"]),53)
        self.assertIn("index.html",{x["path"] for x in m["base_files"]})
        self.assertEqual(m["production_integrity_manifest_sha256"],replay.PIN_LIVE_MANIFEST)

    def test_exact_search_v2_and_r2_replay_matches_live_snapshot(self):
        result=replay.replay()
        self.assertEqual(result["v1_release_rebuilt"],54)
        self.assertEqual(result["r2_release_rebuilt"],54)
        self.assertTrue(result["v1_bridge_from_ts"])
        self.assertTrue(result["r2_bridge_from_ts"])
        self.assertTrue(result["r2_matches_pinned_live_frontend"])
        self.assertFalse(result["editable_react_source_to_base_r3_reproduced"])

    def test_replay_does_not_claim_editable_source_full_parity(self):
        self.assertIn("historical compiled",replay.__doc__.lower())
        self.assertIn("not a reproducible frontend build",replay.__doc__.lower())

    def test_manifest_byte_tampering_fails_closed(self):
        with tempfile.TemporaryDirectory(prefix="v4y-r2-manifest-tamper-") as temp:
            wrong=Path(temp)/"replay-inputs.json"
            wrong.write_bytes(replay.INPUTS.read_bytes()+b" ")
            with patch.object(replay,"INPUTS",wrong):
                with self.assertRaisesRegex(replay.ReplayError,"manifest changed"):
                    replay.manifest()

    def test_invalid_paths_and_patch_anchors_fail_closed(self):
        for name in ("../private.py","C:/secret","assets/../../orders.json","/etc/passwd"):
            with self.subTest(path=name):
                with self.assertRaises(replay.ReplayError):
                    replay.check_rel(name)
        with self.assertRaisesRegex(replay.ReplayError,"one patch anchor"):
            replay.replace_one("no known anchor","a known anchor","patched","missing")

    def test_read_text_newline_behavior_is_explicit(self):
        with tempfile.TemporaryDirectory(prefix="v4y-r2-eol-") as tmp:
            p=Path(tmp)/"sample.js"
            p.write_bytes(b"a\r\nb\rc\nd")
            self.assertEqual(replay.archive_read_text(p),"a\nb\nc\nd")

    def test_production_runtime_reference_does_not_change(self):
        m=replay.manifest()
        expected={x["path"]:x["sha256"] for x in m["expected_step2"]}
        self.assertEqual(len(expected),54)
        for name,sha in expected.items():
            with self.subTest(asset=name):
                live=replay.PRODUCTION/name
                self.assertEqual(hashlib.sha256(live.read_bytes()).hexdigest(),sha)


if __name__=="__main__":
    unittest.main()
