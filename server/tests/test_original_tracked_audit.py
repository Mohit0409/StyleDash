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
MAINTENANCE_RECONCILIATION = (
    ROOT
    / "deployment-snapshots"
    / "vibe4you-20261116-gst-r2"
    / "original-repository-maintenance-reconciliation.json"
)
TERMUX_RECONCILIATION = (
    ROOT
    / "deployment-snapshots"
    / "vibe4you-20261116-gst-r2"
    / "original-termux-operations-reconciliation.json"
)
UBUNTU_SOURCE_MAP = (
    ROOT
    / "deployment-targets"
    / "vibe4you-20261116-r2"
    / "source-map.json"
)
SYNCHRONIZED_RECONCILIATION = (
    ROOT
    / "deployment-snapshots"
    / "vibe4you-20261116-gst-r2"
    / "original-already-synchronized-reconciliation.json"
)
PROTECTED_CONFIG_RECONCILIATION = (
    ROOT
    / "deployment-snapshots"
    / "vibe4you-20261116-gst-r2"
    / "original-protected-config-reconciliation.json"
)
ANALYTICS_RECONCILIATION = (
    ROOT
    / "deployment-snapshots"
    / "vibe4you-20261116-gst-r2"
    / "original-analytics-consent-reconciliation.json"
)
MERCHANT_POLICY_RECONCILIATION = (
    ROOT
    / "deployment-snapshots"
    / "vibe4you-20261116-gst-r2"
    / "original-merchant-policy-seo-reconciliation.json"
)
CATALOG_SELLER_RECONCILIATION = (
    ROOT
    / "deployment-snapshots"
    / "vibe4you-20261116-gst-r2"
    / "original-catalog-seller-reconciliation.json"
)


class OriginalTrackedAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.audit = json.loads(AUDIT.read_text(encoding="utf-8"))
        cls.reconciliation = json.loads(RECONCILIATION.read_text(encoding="utf-8"))
        cls.filter_reconciliation = json.loads(
            FILTER_RECONCILIATION.read_text(encoding="utf-8")
        )
        cls.maintenance_reconciliation = json.loads(
            MAINTENANCE_RECONCILIATION.read_text(encoding="utf-8")
        )
        cls.termux_reconciliation = json.loads(
            TERMUX_RECONCILIATION.read_text(encoding="utf-8")
        )
        cls.ubuntu_source_map = json.loads(
            UBUNTU_SOURCE_MAP.read_text(encoding="utf-8")
        )
        cls.synchronized_reconciliation = json.loads(
            SYNCHRONIZED_RECONCILIATION.read_text(encoding="utf-8")
        )
        cls.protected_config_reconciliation = json.loads(
            PROTECTED_CONFIG_RECONCILIATION.read_text(encoding="utf-8")
        )
        cls.analytics_reconciliation = json.loads(
            ANALYTICS_RECONCILIATION.read_text(encoding="utf-8")
        )
        cls.merchant_policy_reconciliation = json.loads(
            MERCHANT_POLICY_RECONCILIATION.read_text(encoding="utf-8")
        )
        cls.catalog_seller_reconciliation = json.loads(
            CATALOG_SELLER_RECONCILIATION.read_text(encoding="utf-8")
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

    def test_maintenance_reconciliation_covers_the_whole_audit_bundle(self) -> None:
        bundle = next(
            item
            for item in self.audit["bundles"]
            if item["id"] == "repository-maintenance"
        )
        self.assertEqual(
            set(bundle["paths"]),
            set(self.maintenance_reconciliation["audited_paths"]),
        )

    def test_maintenance_reconciliation_keeps_config_not_stale_status(self) -> None:
        self.assertEqual(
            [".eslintrc.cjs"],
            self.maintenance_reconciliation["source_files_ported"],
        )
        self.assertEqual(
            ["docs/DEV_COORDINATION.md"],
            self.maintenance_reconciliation["source_files_rejected"],
        )
        self.assertEqual(
            "reconciled-selective-config-port",
            self.maintenance_reconciliation["supersedes_disposition"]["to"],
        )
        self.assertEqual("PASS", self.maintenance_reconciliation["result"])

    def test_termux_reconciliation_covers_the_whole_audit_bundle(self) -> None:
        bundle = next(
            item
            for item in self.audit["bundles"]
            if item["id"] == "obsolete-termux-operations"
        )
        self.assertEqual(
            set(bundle["paths"]),
            set(self.termux_reconciliation["audited_paths"]),
        )
        self.assertEqual(
            "obsolete-termux-operations",
            self.termux_reconciliation["source_bundle"],
        )

    def test_termux_reconciliation_ports_no_obsolete_operations(self) -> None:
        self.assertEqual([], self.termux_reconciliation["source_files_ported"])
        self.assertEqual(
            set(self.termux_reconciliation["audited_paths"]),
            set(self.termux_reconciliation["source_files_rejected"]),
        )
        self.assertEqual(
            "reconciled-no-termux-port",
            self.termux_reconciliation["supersedes_disposition"]["to"],
        )
        contract = self.termux_reconciliation["ubuntu_release_contract"]
        self.assertFalse(contract["activation_implemented"])
        self.assertFalse(contract["activation_authorized"])
        self.assertFalse(contract["old_termux_installer_allowed"])
        self.assertEqual("PASS", self.termux_reconciliation["result"])

    def test_termux_invoice_modules_are_already_pinned_for_ubuntu(self) -> None:
        actual_targets = {
            entry["target"]
            for entry in self.ubuntu_source_map["verified_targets"]
        }
        modules = self.termux_reconciliation[
            "ubuntu_candidate_modules_already_present"
        ]
        self.assertEqual(7, len(modules))
        self.assertEqual(13, sum(len(item["targets"]) for item in modules))
        for item in modules:
            with self.subTest(module=item["module"]):
                self.assertTrue(set(item["targets"]).issubset(actual_targets))

    def test_termux_backup_principles_are_preserved_as_future_requirements(self) -> None:
        requirement_ids = {
            item["id"]
            for item in self.termux_reconciliation["future_ubuntu_requirements"]
        }
        self.assertEqual(
            {
                "backup-mutual-exclusion",
                "complete-runtime-state-coverage",
                "verified-off-device-copies",
                "validated-restore-procedure",
            },
            requirement_ids,
        )
        self.assertIn(
            "never source-controlled release payloads",
            self.termux_reconciliation["runtime_state_decision"],
        )

    def test_synchronized_reconciliation_covers_the_whole_audit_bundle(self) -> None:
        bundle = next(
            item
            for item in self.audit["bundles"]
            if item["id"] == "already-synchronized"
        )
        self.assertEqual(
            set(bundle["paths"]),
            set(self.synchronized_reconciliation["audited_paths"]),
        )
        self.assertEqual(
            set(self.audit["same_as_synchronized_branch"]),
            set(self.synchronized_reconciliation["audited_paths"]),
        )

    def test_synchronized_reconciliation_requires_no_source_port(self) -> None:
        reconciliation = self.synchronized_reconciliation
        self.assertEqual([], reconciliation["source_files_ported"])
        self.assertEqual([], reconciliation["source_files_rejected"])
        self.assertEqual(4, len(reconciliation["comparisons"]))
        self.assertTrue(
            all(item["normalized_equal"] for item in reconciliation["comparisons"])
        )
        self.assertEqual(
            2,
            sum(
                item["difference"] == "line-ending-only"
                for item in reconciliation["comparisons"]
            ),
        )
        self.assertEqual(
            "reconciled-no-port-required",
            reconciliation["supersedes_disposition"]["to"],
        )
        self.assertEqual("PASS", reconciliation["result"])

    def test_protected_config_reconciliation_covers_the_whole_audit_bundle(self) -> None:
        bundle = next(
            item
            for item in self.audit["bundles"]
            if item["id"] == "protected-policy-and-config"
        )
        reconciliation = self.protected_config_reconciliation
        self.assertEqual(set(bundle["paths"]), set(reconciliation["audited_paths"]))
        self.assertEqual("protected-policy-and-config", reconciliation["source_bundle"])

    def test_protected_config_reconciliation_records_no_values_or_ports(self) -> None:
        reconciliation = self.protected_config_reconciliation
        self.assertFalse(reconciliation["protected_values_recorded"])
        self.assertEqual([], reconciliation["source_files_ported"])
        self.assertEqual(
            {".env.e2e", ".env.example"},
            set(reconciliation["already_satisfied_without_port"]),
        )
        self.assertEqual(
            {"AGENTS.md", "server/payment-data/settings.json"},
            set(reconciliation["source_files_rejected"]),
        )
        settings = next(
            item
            for item in reconciliation["file_decisions"]
            if item["path"] == "server/payment-data/settings.json"
        )
        self.assertEqual(["gst.principalPlace"], settings["observed_changed_paths"])
        self.assertEqual(
            "reconciled-no-protected-value-port",
            reconciliation["supersedes_disposition"]["to"],
        )
        self.assertEqual("PASS", reconciliation["result"])

    def test_analytics_reconciliation_covers_the_whole_audit_bundle(self) -> None:
        bundle = next(
            item
            for item in self.audit["bundles"]
            if item["id"] == "analytics-consent-and-attribution"
        )
        reconciliation = self.analytics_reconciliation
        self.assertEqual(set(bundle["paths"]), set(reconciliation["audited_paths"]))
        self.assertEqual(7, len(reconciliation["file_decisions"]))

    def test_analytics_reconciliation_preserves_privacy_boundary(self) -> None:
        reconciliation = self.analytics_reconciliation
        self.assertEqual([], reconciliation["source_files_ported"])
        self.assertEqual(
            {
                "src/services/ecommerceAnalytics.ts",
                "src/pages/NeemuchShopping.tsx",
                "src/data/neemuchShopping.ts",
            },
            set(reconciliation["untracked_dependencies_not_admitted"]),
        )
        invariants = " ".join(reconciliation["privacy_invariants"])
        self.assertIn("explicit acceptance", invariants)
        self.assertIn("exclude query strings and fragments", invariants)
        self.assertIn("standard arguments object", invariants)
        self.assertEqual(
            "reconciled-current-consent-implementation-retained",
            reconciliation["supersedes_disposition"]["to"],
        )
        self.assertEqual("PASS", reconciliation["result"])

    def test_merchant_policy_reconciliation_covers_the_whole_audit_bundle(self) -> None:
        bundle = next(
            item
            for item in self.audit["bundles"]
            if item["id"] == "merchant-policy-and-seo-shell"
        )
        reconciliation = self.merchant_policy_reconciliation
        self.assertEqual(set(bundle["paths"]), set(reconciliation["audited_paths"]))
        self.assertEqual(5, len(reconciliation["file_decisions"]))

    def test_merchant_policy_reconciliation_is_narrow_and_payment_safe(self) -> None:
        reconciliation = self.merchant_policy_reconciliation
        self.assertEqual(["src/components/SEO.tsx"], reconciliation["source_files_ported"])
        self.assertEqual(["e2e/specs/public.spec.ts"], reconciliation["test_files_updated"])
        self.assertEqual(
            {"index.html", "src/pages/Returns.tsx", "src/pages/Terms.tsx"},
            set(reconciliation["source_files_rejected"]),
        )
        invariants = " ".join(reconciliation["structured_data_invariants"])
        self.assertIn("does not advertise unsupported shippingDetails", invariants)
        self.assertIn("https://vibe4you.in/returns", invariants)
        self.assertIn("does not claim a universal return window", invariants)
        self.assertEqual(
            "reconciled-selective-merchant-policy-port",
            reconciliation["supersedes_disposition"]["to"],
        )
        self.assertEqual("PASS", reconciliation["result"])

    def test_catalog_seller_reconciliation_covers_the_whole_audit_bundle(self) -> None:
        bundle = next(
            item
            for item in self.audit["bundles"]
            if item["id"] == "catalog-taxonomy-and-seller"
        )
        reconciliation = self.catalog_seller_reconciliation
        self.assertEqual(set(bundle["paths"]), set(reconciliation["audited_paths"]))
        self.assertEqual(8, len(reconciliation["file_decisions"]))

    def test_catalog_seller_reconciliation_preserves_backend_contract(self) -> None:
        reconciliation = self.catalog_seller_reconciliation
        self.assertEqual(["src/components/SellerProducts.tsx"], reconciliation["source_files_ported"])
        self.assertEqual(["e2e/specs/seller-products-ui.spec.ts"], reconciliation["test_files_updated"])
        self.assertEqual(
            ["src/data/catalogTaxonomy.ts"],
            reconciliation["untracked_dependencies_not_admitted"],
        )
        invariants = " ".join(reconciliation["contract_invariants"])
        self.assertIn("20 active size/colour combinations", invariants)
        self.assertIn("backend source of truth", invariants)
        self.assertIn("administrator review", invariants)
        self.assertEqual(
            "reconciled-selective-seller-label-port",
            reconciliation["supersedes_disposition"]["to"],
        )
        self.assertEqual("PASS", reconciliation["result"])


if __name__ == "__main__":
    unittest.main()
