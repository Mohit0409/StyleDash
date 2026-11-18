"""Offline, fail-closed assembly for *selected* Vibe4You production code.

NOT a deployer. Does not connect to Ubuntu, touch app state, or build frontend.
Only exact code files pinned in the 2026-11-16 source map may be checked or
assembled into a NEW directory within the operating system temp folder.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
MAP = ROOT / "deployment-targets/vibe4you-20261116-r2/source-map.json"
CAPTURED = ROOT / "deployment-snapshots/vibe4you-20261116-gst-r2/code-manifest.json"
MAP_SHA256 = "4139830b332f68dd137461b7622caa12d812a38c2042ab93c67ea4b5db9966e1"
CAPTURED_SHA256 = "6b057c361ce35a5ee59bac065cd7240bcefcfa2f083c5c90702f3b29bffb2dfd"
LIVE_MANIFEST_SHA256 = "ec13b4f28f99b26f3cf468412d77a651b8596decc1cb5afb1012170bac11a126"
GST_REGISTRY_SHA256 = "3244c8adf4d387474462b3ab9a3d1aa6884ad2fdba30ffcbc37c427d7f824c3f"


class PinnedSourceError(RuntimeError):
    pass


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_repo_source(source: str) -> Path:
    pp = PurePosixPath(source)
    if (
        not source or pp.is_absolute() or ".." in pp.parts
        or str(pp) != source or "\\" in source or ":" in source
    ):
        raise PinnedSourceError("Unsafe source path")
    allowed_prefix = (
        "scripts/",
        "server/admin/",
        "public/",
        "deployment-targets/vibe4you-20261116-r2/targets/",
    )
    if not source.startswith(allowed_prefix):
        raise PinnedSourceError("Source is not in allowlisted source areas")
    path = (ROOT / source).resolve(strict=True)
    if not path.is_relative_to(ROOT.resolve()):
        raise PinnedSourceError("Symlink escapes repository")
    if not path.is_file():
        raise PinnedSourceError("Not a regular source file")
    return path


def safe_target(target: str) -> Path:
    pp = PurePosixPath(target)
    if (
        not target or pp.is_absolute() or ".." in pp.parts
        or str(pp) != target or "\\" in target or ":" in target
        or pp.parts[0] not in ("admin", "server")
        or len(pp.parts) < 2
        or pp.suffix not in (".py", ".html", ".css", ".js", ".json")
    ):
        raise PinnedSourceError("Target not allowlisted code path")
    return Path(*pp.parts)


def validate() -> tuple[list[tuple[Path, Path, str]], dict]:
    raw_map = MAP.read_bytes()
    if digest(raw_map) != MAP_SHA256:
        raise PinnedSourceError("Source map pinned hash changed")
    raw_capture = CAPTURED.read_bytes()
    if digest(raw_capture) != CAPTURED_SHA256:
        raise PinnedSourceError("Pinned production snapshot changed")
    mapping = json.loads(raw_map)
    snapshot = json.loads(raw_capture)
    if (
        mapping.get("schema_version") != 1
        or mapping.get("source_of_truth_manifest_sha256") != LIVE_MANIFEST_SHA256
        or snapshot.get("production_manifest_sha256") != LIVE_MANIFEST_SHA256
        or mapping.get("generated_exclusions") != ["server/index.html"]
    ):
        raise PinnedSourceError("Wrong production baseline or generated exclusions")
    expected = {row["path"]: row["sha256"] for row in snapshot["code_files"]}
    if len(expected) != 59:
        raise PinnedSourceError("Expected 59 unique code manifest paths")
    expected.pop("server/index.html")
    for target in ("admin/gst_phase1_registry.py", "server/gst_phase1_registry.py"):
        expected[target] = GST_REGISTRY_SHA256
    entries = mapping.get("verified_targets", [])
    if not isinstance(entries, list) or len(entries) != 60:
        raise PinnedSourceError("Expected exactly 60 backend/static target records")
    checked = []
    targets = set()
    override_count = 0
    for entry in entries:
        name = entry["target"]
        safe = safe_target(name)
        if name in targets or name not in expected:
            raise PinnedSourceError("Duplicate or extra target")
        targets.add(name)
        source = entry["source"]
        actual_sha = entry["sha256"]
        if actual_sha != expected[name]:
            raise PinnedSourceError("Target SHA differs from pinned live production")
        if source.startswith("deployment-targets/"):
            if source != "deployment-targets/vibe4you-20261116-r2/targets/" + name:
                raise PinnedSourceError("Target-specific mapping mismatch")
            override_count += 1
        if name in ("admin/gst_phase1_registry.py", "server/gst_phase1_registry.py"):
            if source != "scripts/gst_phase1_registry.py":
                raise PinnedSourceError("GST registry cannot be substituted")
        path = safe_repo_source(source)
        if digest(path.read_bytes()) != actual_sha:
            raise PinnedSourceError("Source byte SHA mismatch for target " + name)
        checked.append((safe, path, actual_sha))
    if targets != set(expected) or override_count != 16:
        raise PinnedSourceError("Target coverage or override count differs from pinned plan")
    return checked, mapping


def assemble_temp(output: Path) -> None:
    entries, _ = validate()
    root_temp = Path(tempfile.gettempdir()).resolve()
    resolved = output.resolve()
    if (
        not resolved.is_relative_to(root_temp)
        or resolved == root_temp
        or resolved.is_relative_to(ROOT.resolve())
        or output.exists()
        or output.is_symlink()
        or not output.parent.is_dir()
    ):
        raise PinnedSourceError("Output must be a new directory under system temp")
    output.mkdir(mode=0o700)
    try:
        for target, source, sha in entries:
            dest = output / target
            dest.parent.mkdir(parents=True, exist_ok=True)
            data = source.read_bytes()
            if digest(data) != sha:
                raise PinnedSourceError("Source changed during staging")
            dest.write_bytes(data)
            if digest(dest.read_bytes()) != sha:
                raise PinnedSourceError("Staged bytes changed")
        if len([x for x in output.rglob("*") if x.is_file()]) != 60:
            raise PinnedSourceError("Unexpected file count")
    except Exception:
        shutil.rmtree(output)
        raise
    print("OFFLINE_SOURCE_BUNDLE_PASS count=60 output=" + str(output))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="No writes, validate source hashes only")
    parser.add_argument("--output", type=Path, help="New directory strictly under OS temp")
    opts = parser.parse_args(argv)
    if opts.output and opts.check:
        parser.error("Select --check or --output, not both")
    try:
        if opts.output:
            assemble_temp(opts.output)
        else:
            entries, _ = validate()
            print("OFFLINE_PINNED_TARGET_SOURCES_PASS files=" + str(len(entries))
                  + " distinct_admin_public_overrides=16 generated_homepage_excluded=yes")
    except (OSError, KeyError, ValueError, PinnedSourceError) as exc:
        print("PINNED_SOURCE_CHECK_STOP " + str(exc), file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
