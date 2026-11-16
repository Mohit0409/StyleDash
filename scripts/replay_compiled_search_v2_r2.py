"""OFFLINE Search V2 -> Relevance R2 compiled release replay.

Rebuilds BOTH search bridges from editable TypeScript sources with pinned
esbuild v0.21.5 and replays the two historical compiled JS patch scripts
against a SHA-verified, public compiled V4Y-055 R3 baseline.

Strictly verifies all 54 intermediate outputs and all 54 final Search V2
R2 release outputs by SHA-256; the final files are also compared against
the byte-exact ACTIVE public frontend snapshot captured from production.

IMPORTANT: this is a reproducible *compiled-overlay transformation*,
not a reproducible frontend build from editable React source alone.
No production access, GitHub changes or customer data. No deploy actions.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CAPTURE = ROOT / "deployment-snapshots/vibe4you-20261116-gst-r2"
CHAIN = CAPTURE / "search-v2-replay"
INPUTS = CHAIN / "replay-inputs.json"
PRODUCTION = CAPTURE / "frontend-runtime/site"
PIN_INPUTS_SHA = "78b3bedece2837ff2bf4535637b0c7f26406e450e7d9bf17686c2c802c9b08d1"
PIN_LIVE_MANIFEST = "ec13b4f28f99b26f3cf468412d77a651b8596decc1cb5afb1012170bac11a126"
PIN_R2_BRIDGE = "d0421675026e4e474001f0d9b8037871c1175892dc3e0fa417f200bb73b68794"
PIN_V1_BRIDGE = "d4e13df00eea428e12e3040d2940a2577b9ec50dfb0c9c1a89b3adcd3a338b42"
TAG_R3 = "-v4y055-r3.js"
TAG_V1 = "-v4y-search-v2.js"
TAG_R2 = "-v4y-search-v2-r2.js"
MAIN_BASE = "index-MMTPd8z_-v4y055-r3.js"
PRODUCTS_BASE = "Products-DSTsw2bW-v4y055-r3.js"


class ReplayError(RuntimeError):
    pass


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def check_rel(path: str) -> Path:
    p = PurePosixPath(path)
    if (
        not path or p.is_absolute() or ".." in p.parts or "\\" in path
        or ":" in path or p.as_posix() != path
        or len(path) > 200
    ):
        raise ReplayError("Unsafe input or output relative path")
    return Path(*p.parts)


def from_pin(path: Path, sha: str, size: int) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ReplayError("Missing/non-file pinned public source")
    data = path.read_bytes()
    if digest(data) != sha or len(data) != size:
        raise ReplayError("Pinned input byte/length mismatch: " + path.name)
    return data


def manifest() -> dict:
    raw = INPUTS.read_bytes()
    if digest(raw) != PIN_INPUTS_SHA:
        raise ReplayError("Replay input manifest changed")
    m = json.loads(raw)
    if (
        m.get("schema_version") != 1
        or m.get("production_integrity_manifest_sha256") != PIN_LIVE_MANIFEST
        or len(m.get("base_files", [])) != 54
        or len(m.get("v1_search_bridge_source_files", [])) != 4
        or len(m.get("expected_step1", [])) != 54
        or len(m.get("expected_step2", [])) != 54
    ):
        raise ReplayError("Unexpected baseline / file count")
    return m


def verify_inputs(m: dict) -> None:
    seen = set()
    for row in m["base_files"]:
        rel = row["path"]
        if rel in seen or not rel.startswith(("assets/", "index.html")):
            raise ReplayError("Base source path outside allowlist")
        seen.add(rel)
        from_pin(CHAIN / "base-v4y055-r3" / check_rel(rel),
                 row["sha256"], row["size_bytes"])
    if len(seen) != 54 or "index.html" not in seen:
        raise ReplayError("Incomplete compiled R3 base")
    for row in m["v1_search_bridge_source_files"]:
        from_pin(CHAIN / "v1-bridge" / check_rel(row["path"]),
                 row["sha256"], row["size_bytes"])
    row = m["r2_search_bridge_source"]
    if row["path"] != "scripts/relevance-r2-runtime-bridge.ts":
        raise ReplayError("Unreviewed V2 bridge source")
    from_pin(ROOT / row["path"], row["sha256"], row["size_bytes"])


def write_exact(directory: Path, rel: str, content: bytes) -> None:
    path = directory / check_rel(rel)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def expected_files(directory: Path, expected: list[dict], label: str) -> None:
    wanted = set()
    for row in expected:
        rel = check_rel(row["path"])
        if row["path"] in wanted:
            raise ReplayError(label + ": duplicate target")
        wanted.add(row["path"])
        data = (directory / rel).read_bytes()
        if digest(data) != row["sha256"] or len(data) != row["size_bytes"]:
            raise ReplayError(label + " mismatch: " + row["path"])
    actual = {p.relative_to(directory).as_posix()
              for p in directory.rglob("*") if p.is_file()}
    if wanted != actual:
        raise ReplayError(label + ": unexpected/missing output paths")


def replace_one(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise ReplayError(label + ": expected one patch anchor, got " + str(count))
    return text.replace(old, new)


def esbuild_binary() -> str:
    name = "esbuild.cmd" if os.name == "nt" else "esbuild"
    binary = ROOT / "node_modules" / ".bin" / name
    if not binary.is_file():
        raise ReplayError("Run npm ci in isolated source worktree first")
    check = subprocess.run([str(binary), "--version"], capture_output=True,
                           text=True, timeout=15)
    if check.returncode or check.stdout.strip() != "0.21.5":
        raise ReplayError("Pinned esbuild 0.21.5 is required")
    return str(binary)


def compile_bridge(entry: Path, output: Path, esbuild: str) -> bytes:
    proc = subprocess.run(
        [esbuild, str(entry), "--bundle", "--minify", "--format=iife",
         "--platform=browser", "--target=es2020", "--outfile=" + str(output)],
        capture_output=True, text=True, timeout=25)
    if proc.returncode:
        raise ReplayError("Bridge TypeScript compilation failed: " + proc.stderr[-300:])
    return output.read_bytes()


def archive_read_text(path: Path) -> str:
    """Match Path.read_text() universal-newline conversion in 2026 build scripts."""
    return path.read_bytes().decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")


def step1(base: Path, out: Path, v1_bridge: bytes) -> None:
    old = sorted((base / "assets").glob("*" + TAG_R3))
    if len(old) != 53:
        raise ReplayError("Expected 53 R3 compiled modules")
    for p in old:
        text = p.read_bytes().decode("utf-8")
        write_exact(out, "assets/" + p.name.replace(TAG_R3, TAG_V1),
                    text.replace(TAG_R3, TAG_V1).encode("utf-8"))
    main = out / "assets" / MAIN_BASE.replace(TAG_R3, TAG_V1)
    source = archive_read_text(main)
    start = ",Cv=(e,t,n,r=10)=>{"
    end = ",_v=(e,t)=>"
    i = source.find(start)
    j = source.find(end, i + len(start))
    if i < 0 or j < 0:
        raise ReplayError("R3 compiled search suggestion patch anchors changed")
    previous = source[i:j]
    if not all(value in previous for value in
               ("product:", "store:", "category:", "brand:")):
        raise ReplayError("Unexpected R3 autocomplete implementation")
    source = (
        source[:i]
        + ",Cv=(e,t,n,r=10)=>globalThis.__V4Y_SEARCH_V2__.buildSearchSuggestions(e,t,n,r)"
        + source[j:])
    source = v1_bridge.decode("utf-8").strip() + "\n" + source
    main.write_bytes(source.encode("utf-8"))

    product = out / "assets" / PRODUCTS_BASE.replace(TAG_R3, TAG_V1)
    text = archive_read_text(product)
    start = "ce=(a,r)=>{"
    end = ",L=(a,r)=>"
    i = text.find(start)
    j = text.find(end, i + len(start))
    if i < 0 or j < 0 or "a.name.toLocaleLowerCase()" not in text[i:j]:
        raise ReplayError("R3 product filter compiled anchor changed")
    text = (text[:i]
            + "ce=(a,r)=>!r.trim()||globalThis.__V4Y_SEARCH_V2__.scoreProductSearch(a,r)!==null"
            + text[j:])
    old_store = (
        "C=s?d.filter(t=>{const n=s.toLowerCase();return[t.storeName,t.category,"
        "t.description,t.address,t.city].some(u=>u==null?void 0:u.toLowerCase().includes(n))}):[]"
    )
    new_store = "C=s?d.filter(t=>globalThis.__V4Y_SEARCH_V2__.scoreStoreSearch(t,s)!==null):[]"
    text = replace_one(text, old_store, new_store, "Store search")
    text = replace_one(
        text, ",k=[...V].sort((t,n)=>",
        ",__V4Y_search_scores=s?new Map(V.map(t=>[t,globalThis.__V4Y_SEARCH_V2__.scoreProductSearch(t,s)||0])):null,k=[...V].sort((t,n)=>",
        "Search scores")
    text = replace_one(
        text,
        ':p==="discount"?n.discount-t.discount:0),U=se(k,24,"page",!b,"catalogue-products")',
        ':p==="discount"?n.discount-t.discount:__V4Y_search_scores?(__V4Y_search_scores.get(n)||0)-(__V4Y_search_scores.get(t)||0):0),U=se(k,24,"page",!b,"catalogue-products")',
        "Recommended relevance sort")
    if 'U=se(k,24,"page",!b,"catalogue-products")' not in text:
        raise ReplayError("Search patch unexpectedly changed pagination")
    product.write_bytes(text.encode("utf-8"))
    index = archive_read_text(base / "index.html")
    result = index.replace(TAG_R3, TAG_V1)
    if result == index or result.count("/assets/" + MAIN_BASE.replace(TAG_R3, TAG_V1)) != 1:
        raise ReplayError("Search v1 homepage entrypoint patch failed")
    write_exact(out, "index.html", result.encode("utf-8"))


def step2(step1_dir: Path, out: Path, r2_bridge: bytes) -> None:
    old = sorted((step1_dir / "assets").glob("*" + TAG_V1))
    if len(old) != 53:
        raise ReplayError("Expected 53 compiled Search V1 modules")
    for p in old:
        text = archive_read_text(p)
        write_exact(out, "assets/" + p.name.replace(TAG_V1, TAG_R2),
                    text.replace(TAG_V1, TAG_R2).encode("utf-8"))
    main = out / "assets" / MAIN_BASE.replace(TAG_R3, TAG_R2)
    text = archive_read_text(main)
    boundary = text.find("const __vite__mapDeps")
    if not (4000 < boundary < 10000):
        raise ReplayError("Compiled R2 JS bridge boundary absent")
    if "__V4Y_SEARCH_V2__" not in text[:boundary]:
        raise ReplayError("V1 bridge not present in R2 base")
    text = r2_bridge.decode("utf-8").strip() + "\n" + text[boundary:]
    main.write_bytes(text.encode("utf-8"))

    products = out / "assets" / PRODUCTS_BASE.replace(TAG_R3, TAG_R2)
    text = archive_read_text(products)
    text = replace_one(
        text,
        "xe=(a,r)=>M(a.filter(l=>z(l,r,{ignoreBrand:!0})).map(l=>l.brand))",
        "xe=(a,r)=>globalThis.__V4Y_SEARCH_V2__.canonicalBrandOptions(a.filter(l=>z(l,r,{ignoreBrand:!0})).map(l=>l.brand))",
        "Canonical brand facet")
    text = replace_one(
        text, 'h!=="all"&&!D.includes(h)',
        'h!=="all"&&!D.some(t=>t.toLocaleLowerCase()===h.toLocaleLowerCase())',
        "Case-insensitive brand filter")
    text = replace_one(
        text, "brand:h,setBrand",
        "brand:D.find(t=>t.toLocaleLowerCase()===h.toLocaleLowerCase())||h,setBrand",
        "Selected brand label")
    if '__V4Y_search_scores' not in text:
        raise ReplayError("R2 scores disappeared")
    products.write_bytes(text.encode("utf-8"))

    source_index = archive_read_text(step1_dir / "index.html")
    from_name = "/assets/" + MAIN_BASE.replace(TAG_R3, TAG_V1)
    to_name = "/assets/" + MAIN_BASE.replace(TAG_R3, TAG_R2)
    result = replace_one(source_index, from_name, to_name, "Search R2 homepage entry")
    write_exact(out, "index.html", result.encode("utf-8"))


def replay() -> dict:
    m = manifest()
    verify_inputs(m)
    esbuild = esbuild_binary()
    with tempfile.TemporaryDirectory(prefix="v4y-compiled-search-replay-") as tmp:
        work = Path(tmp)
        v1 = compile_bridge(
            CHAIN / "v1-bridge/qa/search-v2-runtime-bridge.ts",
            work / "bridge-v1.js", esbuild)
        r2 = compile_bridge(
            ROOT / "scripts/relevance-r2-runtime-bridge.ts",
            work / "bridge-r2.js", esbuild)
        if digest(v1) != m["expected_v1_bridge_minified_sha256"] or digest(v1) != PIN_V1_BRIDGE:
            raise ReplayError("Rebuilt V1 search bridge diverged")
        if digest(r2) != PIN_R2_BRIDGE or digest(r2) != m["expected_v2_bridge_minified_sha256"]:
            raise ReplayError("Rebuilt R2 relevance bridge diverged")
        b = CHAIN / "base-v4y055-r3"
        one = work / "step1"
        two = work / "step2"
        step1(b, one, v1)
        expected_files(one, m["expected_step1"], "Search V1 compiled release")
        step2(one, two, r2)
        expected_files(two, m["expected_step2"], "Search R2 compiled release")
        for row in m["expected_step2"]:
            deployed = PRODUCTION / row["path"]
            live = deployed.read_bytes()
            if digest(live) != row["sha256"] or len(live) != row["size_bytes"]:
                raise ReplayError("Final Search R2 bytes differ from pinned live: " + row["path"])
        return {
            "esbuild": "0.21.5",
            "v1_bridge_from_ts":True,
            "r2_bridge_from_ts":True,
            "historical_compiled_r3_base":54,
            "v1_release_rebuilt":len(m["expected_step1"]),
            "r2_release_rebuilt":len(m["expected_step2"]),
            "r2_matches_pinned_live_frontend":True,
            "editable_react_source_to_base_r3_reproduced":False,
        }


if __name__ == "__main__":
    try:
        print("OFFLINE_COMPILED_SEARCH_R2_REPLAY_PASS", json.dumps(replay(), sort_keys=True))
    except (OSError, KeyError, ValueError, TypeError, subprocess.TimeoutExpired, ReplayError) as exc:
        print("COMPILED_SEARCH_R2_REPLAY_STOP",str(exc),file=sys.stderr)
        raise SystemExit(1) from None
