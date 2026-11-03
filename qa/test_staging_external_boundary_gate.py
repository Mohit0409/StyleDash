"""Adversarial tests for staging network/credential preflight. No network I/O."""
from __future__ import annotations

import copy
import unittest

from staging_external_boundary_gate import check


class ExternalBoundaryGateTests(unittest.TestCase):
    def setUp(self):
        self.safe = {
            "staging": {
                "ActiveState": "active", "User": "vibe4you-stage", "Group": "vibe4you-stage",
                "PrivateNetwork": "yes", "NetworkNamespacePath": "",
                "IPAddressDeny": "", "EnvironmentFileStageScoped": True,
                "EnvironmentFileMentionsProduction": False,
            },
            "production": {"User": "vibe4you", "Group": "vibe4you"},
            "flags": {
                "RAZORPAY_MODE": "test",
                "STYLEDASH_ORDERING_ENABLED": "false",
                "STYLEDASH_NTFY_ENABLED": "false",
                "STYLEDASH_NTFY_BACKGROUND": "false",
                "STYLEDASH_ENABLE_TEST_PRODUCT": "false",
            },
            "origin": {"is_localhost": True, "is_public_site": False},
            "env_key_names": ["RAZORPAY_MODE", "STYLEDASH_TOTP_ENCRYPTION_KEY"],
            "listeners": {"8080": {"loopback_only": True}, "8081": {"loopback_only": True}},
            "runtime": {
                "production_loopback_api_blocked": True,
                "external_egress_policy_verified": True,
                "authentication_credentials_distinct": True,
                "staging_health_after_network_policy": True,
            },
        }

    def run_gate(self, mutate=None):
        data = copy.deepcopy(self.safe)
        if mutate:
            mutate(data)
        return check(data)

    def test_all_explicit_evidence_can_pass_policy(self):
        self.assertTrue(self.run_gate()["passed"])

    def test_shared_host_network_without_policy_fails(self):
        x = self.run_gate(lambda d: d["staging"].update(PrivateNetwork="no"))
        self.assertIn("staging_shared_host_network_without_service_policy", x["issues"])

    def test_ip_deny_any_requires_runtime_proofs(self):
        def change(d):
            d["staging"].update(PrivateNetwork="no", IPAddressDeny="any")
            d["runtime"]["production_loopback_api_blocked"] = None
        x = self.run_gate(change)
        self.assertIn("production_localhost_api_denial_not_verified", x["issues"])

    def test_reused_production_identity_fails(self):
        x = self.run_gate(lambda d: d["staging"].update(User="vibe4you"))
        self.assertIn("staging_shares_production_identity",x["issues"])

    def test_production_env_file_reference_fails(self):
        x = self.run_gate(lambda d: d["staging"].update(EnvironmentFileMentionsProduction=True))
        self.assertIn("staging_environment_source_not_isolated",x["issues"])

    def test_production_origin_fails(self):
        x = self.run_gate(lambda d: d["origin"].update(is_localhost=False,is_public_site=True))
        self.assertIn("staging_public_origin_not_local",x["issues"])

    def test_live_payment_mode_fails(self):
        x = self.run_gate(lambda d: d["flags"].update(RAZORPAY_MODE="live"))
        self.assertIn("razorpay_not_test_mode",x["issues"])

    def test_ordering_enabled_fails(self):
        x = self.run_gate(lambda d: d["flags"].update(STYLEDASH_ORDERING_ENABLED="true"))
        self.assertIn("external_side_effects_enabled_or_unknown:STYLEDASH_ORDERING_ENABLED",x["issues"])

    def test_missing_notifications_flag_fails_closed(self):
        x = self.run_gate(lambda d: d["flags"].pop("STYLEDASH_NTFY_ENABLED"))
        self.assertIn("external_side_effects_enabled_or_unknown:STYLEDASH_NTFY_ENABLED",x["issues"])

    def test_payment_keys_present_fails(self):
        x = self.run_gate(lambda d: d["env_key_names"].append("RAZORPAY_KEY_SECRET"))
        self.assertIn("payment_or_messaging_credentials_in_staging_env",x["issues"])

    def test_missing_secret_inventory_fails_closed(self):
        x = self.run_gate(lambda d: d.pop("env_key_names"))
        self.assertIn("staging_environment_key_inventory_missing",x["issues"])

    def test_missing_production_port_listener_evidence_fails(self):
        x = self.run_gate(lambda d: d["listeners"].pop("8081"))
        self.assertIn("production_listener_exposure_unknown:8081",x["issues"])

    def test_loopback_exposed_listener_fails(self):
        x = self.run_gate(lambda d: d["listeners"]["8080"].update(loopback_only=False))
        self.assertIn("production_listener_exposure_unknown:8080",x["issues"])

    def test_missing_runtime_localhost_denial_fails(self):
        x = self.run_gate(lambda d: d["runtime"].update(production_loopback_api_blocked=None))
        self.assertIn("production_localhost_api_denial_not_verified",x["issues"])

    def test_missing_egress_verified_fails(self):
        x = self.run_gate(lambda d: d["runtime"].update(external_egress_policy_verified=False))
        self.assertIn("external_egress_restrictions_not_verified",x["issues"])

    def test_missing_credential_distinct_verification_fails(self):
        x = self.run_gate(lambda d: d["runtime"].update(authentication_credentials_distinct=False))
        self.assertIn("authentication_credential_separation_not_verified",x["issues"])

    def test_runtime_health_must_be_checked(self):
        x = self.run_gate(lambda d: d["runtime"].update(staging_health_after_network_policy=False))
        self.assertIn("staging_health_after_network_policy_not_verified",x["issues"])

    def test_inactive_stage_fails(self):
        x = self.run_gate(lambda d: d["staging"].update(ActiveState="inactive"))
        self.assertIn("staging_not_active",x["issues"])


if __name__ == "__main__":
    unittest.main()
