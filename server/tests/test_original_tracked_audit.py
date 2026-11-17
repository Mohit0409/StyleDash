import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AUDIT = (
    ROOT
    / "deployment-snapshots"
    / "vibe4you-20261116-gst-r2"
    / "original-tracked-audit.json"
)
RECONCILIATION = (
    ROOT
    / "deployment-snapshots"
    / "vibe4you-20261116-gst-r2"
    / "original-local-search-reconciliation.json"
)
FILTER_RECONCILIATION = (
    ROOT
    / "deployment-snapshots"
    / "vibe4you-20261116-gst-r2"
    / "original-filter-dismiss-reconciliation.json"
)


class OriginalTrackedAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.audit = json.loads(AUDIT.read_text(encoding="utf-8"))
        cls.reconciliation = json.loads(RECONCILIATION.read_text(encoding="utf-8"))
        cls.filter_reconciliation = json.loads(
            FILTER_RECONCILIATION.read_text(encoding="utf-8")
        )

    def test_inventory_is_complete_and_non_overlapping(self) -> None:
        paths = [
            path
            for bundle in self.audit["bundles"]
            for path in bundle["paths"]
        ]
        self.assertEqual(68, len(paths))
        self.assertEqual(68, len(set(paths)))
        self.assertEqual(
            self.audit["observed_counts"]["tracked_status_paths"], len(paths)
        )

    def test_status_arithmetic_is_explicit(self) -> None:
        counts = self.audit["observed_counts"]
        self.assertEqual(
            counts["tracked_status_paths"],
            counts["content_diff_paths"] + counts["status_only_paths"],
        )
        self.assertEqual(3, len(self.audit["status_only_paths"]))
        self.assertEqual(0, counts["staged_paths"])

    def test_synchronized_paths_are_in_inventory(self) -> None:
        inventory = {
            path for bundle in self.audit["bundles"] for path in bundle["paths"]
        }
        self.assertEqual(4, len(self.audit["same_as_synchronized_branch"]))
        self.assertTrue(
            set(self.audit["same_as_synchronized_branch"]).issubset(inventory)
        )
        self.assertTrue(
            set(self.audit["status_only_paths"]).issubset(
                set(self.audit["same_as_synchronized_branch"])
            )
        )

    def test_production_comparison_does_not_claim_false_parity(self) -> None:
        comparison = self.audit["production_hash_comparison"]
        self.assertEqual([], comparison["exact_matches"])
        self.assertEqual(9, len(comparison["checked"]))
        self.assertEqual(
            9, len({entry["path"] for entry in comparison["checked"]})
        )
        for entry in comparison["checked"]:
            self.assertRegex(entry["sha256"], r"^[0-9a-f]{64}$")

    def test_sensitive_and_policy_paths_have_safe_disposition(self) -> None:
        bundle = next(
            item
            for item in self.audit["bundles"]
            if item["id"] == "protected-policy-and-config"
        )
        self.assertEqual("manual-review-do-not-copy-values", bundle["disposition"])
        self.assertIn("AGENTS.md", bundle["paths"])
        self.assertIn(".env.e2e", bundle["paths"])
        self.assertIn("server/payment-data/settings.json", bundle["paths"])

    def test_payment_bundle_is_blocked(self) -> None:
        bundle = next(
            item
            for item in self.audit["bundles"]
            if item["id"] == "payment-cod-and-tax-invoice"
        )
        self.assertTrue(bundle["disposition"].startswith("blocked-"))
        self.assertIn("src/pages/Checkout.tsx", bundle["paths"])
        self.assertIn("src/tests/paymentApi.test.ts", bundle["paths"])

    def test_untracked_surface_is_not_declared_complete(self) -> None:
        surface = self.audit["untracked_surface"]
        self.assertGreaterEqual(surface["minimum_paths_observed"], 4239)
        self.assertFalse(surface["scan_complete"])
        self.assertIn("never mass-add", surface["decision"])

    def test_audit_is_not_a_release_approval(self) -> None:
        self.assertEqual("MANUAL ACTION REQUIRED", self.audit["result"])

    def test_local_search_reconciliation_covers_the_whole_audit_bundle(self) -> None:
        bundle = next(
            item
            for item in self.audit["bundles"]
            if item["id"] == "local-search-aliases"
        )
        self.assertEqual(
            set(bundle["paths"]), set(self.reconciliation["audited_paths"])
        )
        self.assertEqual("local-search-aliases", self.reconciliation["source_bundle"])

    def test_local_search_dependency_is_byte_identical(self) -> None:
        dependency = self.reconciliation["dependency"]
        self.assertTrue(dependency["byte_identical"])
        self.assertEqual(dependency["original_sha256"], dependency["synchronized_sha256"])
        self.assertRegex(dependency["synchronized_sha256"], r"^[0-9a-f]{64}$")

    def test_local_search_reconciliation_ports_tests_not_dirty_source(self) -> None:
        self.assertEqual([], self.reconciliation["source_files_ported"])
        self.assertEqual(3, len(self.reconciliation["test_files_updated"]))
        self.assertEqual(
            "reconciled-no-source-port-required",
            self.reconciliation["supersedes_disposition"]["to"],
        )
        self.assertEqual("PASS", self.reconciliation["result"])

    def test_filter_reconciliation_covers_the_whole_audit_bundle(self) -> None:
        bundle = next(
            item
            for item in self.audit["bundles"]
            if item["id"] == "filter-dismissal-ui"
        )
        self.assertEqual(
            set(bundle["paths"]),
            set(self.filter_reconciliation["audited_paths"]),
        )
        self.assertEqual(
            "filter-dismissal-ui", self.filter_reconciliation["source_bundle"]
        )

    def test_filter_reconciliation_is_a_narrow_source_port(self) -> None:
        self.assertEqual(
            ["src/components/FilterSidebar.tsx"],
            self.filter_reconciliation["source_files_ported"],
        )
        self.assertEqual(
            ["e2e/specs/filter-dismiss.spec.ts"],
            self.filter_reconciliation["test_files_updated"],
        )
        self.assertEqual(
            "reconciled-selective-source-port",
            self.filter_reconciliation["supersedes_disposition"]["to"],
        )
        self.assertEqual("PASS", self.filter_reconciliation["result"])


if __name__ == "__main__":
    unittest.main()
