"""Build the pinned editable predecessor of compiled V4Y-046, offline only.

This is a forensic build helper. It does not claim exact V4Y-046 parity and
must be pointed at a disposable, clean checkout of the pinned source commit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
PIN_COMMIT = "748ac8a60e1665bd7dbd4261ef1816423a5ad342"
PUBLIC_BUNDLE = ROOT / (
    "deployment-snapshots/vibe4you-20261116-gst-r2/search-v2-replay/"
    "v4y046-to-r13/live-baseline/assets/"
    "firebaseClient-B8Q2FPL--v4y046-category-social-r1.js"
)
PIN_PUBLIC_BUNDLE_SHA = (
    "fca013771821dcce3e937d4f36ef398e63e59c26d424070e4ee876e0569ed627"
)
PIN_BLOBS = {
    "package.json": (1836, "246c1c5c21d6aacadf9bf9914ad583b0df04f5fbbd70806c2b7276784f59c53a"),
    "package-lock.json": (204293, "113d0f674625d98fed0bf4fd63fcd85a3e936e02d8a6aaab322ec8193ee8d313"),
    "vite.config.ts": (363, "227bb65ab9848b9cec4e2f48ea44ada6729d34df7dc87e60fc139782e79a356f"),
    "src/pages/Categories.tsx": (4297, "6aca3b0716e349db9cadb2dd238e9198877aa5f9969fdde1ece9d87cb4e96c5d"),
    "src/pages/Checkout.tsx": (17329, "fd545544119d40990b774f6b20747d4de8fcd1e5ac8f936654730c1fdd1104b5"),
    "src/pages/StoreDetail.tsx": (6143, "a9eaebd9b89cbec1ae8fc4e411ea059459590efb29ea3ecf722c5a81d2730460"),
    "src/pages/Stores.tsx": (8119, "bbeb614cab93c9aa8e854386d8967228c80b278447449d929e053d04b9649d4e"),
    "src/services/paymentApi.ts": (9248, "30cfb7e5192525923b074c31f6f2b3de98d523dd68ff2a02b45d93b154e89f1e"),
    "src/utils/storeRating.ts": (594, "f427b71ec413ce7331b1578cc81346a5790648e6f3f323bdd8b79b3104e906c5"),
}
PUBLIC_FIELDS = {
    "apiKey": "VITE_FIREBASE_API_KEY",
    "authDomain": "VITE_FIREBASE_AUTH_DOMAIN",
    "projectId": "VITE_FIREBASE_PROJECT_ID",
    "appId": "VITE_FIREBASE_APP_ID",
}
DENIED_ENV_MARKERS = (
    "RAZORPAY", "SMTP", "SESSION_SECRET", "TOTP", "STYLEDASH",
    "PASSWORD", "PRIVATE_KEY", "TOKEN",
)


class SourceBuildError(RuntimeError):
    pass


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def run(args: list[str], cwd: Path, env: dict[str, str] | None = None) -> str:
    completed = subprocess.run(
        args, cwd=cwd, env=env, capture_output=True, text=True, timeout=300
    )
    if completed.returncode:
        detail = (completed.stderr or completed.stdout)[-800:]
        raise SourceBuildError(f"Command failed ({args[0]}): {detail}")
    return completed.stdout.strip()


def verify_source_tree(source_tree: Path) -> None:
    if source_tree.is_symlink() or not source_tree.is_dir():
        raise SourceBuildError("Source tree must be a real directory")
    if source_tree == ROOT or ROOT in source_tree.parents:
        raise SourceBuildError("Use a disposable checkout outside this sync repository")
    git = ["git", "-c", f"safe.directory={source_tree.as_posix()}"]
    head = run(git + ["rev-parse", "HEAD"], source_tree)
    if head != PIN_COMMIT:
        raise SourceBuildError("Source tree is not the pinned source commit")
    if run(git + ["status", "--porcelain", "--untracked-files=no"], source_tree):
        raise SourceBuildError("Tracked source files must be clean before the forensic build")
    for name, (size, digest) in PIN_BLOBS.items():
        raw = subprocess.run(
            git + ["show", f"HEAD:{name}"], cwd=source_tree,
            capture_output=True, timeout=30, check=True,
        ).stdout
        if len(raw) != size or sha(raw) != digest:
            raise SourceBuildError(f"Pinned Git blob changed: {name}")


def build_environment() -> dict[str, str]:
    raw = PUBLIC_BUNDLE.read_bytes()
    if sha(raw) != PIN_PUBLIC_BUNDLE_SHA:
        raise SourceBuildError("Pinned public Firebase bundle changed")
    text = raw.decode("utf-8")
    public: dict[str, str] = {}
    for field, env_name in PUBLIC_FIELDS.items():
        match = re.search(rf'{field}:"([^"\\]+)"', text)
        if not match:
            raise SourceBuildError(f"Public field missing from pinned bundle: {field}")
        public[env_name] = match.group(1)
    clean = {
        key: value for key, value in os.environ.items()
        if not key.upper().startswith("VITE_")
        and not any(marker in key.upper() for marker in DENIED_ENV_MARKERS)
    }
    clean.update(public)
    return clean


def build(source_tree: Path, skip_install: bool) -> dict[str, object]:
    source_tree = source_tree.resolve(strict=True)
    verify_source_tree(source_tree)
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if not npm:
        raise SourceBuildError("npm executable not found")
    env = build_environment()
    if not skip_install:
        run([npm, "ci", "--offline", "--ignore-scripts"], source_tree, env)
    run([npm, "run", "build"], source_tree, env)
    assets = source_tree / "dist/assets"
    chunks = sorted(assets.glob("*.js")) if assets.is_dir() else []
    if len(chunks) != 54:
        raise SourceBuildError(f"Expected 54 JavaScript chunks, found {len(chunks)}")
    return {
        "source_commit": PIN_COMMIT,
        "javascript_chunks": len(chunks),
        "network_used": False,
        "production_contacted": False,
        "exact_editable_source_to_v4y046_reproduced": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-tree", required=True, type=Path)
    parser.add_argument("--skip-install", action="store_true")
    args = parser.parse_args()
    try:
        result = build(args.source_tree, args.skip_install)
    except (SourceBuildError, OSError, subprocess.SubprocessError) as error:
        print("V4Y046_SOURCE_BUILD_STOP", str(error), file=sys.stderr)
        return 1
    print("OFFLINE_V4Y046_SOURCE_BUILD_PASS", json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
