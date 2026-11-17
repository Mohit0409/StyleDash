"""Validate or stage the pinned Vibe4You public overlay/PWA layer OFFLINE.

This is not a React build and not a deployer. It has no network or production
write capability. It only validates repository-local, byte-pinned public
artifacts and may copy them to a NEW directory under the operating-system
temporary directory.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import verify_pinned_frontend_runtime as runtime

MAP = ROOT / "deployment-targets/vibe4you-20261116-r2/frontend-overlay-source-map.json"
MAP_SHA256 = "7ef85f1890ce0d69fa742d0495bd29e401f6aea9d52d4919c066135ae89fa1ea"
CAPSULE_PREFIX = "deployment-snapshots/vibe4you-20261116-gst-r2/frontend-runtime/site/"
EXPECTED_KINDS = {
    "authored-standalone-overlay": 14,
    "compiled-vite-css-reference": 2,
    "reproducible-static-pwa": 9,
}
PWA_TARGETS = {
    "server/sw.js",
    "server/vibe4you-app/icons/apple-touch-icon.png",
    "server/vibe4you-app/icons/icon-192.png",
    "server/vibe4you-app/icons/icon-512.png",
    "server/vibe4you-app/icons/icon-maskable-512.png",
    "server/vibe4you-app/manifest.json",
    "server/vibe4you-app/offline.html",
    "server/vibe4you-app/pwa-install.css",
    "server/vibe4you-app/pwa-install.js",
}


class FrontendOverlayError(RuntimeError):
    pass


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_target(target: str) -> Path:
    if not isinstance(target, str):
        raise FrontendOverlayError("Target is not text")
    pp = PurePosixPath(target)
    allowed = (
        target.startswith("server/assets/")
        or target == "server/sw.js"
        or target.startswith("server/vibe4you-app/")
    )
    if (
        not allowed or pp.is_absolute() or ".." in pp.parts
        or pp.as_posix() != target or "\\" in target or ":" in target
        or len(pp.parts) > 5 or pp.suffix not in runtime.ALLOWED_EXTENSIONS
    ):
        raise FrontendOverlayError("Target is not an allowlisted public path")
    return Path(*pp.parts)


def safe_source(source: str, target: str) -> Path:
    expected = CAPSULE_PREFIX + target.removeprefix("server/")
    if source != expected:
        raise FrontendOverlayError("Source is not the target's pinned capsule path")
    pp = PurePosixPath(source)
    if pp.is_absolute() or ".." in pp.parts or pp.as_posix() != source or "\\" in source:
        raise FrontendOverlayError("Unsafe source path")
    path = (ROOT / source).resolve(strict=True)
    if not path.is_relative_to(ROOT.resolve()) or path.is_symlink() or not path.is_file():
        raise FrontendOverlayError("Source escapes repository or is not a regular file")
    return path


def check_source_file(row: dict, source: Path) -> None:
    data = source.read_bytes()
    if digest(data) != row["sha256"] or len(data) != row["size_bytes"]:
        raise FrontendOverlayError("Source byte/hash mismatch for " + row["target"])


def validate() -> tuple[list[tuple[Path, Path, str]], dict]:
    capsule_result = runtime.verify()
    if capsule_result != {
        "files": 134,
        "pinned": 123,
        "unmanifested": 11,
        "index_direct_refs": 21,
        "potential_vite_assets": 123,
    }:
        raise FrontendOverlayError("Wrong verified frontend capsule baseline")
    raw = MAP.read_bytes()
    if digest(raw) != MAP_SHA256:
        raise FrontendOverlayError("Frontend overlay source map pinned hash changed")
    mapping = json.loads(raw)
    if (
        mapping.get("schema_version") != 1
        or mapping.get("frontend_capsule_manifest_sha256") != runtime.PINNED_MANIFEST_SHA256
        or mapping.get("production_integrity_manifest_sha256") != runtime.PINNED_PROD_SHA256
        or mapping.get("exact_react_integration") is not False
        or mapping.get("expected_kind_counts") != EXPECTED_KINDS
    ):
        raise FrontendOverlayError("Wrong overlay baseline or source classification")
    entries = mapping.get("files")
    if not isinstance(entries, list) or len(entries) != 25:
        raise FrontendOverlayError("Expected exactly 25 overlay/CSS/PWA records")
    capsule = json.loads(runtime.MANIFEST.read_text("utf-8"))
    captured = {row["target"]: row for row in capsule["files"]}
    checked = []
    targets = set()
    kinds = Counter()
    for row in entries:
        target = row["target"]
        safe = safe_target(target)
        if target in targets or target not in captured:
            raise FrontendOverlayError("Duplicate or uncaptured overlay target")
        targets.add(target)
        kind = row["kind"]
        kinds[kind] += 1
        if kind not in EXPECTED_KINDS:
            raise FrontendOverlayError("Unknown overlay source classification")
        live = captured[target]
        for key in ("sha256", "size_bytes", "production_integrity_manifest", "direct_index_link"):
            if row[key] != live[key]:
                raise FrontendOverlayError("Source map differs from capsule for " + target)
        source = safe_source(row["source"], target)
        check_source_file(row, source)
        if kind == "authored-standalone-overlay":
            if not target.startswith("server/assets/") or safe.suffix not in (".js", ".css"):
                raise FrontendOverlayError("Standalone overlay classification escaped assets")
        elif kind == "compiled-vite-css-reference":
            if not target.startswith("server/assets/") or safe.suffix != ".css":
                raise FrontendOverlayError("Compiled CSS classification is inconsistent")
        elif target not in PWA_TARGETS:
            raise FrontendOverlayError("PWA classification includes a non-PWA target")
        checked.append((safe, source, row["sha256"]))
    if dict(kinds) != EXPECTED_KINDS:
        raise FrontendOverlayError("Overlay source classification counts changed")
    actual_pwa = {row["target"] for row in entries if row["kind"] == "reproducible-static-pwa"}
    if actual_pwa != PWA_TARGETS:
        raise FrontendOverlayError("PWA output graph changed")
    if "server/index.html" in targets or any("index-MMTPd8z_" in item for item in targets):
        raise FrontendOverlayError("Generated homepage/main bundle must stay outside overlay assembly")
    return checked, mapping


def assemble_temp(output: Path) -> None:
    entries, _ = validate()
    temp_root = Path(tempfile.gettempdir()).resolve()
    resolved = output.resolve()
    if (
        not resolved.is_relative_to(temp_root) or resolved == temp_root
        or resolved.is_relative_to(ROOT.resolve()) or output.exists()
        or output.is_symlink() or not output.parent.is_dir()
    ):
        raise FrontendOverlayError("Output must be a new directory under system temp")
    output.mkdir(mode=0o700)
    try:
        for target, source, sha in entries:
            destination = output / target
            destination.parent.mkdir(parents=True, exist_ok=True)
            data = source.read_bytes()
            if digest(data) != sha:
                raise FrontendOverlayError("Source changed during staging")
            destination.write_bytes(data)
            if digest(destination.read_bytes()) != sha:
                raise FrontendOverlayError("Staged bytes changed")
        if len([item for item in output.rglob("*") if item.is_file()]) != 25:
            raise FrontendOverlayError("Unexpected staged file count")
    except Exception:
        shutil.rmtree(output)
        raise
    print("OFFLINE_FRONTEND_OVERLAY_BUNDLE_PASS files=25 exact_react_integration=no output=" + str(output))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate pinned sources without writes")
    parser.add_argument("--output", type=Path, help="New directory strictly under OS temp")
    options = parser.parse_args(argv)
    if options.check and options.output:
        parser.error("Select --check or --output, not both")
    try:
        if options.output:
            assemble_temp(options.output)
        else:
            entries, _ = validate()
            print(
                "OFFLINE_PINNED_FRONTEND_OVERLAYS_PASS files=" + str(len(entries))
                + " authored_overlays=14 compiled_css_refs=2 pwa_outputs=9 exact_react_integration=no"
            )
    except (OSError, KeyError, ValueError, TypeError, FrontendOverlayError, runtime.FrontendCapsuleError) as exc:
        print("FRONTEND_OVERLAY_CHECK_STOP " + str(exc), file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
