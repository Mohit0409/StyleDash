"""Verify V4Y-046 editable-source provenance and optional build comparison."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "deployment-snapshots/vibe4you-20261116-gst-r2"
PROOF = SNAPSHOT / "v4y046-editable-source-provenance.json"
ARCHIVE = SNAPSHOT / "search-v2-replay/v4y046-to-r13"
BASELINE = ARCHIVE / "live-baseline"
REPLAY_MANIFEST = ARCHIVE / "replay-manifest.json"
PIN_PROOF_SHA = "9bf57447542f49b3da353d25b4bffd79f8a7222162ac8b193e2b94df8b8bb668"
PIN_CATEGORIES_SHA = "a5f564d834fb28ec21e17f8fbf5a2fc06761341d84f350eee43a9631d983abb8"
PIN_SOURCE_COMMIT = "748ac8a60e1665bd7dbd4261ef1816423a5ad342"
EXPECTED_DIFFERENT = {
    "Categories", "Checkout", "ProductDetail", "Profile", "StoreDetail",
    "Stores", "VendorOnboarding", "categories", "index", "paymentApi",
}


class ProvenanceError(RuntimeError):
    pass


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def path(rel: str) -> Path:
    if not isinstance(rel, str) or not rel or ":" in rel or "\\" in rel:
        raise ProvenanceError("Invalid proof path")
    value = PurePosixPath(rel)
    if value.is_absolute() or ".." in value.parts or value.as_posix() != rel:
        raise ProvenanceError("Invalid proof path")
    return Path(*value.parts)


def load_proof() -> dict:
    raw = PROOF.read_bytes()
    if sha(raw) != PIN_PROOF_SHA:
        raise ProvenanceError("V4Y046 editable-source proof changed")
    proof = json.loads(raw)
    if (
        proof.get("schema_version") != 1
        or proof.get("exact_editable_source_to_v4y046_reproduced") is not False
        or proof.get("source_candidate", {}).get("commit") != PIN_SOURCE_COMMIT
        or proof.get("v4y046_comparison", {}).get(
            "filename_and_newline_normalized_equal_modules"
        ) != 43
        or set(proof.get("v4y046_comparison", {}).get("different_modules", []))
        != EXPECTED_DIFFERENT
    ):
        raise ProvenanceError("Unexpected V4Y046 source classification")
    return proof


def module_name(filename: str, compiled: bool) -> str:
    suffix = "-v4y046-category-social-r1.js" if compiled else ".js"
    if not filename.endswith(suffix):
        raise ProvenanceError("Unexpected JavaScript filename")
    stem = filename[: -len(suffix)]
    match = re.fullmatch(r"(.+)-[A-Za-z0-9_-]{8}", stem)
    if not match:
        raise ProvenanceError("Cannot classify JavaScript chunk: " + filename)
    return match.group(1)


def normalized(raw: bytes, names: dict[str, str]) -> bytes:
    value = raw.replace(b"\r\n", b"\n")
    for filename, label in sorted(names.items(), key=lambda item: -len(item[0])):
        value = value.replace(filename.encode(), f"@{{{label}}}.js".encode())
    return value


def verify_baseline() -> tuple[dict, dict[str, Path]]:
    proof = load_proof()
    replay = json.loads(REPLAY_MANIFEST.read_text(encoding="utf-8"))
    rows = replay.get("v4y046_base_files", [])
    if len(rows) != 54:
        raise ProvenanceError("Unexpected V4Y046 replay inventory")
    files: dict[str, Path] = {}
    for row in rows:
        rel = row.get("path")
        file = BASELINE / path(rel)
        if file.is_symlink() or not file.is_file() or sha(file.read_bytes()) != row.get("sha256"):
            raise ProvenanceError("V4Y046 baseline mismatch: " + str(rel))
        if rel.endswith(".js"):
            name = module_name(file.name, True)
            if name in files:
                raise ProvenanceError("Duplicate V4Y046 module: " + name)
            files[name] = file
    if len(files) != 53:
        raise ProvenanceError("Expected 53 V4Y046 JavaScript modules")
    categories = files.get("Categories")
    raw = categories.read_bytes() if categories else b""
    if len(raw) != 5080 or sha(raw) != PIN_CATEGORIES_SHA:
        raise ProvenanceError("Pinned V4Y046 Categories module changed")
    for marker in (b"V4Y_PH", b"V4Y_Pick", b"V4Y_Thumb"):
        if marker not in raw:
            raise ProvenanceError("V4Y046 Categories marker missing")
    return proof, files


def compare_candidate(candidate_assets: Path) -> dict[str, object]:
    _, baseline = verify_baseline()
    candidate_assets = candidate_assets.resolve(strict=True)
    if candidate_assets.is_symlink() or not candidate_assets.is_dir():
        raise ProvenanceError("Candidate assets must be a real directory")
    candidate: dict[str, Path] = {}
    for file in sorted(candidate_assets.glob("*.js")):
        if file.is_symlink():
            raise ProvenanceError("Candidate asset links are not allowed")
        name = module_name(file.name, False)
        if name in candidate:
            raise ProvenanceError("Duplicate candidate module: " + name)
        candidate[name] = file
    if len(candidate) != 54:
        raise ProvenanceError(f"Expected 54 candidate modules, found {len(candidate)}")
    common = set(candidate) & set(baseline)
    candidate_only = set(candidate) - set(baseline)
    if len(common) != 53 or candidate_only != {"storeRating"}:
        raise ProvenanceError("Unexpected source-build module graph")
    candidate_names = {file.name: name for name, file in candidate.items()}
    baseline_names = {file.name: name for name, file in baseline.items()}
    equal = {
        name for name in common
        if normalized(candidate[name].read_bytes(), candidate_names)
        == normalized(baseline[name].read_bytes(), baseline_names)
    }
    different = common - equal
    if len(equal) != 43 or different != EXPECTED_DIFFERENT:
        raise ProvenanceError("Candidate comparison differs from pinned classification")
    return {
        "candidate_javascript_chunks": 54,
        "common_modules": 53,
        "normalized_equal_modules": 43,
        "candidate_only_modules": ["storeRating"],
        "different_modules": sorted(different),
        "exact_editable_source_to_v4y046_reproduced": False,
    }


def verify(candidate_assets: Path | None = None) -> dict[str, object]:
    _, baseline = verify_baseline()
    result: dict[str, object] = {
        "v4y046_javascript_chunks": len(baseline),
        "source_commit": PIN_SOURCE_COMMIT,
        "exact_editable_source_to_v4y046_reproduced": False,
    }
    if candidate_assets is not None:
        result.update(compare_candidate(candidate_assets))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-assets", type=Path)
    args = parser.parse_args()
    try:
        result = verify(args.candidate_assets)
    except (ProvenanceError, OSError, KeyError, TypeError, ValueError) as error:
        print("V4Y046_SOURCE_PROVENANCE_STOP", str(error), file=sys.stderr)
        return 1
    print("OFFLINE_V4Y046_SOURCE_PROVENANCE_PASS", json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
