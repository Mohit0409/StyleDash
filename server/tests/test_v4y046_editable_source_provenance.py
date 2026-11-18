"""Regression coverage for the pinned V4Y-046 source classification."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import verify_v4y046_editable_source_provenance as provenance


class V4Y046EditableSourceProvenanceTests(unittest.TestCase):
    def test_pinned_baseline_and_classification(self):
        result = provenance.verify()
        self.assertEqual(result["v4y046_javascript_chunks"], 53)
        self.assertEqual(result["source_commit"], provenance.PIN_SOURCE_COMMIT)
        self.assertFalse(result["exact_editable_source_to_v4y046_reproduced"])

    def test_categories_post_minification_markers_are_pinned(self):
        _, modules = provenance.verify_baseline()
        raw = modules["Categories"].read_bytes()
        self.assertEqual(len(raw), 5080)
        self.assertEqual(provenance.sha(raw), provenance.PIN_CATEGORIES_SHA)
        for marker in (b"V4Y_PH", b"V4Y_Pick", b"V4Y_Thumb"):
            self.assertIn(marker, raw)

    def test_proof_byte_tampering_is_denied(self):
        with tempfile.TemporaryDirectory(prefix="v4y046-source-proof-") as tmp:
            changed = Path(tmp) / "proof.json"
            changed.write_bytes(provenance.PROOF.read_bytes() + b" ")
            with patch.object(provenance, "PROOF", changed):
                with self.assertRaisesRegex(provenance.ProvenanceError, "proof changed"):
                    provenance.load_proof()

    def test_filename_and_newline_normalization_is_narrow(self):
        names = {"Home-ABCDEFGH.js": "Home"}
        self.assertEqual(
            provenance.normalized(b'import"./Home-ABCDEFGH.js";\r\n', names),
            b'import"./@{Home}.js";\n',
        )
        self.assertNotEqual(
            provenance.normalized(b"const value=1;", names),
            provenance.normalized(b"const value=2;", names),
        )

    def test_unsafe_paths_are_denied(self):
        for name in ("../orders.sqlite", "C:/admin/private.ini", "/etc/passwd", "assets/../../customer.json"):
            with self.subTest(path=name):
                with self.assertRaises(provenance.ProvenanceError):
                    provenance.path(name)


if __name__ == "__main__":
    unittest.main()
