from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "termux" / "deploy-surgical-combined-release"


def find_bash() -> str | None:
    found = shutil.which("bash")
    if found:
        return found
    if os.name == "nt":
        for candidate in (
            Path(r"C:\Program Files\Git\bin\bash.exe"),
            Path(r"C:\Program Files\Git\usr\bin\bash.exe"),
        ):
            if candidate.exists():
                return str(candidate)
    return None


def bash_path(path: Path) -> str:
    value = path.resolve().as_posix()
    if os.name == "nt" and len(value) >= 3 and value[1:3] == ":/":
        return f"/{value[0].lower()}/{value[3:]}"
    return value


class SurgicalReleaseIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bash = find_bash()
        if cls.bash is None:
            raise unittest.SkipTest("bash is required for surgical release integration tests")

    def write(self, path: Path, content: str, executable: bool = False) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
        if executable:
            path.chmod(0o755)

    def fixture(self, root: Path) -> tuple[Path, Path, Path]:
        home = root / "home"
        stage = root / "stage"
        mock_bin = root / "mock-bin"
        for directory in (
            home / "server" / "assets",
            home / "admin" / "admin",
            home / ".local" / "share" / "styledash",
            home / ".config" / "styledash",
            home / "bin",
            home / "run",
            home / "logs",
            home / "backups",
            stage / "dist" / "assets",
            stage / "scripts" / "termux",
            mock_bin,
        ):
            directory.mkdir(parents=True, exist_ok=True)

        old_files = {
            home / "server" / "serve.py": "old-public-server\n",
            home / "server" / "styledash_reviews.py": "old-public-reviews\n",
            home / "server" / "index.html": "old-frontend\n",
            home / "server" / "assets" / "old.js": "old-asset\n",
            home / "admin" / "serve.py": "old-admin-server\n",
            home / "admin" / "styledash_reviews.py": "old-admin-reviews\n",
            home / "admin" / "admin" / "index.html": "old-admin-index\n",
            home / "admin" / "admin" / "admin.js": "old-admin-js\n",
            home / "bin" / "backup-styledash-data": "#!/usr/bin/env bash\necho backup=verified\n",
            home / "bin" / "start-styledash-cloudflare": "#!/usr/bin/env bash\necho old-cloudflare\n",
        }
        for path, content in old_files.items():
            self.write(path, content, path.parent == home / "bin")

        for location in (home / "server", home / "admin"):
            self.write(location / "styledash_security.py", "security-preserved\n")
            self.write(location / "catalog_normalization.py", "normalization-preserved\n")
            self.write(location / "styledash_shops.py", "shops-preserved\n")
        data = home / ".local" / "share" / "styledash"
        self.write(data / "styledash.db", "mock-db\n")
        self.write(data / "catalog.json", "{}\n")
        self.write(data / "settings.json", "{}\n")
        self.write(data / "delivery-zones.geojson", "{}\n")
        self.write(
            home / ".config" / "styledash" / "secrets.env",
            "MOCK_ONLY=1\nSTYLEDASH_FIREBASE_PROJECT_ID=styledash-auth\n",
        )

        self.write(home / "run" / "styledash.pid", "101\n")
        self.write(home / "run" / "styledash-admin.pid", "202\n")
        self.write(home / "run" / "styledash-cloudflare.pid", "505\n")

        process_lib = r'''#!/usr/bin/env bash
styledash_read_pid_file() { cat "$1"; }
styledash_assert_single_process() { [ -n "$1" ]; }
styledash_stop_matching_processes() { return 0; }
styledash_wait_for_port_release() { return 0; }
styledash_watchdog_stop() { return 0; }
styledash_watchdog_start() { return 0; }
styledash_cmdline() { echo "cloudflared tunnel run --protocol http2 --token-file $HOME/.config/styledash/cloudflare-tunnel-token"; }
'''
        self.write(home / "bin" / "styledash-process-lib", process_lib, True)
        self.write(
            home / "bin" / "styledash-notify",
            "#!/usr/bin/env bash\nexit 0\n",
            True,
        )
        self.write(
            home / "bin" / "start-styledash",
            '#!/usr/bin/env bash\nprintf "303\\n" > "$HOME/run/styledash.pid"\n',
            True,
        )
        self.write(
            home / "bin" / "start-styledash-admin",
            '#!/usr/bin/env bash\nprintf "404\\n" > "$HOME/run/styledash-admin.pid"\n',
            True,
        )

        stage_files = {
            stage / "dist" / "index.html": "new-frontend\n",
            stage / "dist" / "favicon.svg": "new-favicon\n",
            stage / "dist" / "manifest.json": "{}\n",
            stage / "dist" / "product-placeholder.svg": "new-placeholder\n",
            stage / "dist" / "robots.txt": "User-agent: *\n",
            stage / "dist" / "assets" / "new.js": (
                'const firebaseConfig={apiKey:"test-api-key",'
                'authDomain:"styledash-auth.firebaseapp.com",projectId:"styledash-auth",appId:"test-app-id"};\n'
            ),
            stage / "scripts" / "termux-spa-server.py": "new-public-server\n",
            stage / "scripts" / "termux-admin-server.py": "new-admin-server\n",
            stage / "scripts" / "styledash_reviews.py": "new-reviews\n",
            stage / "scripts" / "termux" / "backup-styledash-data": "#!/usr/bin/env bash\necho staged-backup\n",
            stage / "scripts" / "termux" / "start-styledash-cloudflare": "#!/usr/bin/env bash\ncloudflared tunnel run --protocol http2 --token-file token\n",
        }
        for path, content in stage_files.items():
            self.write(path, content, "scripts/termux" in path.as_posix())

        curl_mock = r'''#!/usr/bin/env bash
url=''
for argument in "$@"; do
  case "$argument" in http://*) url="$argument" ;; esac
done
status=200
case "$url" in
  */admin|*/api/admin/me) status=404 ;;
  */api/shop-products/homepage)
    [ "${MOCK_HOMEPAGE_FAILURE:-0}" = 1 ] && status=500
    ;;
esac
printf '%s' "$status"
'''
        self.write(mock_bin / "curl", curl_mock, True)
        self.write(
            mock_bin / "python3",
            '#!/usr/bin/env bash\necho sqlite_integrity=ok\necho sqlite_foreign_key_errors=0\n',
            True,
        )
        return home, stage, mock_bin

    def run_deploy(
        self, home: Path, stage: Path, mock_bin: Path, fail_homepage: bool = False
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        # Git for Windows converts a native HOME path at Bash startup. Passing
        # an already-POSIX path here makes its startup code fall back to the
        # real account home instead of the isolated fixture.
        env["HOME"] = str(home)
        if fail_homepage:
            env["MOCK_HOMEPAGE_FAILURE"] = "1"
        return subprocess.run(
            [
                self.bash,
                "-c",
                'export PATH="$1:/usr/bin:/bin:$PATH"; deploy="$2"; stage="$3"; '
                'set -- "$stage"; source "$deploy"',
                "surgical-release-test",
                bash_path(mock_bin),
                bash_path(DEPLOY),
                bash_path(stage),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )

    def test_success_replaces_runtime_and_records_separate_rollback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home, stage, mock_bin = self.fixture(Path(temporary))
            result = self.run_deploy(home, stage, mock_bin)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("surgical_deployment=PASS", result.stdout)
            self.assertIn("old_public_pid=101", result.stdout)
            self.assertIn("new_public_pid=303", result.stdout)
            self.assertEqual((home / "server" / "serve.py").read_text(), "new-public-server\n")
            self.assertEqual((home / "admin" / "serve.py").read_text(), "new-admin-server\n")
            self.assertTrue((home / "server" / "assets" / "new.js").is_file())
            self.assertEqual(
                (home / "admin" / "admin" / "index.html").read_text(), "old-admin-index\n"
            )
            self.assertEqual(
                (home / "admin" / "admin" / "admin.js").read_text(), "old-admin-js\n"
            )
            self.assertFalse((home / "server" / "assets" / "old.js").exists())
            rollback_marker = (
                home / "run" / "styledash-last-surgical-backup"
            ).read_text().strip()
            rollback = home / "backups" / Path(rollback_marker).name
            self.assertTrue((rollback / "public" / "runtime" / "serve.py").is_file())
            self.assertTrue((rollback / "admin" / "runtime" / "serve.py").is_file())
            self.assertFalse((rollback / "serve.py").exists())

    def test_acceptance_failure_restores_exact_old_public_admin_and_ops_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home, stage, mock_bin = self.fixture(Path(temporary))
            result = self.run_deploy(home, stage, mock_bin, fail_homepage=True)
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("automatic_rollback=PASS", result.stdout)
            self.assertEqual((home / "server" / "serve.py").read_text(), "old-public-server\n")
            self.assertEqual(
                (home / "server" / "styledash_reviews.py").read_text(),
                "old-public-reviews\n",
            )
            self.assertEqual((home / "server" / "index.html").read_text(), "old-frontend\n")
            self.assertTrue((home / "server" / "assets" / "old.js").is_file())
            self.assertFalse((home / "server" / "assets" / "new.js").exists())
            self.assertEqual((home / "admin" / "serve.py").read_text(), "old-admin-server\n")
            self.assertEqual(
                (home / "admin" / "admin" / "admin.js").read_text(), "old-admin-js\n"
            )
            self.assertIn(
                "backup=verified", (home / "bin" / "backup-styledash-data").read_text()
            )
            self.assertIn(
                "old-cloudflare", (home / "bin" / "start-styledash-cloudflare").read_text()
            )
            self.assertEqual(
                (home / "server" / "styledash_shops.py").read_text(),
                "shops-preserved\n",
            )


    def test_empty_firebase_config_is_rejected_before_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home, stage, mock_bin = self.fixture(Path(temporary))
            self.write(
                stage / "dist" / "assets" / "new.js",
                'const firebaseConfig={apiKey:"",authDomain:"",projectId:"",appId:""};\n',
            )
            result = self.run_deploy(home, stage, mock_bin)
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("empty Firebase web configuration", result.stderr)
            self.assertEqual((home / "server" / "index.html").read_text(), "old-frontend\n")
            self.assertTrue((home / "server" / "assets" / "old.js").is_file())
            self.assertFalse((home / "server" / "assets" / "new.js").exists())


if __name__ == "__main__":
    unittest.main()
