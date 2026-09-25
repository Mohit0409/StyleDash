from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "termux" / "deploy-surgical-combined-release"


class SurgicalCombinedReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.script = SCRIPT.read_text(encoding="utf-8")

    def test_rollback_namespaces_cannot_collide(self) -> None:
        self.assertIn('"$ROLLBACK/public/runtime/serve.py"', self.script)
        self.assertIn('"$ROLLBACK/admin/runtime/serve.py"', self.script)
        self.assertNotIn('"$ROLLBACK/serve.py"', self.script)
        self.assertIn('"$ROLLBACK/public/static/assets"', self.script)
        self.assertNotIn('"$ROLLBACK/admin/static/admin.js"', self.script)

    def test_services_are_stopped_before_any_runtime_install(self) -> None:
        watchdog = self.script.index('styledash_watchdog_stop "$WATCHDOG_MARKER"')
        public_stop = self.script.index(
            'styledash_stop_matching_processes "StyleDash public service"', watchdog
        )
        port_release = self.script.index(
            'styledash_wait_for_port_release 8080 "StyleDash public service"', public_stop
        )
        public_install = self.script.index(
            'install -m 755 "$STAGE/scripts/termux-spa-server.py"', port_release
        )
        self.assertLess(watchdog, public_stop)
        self.assertLess(public_stop, port_release)
        self.assertLess(port_release, public_install)

    def test_new_processes_must_replace_old_processes(self) -> None:
        self.assertIn('OLD_PUBLIC_PID="$(styledash_read_pid_file', self.script)
        self.assertIn('OLD_ADMIN_PID="$(styledash_read_pid_file', self.script)
        self.assertIn('NEW_PUBLIC_PID="$(styledash_read_pid_file', self.script)
        self.assertIn('NEW_ADMIN_PID="$(styledash_read_pid_file', self.script)
        self.assertIn(
            '[ "$NEW_PUBLIC_PID" = "$OLD_PUBLIC_PID" ] || '
            '[ "$NEW_ADMIN_PID" = "$OLD_ADMIN_PID" ]',
            self.script,
        )

    def test_acceptance_checks_cover_new_and_existing_routes(self) -> None:
        self.assertIn('/api/shop-products/homepage"', self.script)
        self.assertIn('/api/shop-products/published"', self.script)
        self.assertIn('/api/health"', self.script)
        self.assertIn('/admin"', self.script)
        self.assertIn('/api/admin/me"', self.script)
        self.assertIn('private administrator health returned HTTP', self.script)
        self.assertIn('PRAGMA integrity_check', self.script)
        self.assertIn('PRAGMA foreign_key_check', self.script)

    def test_unrelated_live_configuration_is_hash_guarded_and_release_modules_are_pinned(self) -> None:
        for protected in (
            '"$PUBLIC_DIR/styledash_security.py"',
            '"$ADMIN_DIR/styledash_security.py"',
            '"$ADMIN_DIR/admin/index.html"',
            '"$ADMIN_DIR/admin/admin.js"',
            '"$DATA_ROOT/catalog.json"',
            '"$DATA_ROOT/settings.json"',
            '"$DATA_ROOT/delivery-zones.geojson"',
            '"$HOME/.config/styledash/secrets.env"',
        ):
            self.assertIn(protected, self.script)
        self.assertIn('protected_file_hashes=unchanged', self.script)
        self.assertIn('assert_approved_module_baseline', self.script)
        self.assertIn('assert_approved_stage_modules', self.script)
        self.assertIn('approved category/shop module has an unexpected live hash', self.script)
        self.assertIn('approved category/shop staged module has an unexpected hash', self.script)
        self.assertIn('approved_category_module_baseline=verified', self.script)
        self.assertIn('approved_category_stage_modules=verified', self.script)
        self.assertIn('approved_category_modules=installed', self.script)
        self.assertIn('approved_category_modules=restored', self.script)
        self.assertIn('install -m 600 "$STAGE/scripts/catalog_normalization.py"', self.script)
        self.assertIn('install -m 600 "$STAGE/scripts/styledash_shops.py"', self.script)
        self.assertNotIn('install -m 600 "$STAGE/scripts/styledash_security.py"', self.script)
        baseline = self.script.index('assert_approved_module_baseline', self.script.index('database_check\nassert_approved_module_baseline'))
        stage = self.script.index('assert_approved_stage_modules', self.script.index('assert_approved_module_baseline\nassert_approved_stage_modules'))
        backup = self.script.index('bash "$STAGE/scripts/termux/backup-styledash-data"')
        mutation = self.script.index('MUTATION_STARTED=1')
        self.assertLess(baseline, backup)
        self.assertLess(baseline, mutation)
        self.assertLess(stage, backup)
        self.assertLess(stage, mutation)

        self.assertNotIn(
            'install -m 600 "$STAGE/server/admin/index.html"', self.script
        )
        self.assertNotIn(

            'install -m 600 "$STAGE/server/admin/admin.js"', self.script
        )
    def test_failure_after_mutation_triggers_automatic_code_only_rollback(self) -> None:
        self.assertIn("trap 'handle_failure $? $LINENO' ERR", self.script)
        self.assertIn('rollback_release || true', self.script)
        self.assertIn('automatic_rollback=PASS', self.script)
        self.assertIn('production_data=preserved', self.script)
        self.assertNotIn('restore_file "$ROLLBACK', self.script.split('LIVE_DB=', 1)[0])
        rollback_body = self.script.split('rollback_release() {', 1)[1].split(
            'handle_failure() {', 1
        )[0]
        self.assertNotIn('styledash.db', rollback_body)
        self.assertNotIn('orders.json', rollback_body)

    def test_fresh_supported_backup_finishes_before_mutation(self) -> None:
        backup = self.script.index('bash "$STAGE/scripts/termux/backup-styledash-data"')
        mutation = self.script.index('MUTATION_STARTED=1')
        self.assertLess(backup, mutation)
        self.assertIn('sqlite_integrity=ok', self.script)
        self.assertIn('sqlite_foreign_key_errors=0', self.script)

    def test_cloudflare_is_preserved_and_verified_as_http2(self) -> None:
        self.assertIn('cloudflared tunnel run --protocol http2', self.script)
        self.assertIn("'--protocol http2'", self.script)
        self.assertIn('cloudflare_transport=http2', self.script)
        self.assertNotIn('styledash_stop_matching_processes "StyleDash Cloudflare tunnel"', self.script)

    def test_stage_cannot_overlap_live_or_rollback_directories(self) -> None:
        self.assertIn('staging directory overlaps a managed production or backup directory', self.script)
        self.assertIn('"$PUBLIC_DIR"|"$PUBLIC_DIR"/*', self.script)
        self.assertIn('"$ADMIN_DIR"|"$ADMIN_DIR"/*', self.script)
        self.assertIn('"$DATA_ROOT"|"$DATA_ROOT"/*', self.script)
        self.assertIn('"$BACKUP_ROOT"|"$BACKUP_ROOT"/*', self.script)
        self.assertIn('surgical release frontend contains an unexpected top-level file', self.script)
        self.assertIn('surgical release file is a symbolic link', self.script)
        self.assertIn("stat -c '%u'", self.script)

    def test_firebase_browser_config_is_required_before_mutation(self) -> None:
        self.assertIn('surgical release contains an empty Firebase web configuration', self.script)
        self.assertIn('surgical release is missing a complete Firebase web configuration', self.script)
        self.assertIn('Firebase browser and server project IDs do not match', self.script)
        firebase_guard = self.script.index('firebase_assets=("$STAGE"/dist/assets/*.js)')
        backup = self.script.index('bash "$STAGE/scripts/termux/backup-styledash-data"')
        mutation = self.script.index('MUTATION_STARTED=1')
        self.assertLess(firebase_guard, backup)
        self.assertLess(firebase_guard, mutation)


if __name__ == "__main__":
    unittest.main()
