"""Editable Search V2 R2 source provenance tests, no network."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import verify_search_v2_source_build as search


class SearchV2SourceRecoveryTests(unittest.TestCase):
    def test_all_eleven_editable_source_hashes_are_pinned(self):
        self.assertEqual(search.verify_source(),
                         {"source_files":11,"archived_build_files":61,
                          "extra_public_files":5})

    def test_source_proof_must_not_claim_final_live_build_parity(self):
        proof=search.read_proof()
        text=proof["classification"].lower()
        self.assertIn("not the final deployment bundle",text)
        self.assertEqual(len(proof["archived_final_release_payload_matches_live"]),3)
        self.assertEqual(len(proof["source_build_reproduced_files"]),61)

    def test_invalid_source_path_is_denied(self):
        for item in ("../private.py","C:/Windows/System32/driver.ts",
                     "/etc/passwd","src/../../order-data.ts"):
            with self.subTest(item=item):
                with self.assertRaises(search.SearchSourceError):
                    search.safe_path(item)

    def test_proof_tampering_is_denied(self):
        with tempfile.TemporaryDirectory(prefix="v4y-source-pin-test-") as tmp:
            file=Path(tmp)/"altered.json"
            file.write_bytes(search.PROOF.read_bytes()+b" ")
            with patch.object(search,"PROOF",file):
                with self.assertRaisesRegex(search.SearchSourceError,"proof changed"):
                    search.verify_source()


if __name__=="__main__":
    unittest.main()
