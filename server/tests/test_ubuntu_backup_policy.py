from pathlib import Path
import hashlib
import unittest


ROOT = Path(__file__).resolve().parents[2]
BACKUP = ROOT / "scripts" / "ubuntu" / "backup-styledash-data"
OPS = ROOT / "scripts" / "ubuntu" / "vibe4you-ops"
INSTALLER = ROOT / "scripts" / "ubuntu" / "install-vibe4you-deployment-backup-mode.sh"
ROLLBACK = ROOT / "scripts" / "ubuntu" / "rollback-vibe4you-deployment-backup-mode.sh"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class UbuntuDeploymentBackupPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.backup = BACKUP.read_text(encoding="utf-8")
        cls.ops = OPS.read_text(encoding="utf-8")
        cls.installer = INSTALLER.read_text(encoding="utf-8")
        cls.rollback = ROLLBACK.read_text(encoding="utf-8")

    def test_deployment_mode_uses_24_hour_primary_freshness_default(self):
        self.assertIn(
            'DEPLOYMENT_MAX_PRIMARY_AGE_SECONDS="${STYLEDASH_DEPLOYMENT_MAX_PRIMARY_AGE_SECONDS:-86400}"',
            self.backup,
        )
        self.assertIn(
            'marker="$RUN_DIR/styledash-last-offdevice-backup"',
            self.backup,
        )

    def test_deployment_freshness_is_checked_before_snapshot_creation(self):
        freshness = self.backup.index('  assert_recent_primary_backup')
        snapshot = self.backup.index('stamp="$(date -u +%Y%m%dT%H%M%SZ)"')
        self.assertLess(freshness, snapshot)

    def test_deployment_mode_skips_primary_upload_and_verifies_windows_secondary(self):
        start = self.backup.index(
            'if [ "$MODE" = "deployment" ]; then\n  secondary='
        )
        end = self.backup.index('elif [ "$MODE" = "full" ]; then', start)
        block = self.backup[start:end]

        self.assertIn('STYLEDASH_BACKUP_REMOTE_SECONDARY', block)
        self.assertIn('run_rclone copy "$target" "$secondary_target"', block)
        self.assertIn(
            'verify_remote "$target" "$secondary_target" '
            '"Deployment secondary off-device backup"',
            block,
        )
        self.assertIn(
            'Deployment backup skipped primary cloud upload',
            block,
        )
        self.assertNotIn('remote_target=', block)
        self.assertNotIn('Primary off-device Vibe4You backup verified', block)

    def test_full_mode_still_contains_primary_and_secondary_replication(self):
        start = self.backup.index('elif [ "$MODE" = "full" ]; then')
        block = self.backup[start:]
        self.assertIn('remote="${STYLEDASH_BACKUP_REMOTE:-}"', block)
        self.assertIn('remote_target="${remote%/}/$stamp"', block)
        self.assertIn(
            'verify_remote "$target" "$remote_target" "Primary off-device backup"',
            block,
        )
        self.assertIn('secondary="${STYLEDASH_BACKUP_REMOTE_SECONDARY:-}"', block)
        self.assertIn(
            'verify_remote "$target" "$secondary_target" "Secondary off-device backup"',
            block,
        )

    def test_privileged_wrapper_exposes_explicit_deployment_backup_action(self):
        self.assertIn('backup-deployment)', self.ops)
        self.assertIn(
            'runuser -u vibe4you -- "$script" --deployment',
            self.ops,
        )
        self.assertIn(
            'A scheduled/full Vibe4You backup is already running; deployment backup refused',
            self.ops,
        )

    def test_installer_hashes_are_pinned_to_exact_candidate_files(self):
        self.assertIn(
            'EXPECTED_CANDIDATE_BACKUP_SHA256="{}"'.format(sha256(BACKUP)),
            self.installer,
        )
        self.assertIn(
            'EXPECTED_CANDIDATE_OPS_SHA256="{}"'.format(sha256(OPS)),
            self.installer,
        )

    def test_installer_keeps_normal_backup_timer_active(self):
        self.assertNotIn('systemctl stop vibe4you-backup.timer', self.installer)
        self.assertNotIn('systemctl disable vibe4you-backup.timer', self.installer)
        self.assertIn('vibe4you-backup.timer', self.installer)

    def test_installer_proves_cloud_skipped_and_fresh_local_secondary_created(self):
        self.assertIn(
            'if [ "$after_primary" != "$before_primary" ]; then',
            self.installer,
        )
        self.assertIn(
            'if [ -z "$after_secondary" ] || [ "$after_secondary" = "$before_secondary" ]; then',
            self.installer,
        )
        self.assertIn(
            'if [ -z "$after_local" ] || [ "$after_local" = "$before_local" ]; then',
            self.installer,
        )
        self.assertIn(
            'if [ "$after_local" != "$after_secondary" ]; then',
            self.installer,
        )

    def test_rollback_restores_only_backup_script_and_ops_wrapper(self):
        self.assertIn(
            'install -o root -g vibe4you -m 0750 "$ROLLBACK_DIR/backup-styledash-data"',
            self.rollback,
        )
        self.assertIn(
            'install -o root -g root -m 0755 "$ROLLBACK_DIR/vibe4you-ops"',
            self.rollback,
        )
        self.assertNotIn('restart', self.rollback.lower())


if __name__ == "__main__":
    unittest.main()
