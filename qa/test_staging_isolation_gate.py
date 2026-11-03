"""Adversarial offline tests for staging-only isolation preflight."""
from __future__ import annotations

import copy
import unittest

from staging_isolation_gate import check_staging, PROTECTED_PRODUCTION_ROOTS


class StagingIsolationGateTests(unittest.TestCase):
    def setUp(self):
        self.good = {
            "production": {"User": "vibe4you"},
            "staging": {
                "ActiveState": "active",
                "User": "vibe4you",
                "ProtectSystem": "strict",
                "NoNewPrivileges": "yes",
                "PrivateTmp": "yes",
                "ProtectHome": "yes",
                "ReadWritePaths": "/var/lib/vibe4you-staging",
                "InaccessiblePaths": " ".join(PROTECTED_PRODUCTION_ROOTS),
            },
            "paths": {
                key: {"scope": "staging", "exists": True}
                for key in (
                    "STYLEDASH_DATABASE_PATH",
                    "STYLEDASH_DATA_DIR",
                    "STYLEDASH_CATALOG_PATH",
                    "STYLEDASH_SETTINGS_PATH",
                )
            },
            "settings": {
                "RAZORPAY_MODE": "test",
                "STYLEDASH_ORDERING_ENABLED": "false",
                "STYLEDASH_NTFY_ENABLED": "false",
                "STYLEDASH_NTFY_BACKGROUND": "false",
                "STYLEDASH_ENABLE_TEST_PRODUCT": "false",
            },
        }

    def check(self, updater=None):
        data = copy.deepcopy(self.good)
        if updater:
            updater(data)
        return check_staging(data)

    def test_explicit_staging_mount_isolation_can_pass_configuration_gate(self):
        result = self.check()
        self.assertTrue(result["passed"], result)
        self.assertTrue(result["shared_service_account"])
        self.assertFalse(result["full_runtime_isolation_verified"])

    def test_current_runtime_missing_inaccessible_paths_fails(self):
        result = self.check(lambda s: s["staging"].update(InaccessiblePaths=""))
        self.assertIn("production_filesystem_not_hidden", result["issues"])

    def test_partial_hidden_paths_fails(self):
        result = self.check(lambda s: s["staging"].update(
            InaccessiblePaths=" ".join(PROTECTED_PRODUCTION_ROOTS[:-1])
        ))
        self.assertIn("production_filesystem_not_hidden", result["issues"])

    def test_systemd_optional_dash_modifier_does_not_count_as_block(self):
        result = self.check(lambda s: s["staging"].update(
            InaccessiblePaths="-"+PROTECTED_PRODUCTION_ROOTS[0]+" "+" ".join(PROTECTED_PRODUCTION_ROOTS[1:])
        ))
        self.assertIn("production_filesystem_not_hidden", result["issues"])

    def test_extra_writable_production_path_fails(self):
        result = self.check(lambda s: s["staging"].update(
            ReadWritePaths="/var/lib/vibe4you-staging /var/lib/vibe4you-production"
        ))
        self.assertIn("unexpected_staging_write_paths", result["issues"])

    def test_unisolated_data_path_fails(self):
        result = self.check(lambda s: s["paths"]["STYLEDASH_DATABASE_PATH"].update(scope="production"))
        self.assertIn("data_path_outside_staging:STYLEDASH_DATABASE_PATH",result["issues"])

    def test_live_payment_mode_fails(self):
        result = self.check(lambda s: s["settings"].update(RAZORPAY_MODE="live"))
        self.assertIn("razorpay_not_test_mode", result["issues"])

    def test_ordering_enabled_fails(self):
        result = self.check(lambda s: s["settings"].update(STYLEDASH_ORDERING_ENABLED="true"))
        self.assertIn("staging_external_actions_not_disabled:STYLEDASH_ORDERING_ENABLED",result["issues"])

    def test_notifications_enabled_fails(self):
        result = self.check(lambda s: s["settings"].update(STYLEDASH_NTFY_ENABLED="yes"))
        self.assertIn("staging_external_actions_not_disabled:STYLEDASH_NTFY_ENABLED",result["issues"])

    def test_too_little_confinement_fails(self):
        result = self.check(lambda s: s["staging"].update(ProtectSystem="full",NoNewPrivileges="no"))
        self.assertIn("protect_system_not_strict",result["issues"])
        self.assertIn("privilege_escalation_not_disabled",result["issues"])

    def test_inactive_staging_fails(self):
        result = self.check(lambda s: s["staging"].update(ActiveState="inactive"))
        self.assertIn("staging_service_not_active",result["issues"])

    def test_missing_runtime_path_snapshot_fails_closed(self):
        result = self.check(lambda s: s["paths"].pop("STYLEDASH_SETTINGS_PATH"))
        self.assertIn("missing_staging_path_status:STYLEDASH_SETTINGS_PATH",result["issues"])


if __name__=="__main__":
    unittest.main()
