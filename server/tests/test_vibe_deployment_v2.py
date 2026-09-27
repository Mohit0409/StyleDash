from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sqlite3
import tarfile
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BUILDER = load_module("vibe_artifact_builder", ROOT / "scripts" / "build_deployment_artifact.py")
RUNNER = load_module("vibe_deployment_runner", ROOT / "scripts" / "termux" / "vibe_deploy.py")


class FixtureDeployment(RUNNER.Deployment):
    fail_backup = False
    fail_smoke = False
    backup_calls = 0
    mutation_calls = 0

    def verify_processes(self) -> None:
        return None

    def security_routes(self) -> None:
        return None

    def stop_services(self) -> None:
        return None

    def start_services(self) -> None:
        return None

    def http(self, url: str, expected: int, **_: object) -> bytes:
        if self.fail_smoke and url.endswith("/api/shop-products/published"):
            raise RUNNER.DeployError("forced runtime acceptance failure")
        if expected == 404:
            return b""
        if url.endswith("/api/health"):
            return b'{"status":"ok","service":"Vibe4You","database":"ok"}'
        if url.endswith("/api/shop-products/homepage"):
            return b'[{"id":"fixture-product"}]'
        return b"Vibe4You Local Administration"

    def backup(self) -> str:
        type(self).backup_calls += 1
        if self.fail_backup:
            raise RUNNER.DeployError("forced backup failure")
        self.save_state(
            "BACKUP_PASS",
            backupPassed=True,
            backupTimestamp="20260927T000000Z",
            backupPrimary="PASS",
            backupSecondary="PASS",
        )
        return "20260927T000000Z"

    def mutate(self) -> None:
        type(self).mutation_calls += 1
        super().mutate()


class VibeDeploymentV2Tests(unittest.TestCase):
    def write(self, path: Path, text: str, executable: bool = False) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
        if executable:
            path.chmod(0o755)

    def sha(self, path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def frontend_hash(self, root: Path) -> tuple[str, int]:
        files = [root / name for name in ("index.html", "favicon.svg", "manifest.json", "product-placeholder.svg", "robots.txt")]
        files += sorted(path for path in (root / "assets").rglob("*") if path.is_file())
        lines = [f"{self.sha(path)}  {path.relative_to(root).as_posix()}\n" for path in sorted(files)]
        return hashlib.sha256("".join(lines).encode()).hexdigest(), len(files)

    def make_source(self, root: Path) -> Path:
        source = root / "source"
        files = {
            "scripts/termux-spa-server.py": "print('public')\n",
            "scripts/termux-admin-server.py": "print('admin')\n",
            "scripts/styledash_reviews.py": "REVIEWS = 1\n",
            "scripts/catalog_normalization.py": "NORMALIZATION = 1\n",
            "scripts/styledash_shops.py": "SHOPS = 1\n",
            "scripts/termux/backup-styledash-data": "#!/usr/bin/env bash\nexit 0\n",
            "scripts/termux/start-styledash-cloudflare": "#!/usr/bin/env bash\nexit 0\n",
            "scripts/termux/styledash-process-lib": "#!/usr/bin/env bash\ntrue\n",
            "scripts/termux/vibe-deploy": "#!/usr/bin/env bash\ntrue\n",
            "scripts/termux/vibe_deploy.py": "print('runner')\n",
            "dist/index.html": "<title>fixture</title>\n",
            "dist/favicon.svg": "<svg/>\n",
            "dist/manifest.json": "{}\n",
            "dist/product-placeholder.svg": "<svg/>\n",
            "dist/robots.txt": "User-agent: *\n",
            "dist/assets/index-fixture.js": 'const firebaseConfig={apiKey:"fixture-api",authDomain:"fixture.firebaseapp.com",projectId:"fixture-project",appId:"fixture-app"};const ids="G-FIXTURE 123456789";\n',
        }
        for relative, text in files.items():
            self.write(source / relative, text, "/termux/" in relative)
        return source

    def make_home(self, root: Path, source: Path) -> Path:
        home = root / "home"
        for directory in (
            home / "server" / "assets",
            home / "admin" / "admin",
            home / "bin",
            home / "run",
            home / "logs",
            home / ".config" / "styledash",
            home / ".local" / "share" / "styledash",
        ):
            directory.mkdir(parents=True, exist_ok=True)
        for name in ("index.html", "favicon.svg", "manifest.json", "product-placeholder.svg", "robots.txt"):
            (home / "server" / name).write_bytes((source / "dist" / name).read_bytes())
        (home / "server" / "assets" / "index-fixture.js").write_bytes((source / "dist" / "assets" / "index-fixture.js").read_bytes())
        mapping = {
            "scripts/termux-spa-server.py": ["server/serve.py"],
            "scripts/termux-admin-server.py": ["admin/serve.py"],
            "scripts/styledash_reviews.py": ["server/styledash_reviews.py", "admin/styledash_reviews.py"],
            "scripts/catalog_normalization.py": ["server/catalog_normalization.py", "admin/catalog_normalization.py"],
            "scripts/styledash_shops.py": ["server/styledash_shops.py", "admin/styledash_shops.py"],
            "scripts/termux/backup-styledash-data": ["bin/backup-styledash-data"],
            "scripts/termux/start-styledash-cloudflare": ["bin/start-styledash-cloudflare"],
            "scripts/termux/styledash-process-lib": ["bin/styledash-process-lib"],
        }
        managed: dict[str, str] = {}
        for relative, targets in mapping.items():
            for target in targets:
                target_path = home / target
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_bytes((source / relative).read_bytes())
                managed[target] = self.sha(target_path)
        for relative in (
            "server/styledash_security.py",
            "admin/styledash_security.py",
            "admin/admin/index.html",
            "admin/admin/admin.js",
            ".local/share/styledash/catalog.json",
            ".local/share/styledash/settings.json",
            ".local/share/styledash/delivery-zones.geojson",
        ):
            self.write(home / relative, "protected\n")
        self.write(
            home / ".config" / "styledash" / "secrets.env",
            "STYLEDASH_FIREBASE_PROJECT_ID=fixture-project\nRAZORPAY_MODE=test\nRAZORPAY_TEST_KEY_ID=id\nRAZORPAY_TEST_KEY_SECRET=fixture-private-material\nRAZORPAY_TEST_WEBHOOK_SECRET=fixture-webhook-material\nSTYLEDASH_BACKUP_REMOTE=fixture-primary:backup\nSTYLEDASH_BACKUP_REMOTE_SECONDARY=fixture-secondary:backup\n",
        )
        database = home / ".local" / "share" / "styledash" / "styledash.db"
        connection = sqlite3.connect(database)
        connection.execute("CREATE TABLE fixture (id INTEGER PRIMARY KEY)")
        connection.commit()
        connection.close()
        frontend, count = self.frontend_hash(home / "server")
        bootstrap = {
            "schemaVersion": 1,
            "deployedCommit": "780cde2aca46fc21a02eaa480e55c8060820df94",
            "approvedRuntimeCommit": "780cde2aca46fc21a02eaa480e55c8060820df94",
            "frontendTreeSha256": frontend,
            "frontendFileCount": count,
            "managedFiles": managed,
        }
        self.write(source / "ops" / "deployment-v2-bootstrap.json", json.dumps(bootstrap))
        return home

    def build_artifact(self, root: Path) -> tuple[Path, Path]:
        source = self.make_source(root)
        home = self.make_home(root, source)
        artifact = root / "fixture.tar.gz"
        old = dict(os.environ)
        os.environ.update(
            {
                "VITE_FIREBASE_API_KEY": "fixture-api",
                "VITE_FIREBASE_AUTH_DOMAIN": "fixture.firebaseapp.com",
                "VITE_FIREBASE_PROJECT_ID": "fixture-project",
                "VITE_FIREBASE_APP_ID": "fixture-app",
                "VITE_GA_MEASUREMENT_ID": "G-FIXTURE",
                "VITE_META_PIXEL_ID": "123456789",
            }
        )
        try:
            BUILDER.build(
                argparse.Namespace(
                    source=str(source), output=str(artifact), release_sha="a" * 40,
                    repository="Mohit0409/StyleDash", ci_run_id="123", ci_url="https://github.com/Mohit0409/StyleDash/actions/runs/123", created_at="2026-09-27T00:00:00Z", pull_request=[]
                )
            )
        finally:
            os.environ.clear(); os.environ.update(old)
        return artifact, home

    def test_artifact_is_allowlisted_checksumed_and_contains_exact_ci_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            artifact, home = self.build_artifact(Path(temporary))
            parsed = RUNNER.Artifact(artifact, home / ".local" / "share" / "styledash" / "deployments")
            stage = parsed.extract()
            self.assertEqual(parsed.metadata["releaseSha"], "a" * 40)
            self.assertEqual(parsed.metadata["ci"]["requiredCheck"], "StyleDash Required CI")
            self.assertTrue((stage / "payload" / "dist" / "assets" / "index-fixture.js").is_file())

    def test_secret_bearing_artifact_is_rejected_before_extraction(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifact = root / "unsafe.tar.gz"
            with tarfile.open(artifact, "w:gz") as archive:
                payload = root / ".env"
                payload.write_text("PRIVATE=bad\n", encoding="utf-8")
                archive.add(payload, "payload/.env")
            digest = self.sha(artifact)
            artifact.with_suffix(".gz.sha256").write_text(f"{digest}  unsafe.tar.gz\n", encoding="ascii")
            parsed = RUNNER.Artifact(artifact, root / "deployments")
            with self.assertRaisesRegex(RUNNER.DeployError, "forbidden"):
                parsed.extract()

    def make_deployment(self, root: Path) -> FixtureDeployment:
        artifact, home = self.build_artifact(root)
        FixtureDeployment.backup_calls = 0
        FixtureDeployment.mutation_calls = 0
        FixtureDeployment.fail_backup = False
        FixtureDeployment.fail_smoke = False
        return FixtureDeployment(artifact, home=home)

    def test_bootstrap_baseline_passes_and_preflight_never_starts_backup(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            deployment = self.make_deployment(Path(temporary))
            deployment.run(preflight_only=True)
            self.assertEqual(FixtureDeployment.backup_calls, 0)
            self.assertEqual(deployment.state["stage"], "PREFLIGHT_PASS")
            self.assertTrue(deployment.state["readyToBackup"])

    def test_altered_live_managed_file_fails_before_backup_or_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            deployment = self.make_deployment(Path(temporary))
            (deployment.home / "server" / "styledash_shops.py").write_text("drift\n", encoding="utf-8")
            with self.assertRaises(RUNNER.DeployError):
                deployment.run(preflight_only=True)
            self.assertEqual(FixtureDeployment.backup_calls, 0)
            self.assertEqual(FixtureDeployment.mutation_calls, 0)
            self.assertFalse(deployment.state["productionMutated"])

    def test_altered_staged_file_fails_before_backup(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            deployment = self.make_deployment(Path(temporary))
            deployment.initialize()
            assert deployment.stage
            (deployment.stage / "payload" / "scripts" / "styledash_shops.py").write_text("tampered\n", encoding="utf-8")
            with self.assertRaisesRegex(RUNNER.DeployError, "staged-file mismatch"):
                deployment.artifact.validate_extracted()
            self.assertEqual(FixtureDeployment.backup_calls, 0)

    def test_backup_failure_causes_no_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            deployment = self.make_deployment(Path(temporary))
            deployment.fail_backup = True
            with self.assertRaises(RUNNER.DeployError):
                deployment.run()
            self.assertEqual(FixtureDeployment.backup_calls, 1)
            self.assertEqual(FixtureDeployment.mutation_calls, 0)
            self.assertFalse(deployment.state["productionMutated"])

    def test_pass_writes_current_and_immutable_history_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            deployment = self.make_deployment(Path(temporary))
            deployment.run()
            manifest = deployment.deployments / "current.json"
            self.assertTrue(manifest.is_file())
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(payload["result"], "PASS")
            self.assertEqual(payload["deployedCommit"], "a" * 40)
            self.assertEqual(len(list(deployment.history_dir.glob("*.json"))), 1)
            self.assertEqual(FixtureDeployment.backup_calls, 1)

    def test_runtime_acceptance_failure_rolls_back_exact_prior_managed_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            deployment = self.make_deployment(Path(temporary))
            before = (deployment.home / "server" / "serve.py").read_bytes()
            deployment.fail_smoke = True
            with self.assertRaises(RUNNER.DeployError):
                deployment.run()
            self.assertEqual((deployment.home / "server" / "serve.py").read_bytes(), before)
            self.assertEqual(deployment.state["automaticRollback"], "PASS")
            self.assertFalse((deployment.home / "server" / "assets").is_symlink())

    def test_owner_wrapper_uses_git_archive_and_never_cleans_root_worktree(self) -> None:
        script = (ROOT / "ops" / "deploy-vibe4you.ps1").read_text(encoding="utf-8")
        self.assertIn("Invoke-Native git @('archive'", script)
        self.assertNotIn("git reset", script.lower())
        self.assertNotIn("git clean", script.lower())
        self.assertIn("merge-base --is-ancestor", script)
        self.assertIn("CI_NOT_GREEN", script)

    def test_detached_runner_and_sensitive_routes_are_explicit(self) -> None:
        shell = (ROOT / "scripts" / "termux" / "vibe-deploy").read_text(encoding="utf-8")
        runner = (ROOT / "scripts" / "termux" / "vibe_deploy.py").read_text(encoding="utf-8")
        self.assertIn("nohup setsid", shell)
        self.assertIn("EXISTING_TRANSACTION=YES", shell)
        for path in ("/backups", "/backups/deployment-probe", "/logs/deployment-probe", "/admin/", "/.env", "/secrets.env"):
            self.assertIn(path, runner)
        self.assertIn("CANONICAL_ORIGIN = \"https://vibe4you.in\"", runner)
        self.assertNotIn("styledash-public-url", runner)


if __name__ == "__main__":
    unittest.main()
