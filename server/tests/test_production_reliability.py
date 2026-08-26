from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class ProductionReliabilityTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_ci_covers_required_release_checks(self) -> None:
        workflow = self.read(".github/workflows/ci.yml")
        for command in (
            "npm run typecheck",
            "npm run lint",
            "npm test",
            "npm run build",
            "npm audit --omit=dev",
            'python -m unittest discover -s server/tests -p "test_*.py"',
            "npm run test:e2e:desktop",
            "npm run test:e2e:mobile",
        ):
            self.assertIn(command, workflow)
        self.assertIn("cache: npm", workflow)
        self.assertIn("cache: pip", workflow)
        self.assertIn("name: StyleDash Required CI", workflow)

    def test_main_protection_requires_pr_ci_and_disables_force_pushes(self) -> None:
        policy = json.loads(self.read(".github/main-protection.json"))
        self.assertTrue(policy["required_status_checks"]["strict"])
        self.assertEqual(
            policy["required_status_checks"]["contexts"],
            ["StyleDash Required CI"],
        )
        self.assertTrue(policy["enforce_admins"])
        self.assertIsNotNone(policy["required_pull_request_reviews"])
        self.assertEqual(
            policy["required_pull_request_reviews"]["required_approving_review_count"],
            0,
        )
        self.assertFalse(policy["allow_force_pushes"])
        self.assertFalse(policy["allow_deletions"])

    def test_backup_is_online_integrity_checked_and_supports_offdevice_copy(self) -> None:
        script = self.read("scripts/termux/backup-styledash-data")
        self.assertIn("source.backup(target)", script)
        self.assertIn("PRAGMA integrity_check", script)
        self.assertIn("STYLEDASH_BACKUP_REMOTE", script)
        self.assertIn('rclone copy "$target" "$remote_target"', script)
        self.assertIn('rclone check "$target" "$remote_target"', script)
        self.assertIn("--download", script)
        self.assertIn("--local-only", script)
        self.assertIn("STYLEDASH_BACKUP_REMOTE_SECONDARY", script)
        self.assertIn('rclone copy "$target" "$secondary_target"', script)
        self.assertIn('rclone check "$target" "$secondary_target"', script)
        self.assertIn("styledash-last-secondary-backup", script)
        self.assertIn("STYLEDASH_BACKUP_SECONDARY_TIMEOUT_SECONDS", script)
        self.assertIn('timeout "${secondary_timeout}s" rclone copy', script)
        self.assertIn('timeout "${secondary_timeout}s" rclone check', script)
        self.assertIn("primary backup remains verified", script)

    def test_full_recovery_bundle_is_encrypted_verified_and_offdevice(self) -> None:
        script = self.read("scripts/termux/backup-styledash-recovery")
        self.assertIn("openssl enc -aes-256-cbc", script)
        self.assertIn("-pbkdf2", script)
        self.assertIn("sha256sum -c SHA256SUMS", script)
        self.assertIn("STYLEDASH_RECOVERY_WINDOWS_HOST", script)
        self.assertIn("STYLEDASH_RECOVERY_WINDOWS_PASSWORD_FILE", script)
        self.assertIn("STYLEDASH_RECOVERY_REMOTE_PRIMARY", script)
        self.assertIn("STYLEDASH_RECOVERY_REMOTE_SECONDARY", script)
        self.assertIn("umask 077", script)
        self.assertIn('rm -f "$ARCHIVE"', script)
        self.assertIn("SUCCESS=1", script)
        self.assertNotIn("100.106.126.74", script)
        self.assertNotIn(r"C:\\Users\\", script)

    def test_watchdog_checks_and_notifies_both_services(self) -> None:
        script = self.read("scripts/termux/styledash-health")
        self.assertIn("http://127.0.0.1:8080/api/health", script)
        self.assertIn("http://127.0.0.1:8081/", script)
        self.assertIn("public_restart_failed", script)
        self.assertIn("admin_restart_failed", script)
        self.assertIn("backup_failed", script)
        self.assertIn("LAST_RECOVERY_FILE", script)
        self.assertIn("RECOVERY_RETRY_SECONDS", script)
        self.assertIn('"$HOME/bin/backup-styledash-recovery"', script)
        self.assertIn("recovery_backup_failed", script)

    def test_rollback_preserves_live_database_history(self) -> None:
        script = self.read("scripts/termux/rollback-payment-release")
        self.assertIn('backup-styledash-data" --local-only', script)
        self.assertIn("production_data=preserved", script)
        self.assertNotIn("styledash.db", script)
        self.assertNotIn("orders.json", script)

    def test_deploy_records_and_installs_rollback_tooling(self) -> None:
        script = self.read("scripts/termux/deploy-payment-release")
        self.assertIn("styledash-last-release-backup", script)
        self.assertIn(
            'install -m 755 "$STAGE/scripts/termux/rollback-payment-release" '
            '"$HOME/bin/rollback-payment-release"',
            script,
        )
        self.assertIn(
            'install -m 755 "$STAGE/scripts/termux/styledash-notify" '
            '"$HOME/bin/styledash-notify"',
            script,
        )
        self.assertIn(
            'install -m 700 "$STAGE/scripts/termux/backup-styledash-recovery" '
            '"$HOME/bin/backup-styledash-recovery"',
            script,
        )
        self.assertIn("razorpay-global-preload-unexpected", script)
        self.assertIn("razorpay-lazy-load-ok", script)
        self.assertIn("https://checkout.razorpay.com/v1/checkout.js", script)
        self.assertNotIn("razorpay-script-missing", script)

    def test_repository_production_branch_is_main(self) -> None:
        agents = self.read("AGENTS.md")
        self.assertIn("The production branch is `main`", agents)


if __name__ == "__main__":
    unittest.main()
