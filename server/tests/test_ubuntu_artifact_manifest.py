from __future__ import annotations
from pathlib import Path
import hashlib
import os
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "ubuntu" / "reseal-vibe4you-artifact-manifest"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_manifest(root: Path, relatives: list[str]) -> Path:
    manifest_dir = root / ".migration"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest = manifest_dir / "artifact-files-remediated.sha256"
    lines = [f"{sha256(root / relative)}  {relative}" for relative in relatives]
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return manifest


class UbuntuArtifactManifestResealTests(unittest.TestCase):
    def run_helper(self, root: Path, *relatives: str) -> subprocess.CompletedProcess:
        env = os.environ.copy()
        env["VIBE4YOU_APP_ROOT"] = str(root)
        return subprocess.run(
            ["bash", str(SCRIPT), *relatives],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
        )
    def make_tree(self, base: Path) -> None:
        (base / "server" / "assets").mkdir(parents=True)
        (base / "server" / "index.html").write_text("old-index", encoding="utf-8")
        (base / "server" / "serve.py").write_text("stable-runtime", encoding="utf-8")

    def test_reseals_existing_index_and_preserves_rollback_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_tree(root)
            manifest = write_manifest(root, ["server/index.html", "server/serve.py"])
            before = manifest.read_text(encoding="utf-8")

            (root / "server" / "index.html").write_text("new-index", encoding="utf-8")
            result = self.run_helper(root, "server/index.html")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("ARTIFACT_MANIFEST_RESEAL=PASS", result.stdout)
            self.assertIn(
                f"{sha256(root / 'server' / 'index.html')}  server/index.html",
                manifest.read_text(encoding="utf-8"),
            )
            backups = list(manifest.parent.glob(manifest.name + ".before-reseal-*"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_text(encoding="utf-8"), before)
    def test_allows_new_frontend_asset_and_verifies_whole_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_tree(root)
            manifest = write_manifest(root, ["server/index.html", "server/serve.py"])
            asset = root / "server" / "assets" / "iphone-image-compat-119.js"
            asset.write_text("compat", encoding="utf-8")

            result = self.run_helper(root, "server/assets/iphone-image-compat-119.js")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(
                f"{sha256(asset)}  server/assets/iphone-image-compat-119.js",
                manifest.read_text(encoding="utf-8"),
            )

    def test_refuses_reseal_when_unrelated_manifest_entry_is_changed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_tree(root)
            manifest = write_manifest(root, ["server/index.html", "server/serve.py"])
            before = manifest.read_bytes()
            (root / "server" / "index.html").write_text("new-index", encoding="utf-8")
            (root / "server" / "serve.py").write_text("unexpected-runtime-change", encoding="utf-8")

            result = self.run_helper(root, "server/index.html")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unrelated manifest entries do not match", result.stderr)
            self.assertEqual(manifest.read_bytes(), before)
            self.assertEqual(
                list(manifest.parent.glob(manifest.name + ".before-reseal-*")),
                [],
            )
    def test_refuses_runtime_file_as_reseal_target(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_tree(root)
            manifest = write_manifest(root, ["server/index.html", "server/serve.py"])
            before = manifest.read_bytes()

            result = self.run_helper(root, "server/serve.py")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("not approved for frontend manifest reseal", result.stderr)
            self.assertEqual(manifest.read_bytes(), before)

    def test_refuses_path_traversal(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_tree(root)
            write_manifest(root, ["server/index.html", "server/serve.py"])

            result = self.run_helper(root, "server/assets/../serve.py")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Unsafe manifest path", result.stderr)


if __name__ == "__main__":
    unittest.main()
