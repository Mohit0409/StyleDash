"""Verify Search V2 R2 editable source and its intermediate Vite build.

Offline only. 11 recovered TypeScript/TSX source files are pinned. Optional
--dist checks 61 archived prepatch built files plus 5 extra public assets.
This is NOT verification of the final live Search V2 R2 postprocessed bundle.
"""
from pathlib import Path, PurePosixPath
import hashlib,json,sys,argparse

ROOT=Path(__file__).resolve().parents[1]
PROOF=ROOT/"deployment-snapshots/vibe4you-20261116-gst-r2/search-v2-source-build-proof.json"
PROOF_SHA256="967ada203370fc6803e1a9de90647f9f1c5670325e0e48192c149f9dbca4a586"
LIVE_MANIFEST_SHA256="ec13b4f28f99b26f3cf468412d77a651b8596decc1cb5afb1012170bac11a126"


class SearchSourceError(RuntimeError):
    pass


def sha(data:bytes)->str:
    return hashlib.sha256(data).hexdigest()


def safe_path(path:str)->Path:
    p=PurePosixPath(path)
    if (not isinstance(path,str) or p.is_absolute() or ".." in p.parts
        or "\\" in path or ":" in path or p.as_posix()!=path):
        raise SearchSourceError("Unsafe source path")
    return Path(*p.parts)


def read_proof()->dict:
    raw=PROOF.read_bytes()
    if sha(raw)!=PROOF_SHA256:raise SearchSourceError("Pinned source/build proof changed")
    proof=json.loads(raw)
    if (proof.get("schema_version")!=1
        or proof.get("production_integrity_manifest_sha256")!=LIVE_MANIFEST_SHA256
        or len(proof.get("recovered_source_files",[]))!=11
        or len(proof.get("source_build_reproduced_files",[]))!=61
        or len(proof.get("additional_recovered_public_files",[]))!=5
        or len(proof.get("archived_final_release_payload_matches_live",[]))!=3):
        raise SearchSourceError("Unexpected source/build baseline")
    return proof


def verify_source()->dict:
    proof=read_proof()
    names=set()
    for row in proof["recovered_source_files"]:
        name=row["path"]
        if name in names or not name.startswith("src/") or not name.endswith((".ts",".tsx")):
            raise SearchSourceError("Bad source record")
        names.add(name)
        p=(ROOT/safe_path(name)).resolve(strict=True)
        if not p.is_relative_to(ROOT.resolve()) or p.is_symlink():
            raise SearchSourceError("Source escapes Git worktree")
        if sha(p.read_bytes())!=row["sha256"]:
            raise SearchSourceError("Editable source hash mismatch: "+name)
    return {"source_files":len(names),"archived_build_files":61,"extra_public_files":5}


def verify_dist()->dict:
    info=verify_source()
    proof=read_proof()
    dist=ROOT/"dist"
    if not dist.is_dir():
        raise SearchSourceError("Vite dist is not present; run npx vite build")
    combined=proof["source_build_reproduced_files"]+proof["additional_recovered_public_files"]
    expected={}
    for row in combined:
        p=safe_path(row["path"])
        if row["path"] in expected:
            raise SearchSourceError("Duplicate build file")
        expected[row["path"]]=row["sha256"]
        source=(dist/p).resolve(strict=True)
        if not source.is_relative_to(dist.resolve()):
            raise SearchSourceError("Build file escapes dist")
        if sha(source.read_bytes())!=row["sha256"]:
            raise SearchSourceError("Vite intermediate build hash mismatch: "+row["path"])
    actual={p.relative_to(dist).as_posix() for p in dist.rglob("*") if p.is_file()}
    if actual!=set(expected):
        raise SearchSourceError("Build contains unexpected/missing generated files")
    return {**info,"exact_intermediate_vite_build_files":len(actual),
            "final_live_bundle_reproduced":False}


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist",action="store_true",
                        help="Check a previously generated local Vite dist/ too")
    args=parser.parse_args()
    try:
        result=verify_dist() if args.dist else verify_source()
        print("OFFLINE_SEARCH_V2_EDITABLE_SOURCE_PASS",json.dumps(result,sort_keys=True))
    except (SearchSourceError,OSError,ValueError,KeyError,TypeError) as err:
        print("OFFLINE_SEARCH_R2_SOURCE_STOP",str(err),file=sys.stderr)
        raise SystemExit(1) from None
