"""Synthetic coverage-integrity unit tests; no production data or credentials."""
import unittest
from coverage_integrity import analyze_coverage

class CoverageIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.manifest=[{"id":"01.public","section":"Public"},{"id":"02.payment","section":"Payment"},{"id":"03.admin","section":"Admin"}]
        self.report=[
            {"id":"01.public","status":"PASS"},
            {"id":"02.payment","status":"BLOCKED"},
            {"id":"03.admin","status":"NOT TESTED"},
            {"id":"ops.health","status":"PASS"},
            {"id":"staging.mrp","status":"WARN"},
        ]

    def test_exact_ids_and_supplements_are_separated(self):
        result=analyze_coverage(self.manifest,self.report,expected=3)
        self.assertTrue(result["integrity_pass"],result)
        self.assertEqual(result["official_status"],{"BLOCKED":1,"NOT TESTED":1,"PASS":1})
        self.assertEqual(result["supplementary_status"],{"PASS":1,"WARN":1})
        self.assertEqual(result["official_count"],3)
        self.assertEqual(result["supplementary_count"],2)

    def test_missing_official_id_fails(self):
        result=analyze_coverage(self.manifest,self.report[:-3],expected=3)
        self.assertFalse(result["integrity_pass"])
        self.assertIn("03.admin",result["missing_official_ids"])

    def test_duplicate_report_id_fails(self):
        result=analyze_coverage(self.manifest,self.report+[{"id":"01.public","status":"PASS"}],expected=3)
        self.assertFalse(result["integrity_pass"])
        self.assertIn("01.public",result["duplicate_report_ids"])

    def test_duplicate_manifest_id_fails(self):
        manifest=self.manifest+[{"id":"02.payment","section":"Payment"}]
        result=analyze_coverage(manifest,self.report,expected=4)
        self.assertFalse(result["integrity_pass"])
        self.assertIn("02.payment",result["duplicate_manifest_ids"])

    def test_invalid_status_fails(self):
        changed=[dict(row) for row in self.report]
        changed[1]["status"]="UNKNOWN"
        result=analyze_coverage(self.manifest,changed,expected=3)
        self.assertFalse(result["integrity_pass"])
        self.assertEqual(result["invalid_status_row_count"],1)

    def test_manifest_count_drift_fails(self):
        result=analyze_coverage(self.manifest,self.report,expected=185)
        self.assertFalse(result["integrity_pass"])
        self.assertTrue(any("expected 185" in x for x in result["errors"]))

if __name__=="__main__":
    unittest.main()
