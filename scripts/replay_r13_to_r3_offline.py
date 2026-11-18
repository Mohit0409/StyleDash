"""Offline replay of the historical V4Y-056 R13 -> V4Y-055 R3 patch.

Inputs: SHA-256-pinned public COMPILED R13 homepage and 53 JS chunks,
archived original builder Python, public Android assetlinks.
Output: only disposable OS-temp R3 candidate; verify all 56 release
outputs by hash, including SHA256SUMS and Digital Asset Links.
No network, production writes, repo mutation, secrets or customer data.

Limitation: this proves the compiled R13 -> R3 patch transformation,
NOT how editable React source originally generated the R13 baseline.
"""
from __future__ import annotations
import hashlib,json,re,subprocess,sys,tempfile
from pathlib import Path,PurePosixPath

ROOT=Path(__file__).resolve().parents[1]
CHAIN=ROOT/"deployment-snapshots/vibe4you-20261116-gst-r2/search-v2-replay"
R3=CHAIN/"r13-to-r3"
PROOF=R3/"replay-manifest.json"
PIN_PROOF="fa340064c75a99a5c5d939a314db3eaf16fd123c4a209de87f47ab1b9e904d9b"
PIN_R13_MANIFEST="dd97baecb6edb5f44b58704258f8815507f212117b9c044c9a8d0594311f00ac"
PIN_BUILDER="d1e4c885c45f77682827db609c2f6c3ea53626995a30900ff4f7d4a6e07b0617"
PIN_ASSETLINKS="eefc6823c917a4529e36d8deeddb757aad10b0bb2f84fe9f8d32406836ed10a4"
PIN_PRODUCTION="ec13b4f28f99b26f3cf468412d77a651b8596decc1cb5afb1012170bac11a126"


class R13ReplayError(RuntimeError):
    pass


def sha(raw:bytes)->str:
    return hashlib.sha256(raw).hexdigest()


def safe_rel(rel:str)->Path:
    if not isinstance(rel,str) or not rel or "\\" in rel or ":" in rel:
        raise R13ReplayError("Unsafe archive path")
    p=PurePosixPath(rel)
    if p.is_absolute() or ".." in p.parts or p.as_posix()!=rel:
        raise R13ReplayError("Unsafe archive path")
    return Path(*p.parts)


def read_proof()->dict:
    raw=PROOF.read_bytes()
    if sha(raw)!=PIN_PROOF:raise R13ReplayError("Pinned R13-R3 proof SHA mismatch")
    p=json.loads(raw)
    if (p.get("schema_version")!=1
        or p.get("production_integrity_manifest_sha256")!=PIN_PRODUCTION
        or p.get("r13_sha_manifest_sha256")!=PIN_R13_MANIFEST
        or p.get("builder_sha256")!=PIN_BUILDER
        or p.get("assetlinks_sha256")!=PIN_ASSETLINKS
        or p.get("r13_expected_files")!=54
        or len(p.get("r3_expected_files",{}))!=56
        or p.get("editable_react_source_to_r13_reproduced") is not False):
        raise R13ReplayError("Wrong production or artifact baseline")
    return p


def verified_inputs()->tuple[dict,dict]:
    proof=read_proof()
    baseline=R3/"live-baseline"
    pin=(baseline/"r13-candidate.sha256").read_bytes()
    if sha(pin)!=PIN_R13_MANIFEST:
        raise R13ReplayError("R13 full release SHA manifest changed")
    rows={}
    for line in pin.decode("utf-8").splitlines():
        if not re.fullmatch(r"[0-9a-f]{64}  [a-zA-Z0-9_./-]+",line):
            raise R13ReplayError("Unrecognized full R13 manifest row")
        digest,path=line.split("  ",1)
        if path=="server/index.html" or re.fullmatch(r"server/assets/[A-Za-z0-9_.-]+-v4y056-storefront-hardening-r4\.js",path):
            if path in rows:raise R13ReplayError("Duplicate R13 file")
            rows[path]=digest
    if len(rows)!=54 or "server/index.html" not in rows:
        raise R13ReplayError("Incomplete R13 compiled public baseline")
    actual=set()
    for target,digest in rows.items():
        rel=target.removeprefix("server/")
        path=baseline/safe_rel(rel)
        if not path.is_file() or path.is_symlink() or sha(path.read_bytes())!=digest:
            raise R13ReplayError("R13 input bytes differ: "+rel)
        actual.add(rel)
    disk={p.relative_to(baseline).as_posix()
          for p in baseline.rglob("*") if p.is_file()
          and p.name!="r13-candidate.sha256"}
    if disk!=actual:
        raise R13ReplayError("Extra or missing R13 code files")
    if sha((R3/"tools/build_candidate.py").read_bytes())!=PIN_BUILDER:
        raise R13ReplayError("Original R3 builder changed")
    if sha((R3/"assetlinks.json").read_bytes())!=PIN_ASSETLINKS:
        raise R13ReplayError("R3 public Digital Asset Links source changed")
    return proof,rows


def replay()->dict:
    proof,rows=verified_inputs()
    r3base=CHAIN/"base-v4y055-r3"
    with tempfile.TemporaryDirectory(prefix="v4y-r13-r3-replay-") as temp:
        stage=Path(temp)/"release"
        (stage/"tools").mkdir(parents=True)
        (stage/"live-baseline/assets").mkdir(parents=True)
        (stage/"tools/build_candidate.py").write_bytes(
            (R3/"tools/build_candidate.py").read_bytes())
        (stage/"assetlinks.json").write_bytes((R3/"assetlinks.json").read_bytes())
        (stage/"live-baseline/r13-candidate.sha256").write_bytes(
            (R3/"live-baseline/r13-candidate.sha256").read_bytes())
        for target in rows:
            rel=target.removeprefix("server/")
            src=R3/"live-baseline"/rel
            out=stage/"live-baseline"/safe_rel(rel)
            out.parent.mkdir(parents=True,exist_ok=True)
            out.write_bytes(src.read_bytes())
        process=subprocess.run(
            [sys.executable,"-I","-B",str(stage/"tools/build_candidate.py")],
            cwd=stage,capture_output=True,text=True,timeout=45)
        if process.returncode:
            raise R13ReplayError("Historical R3 builder failed: "+process.stderr[-350:])
        candidate=stage/"candidate"
        wanted=proof["r3_expected_files"]
        found={p.relative_to(candidate).as_posix() for p in candidate.rglob("*") if p.is_file()}
        if found!=set(wanted):raise R13ReplayError("R3 output names incomplete or unexpected")
        for rel,row in wanted.items():
            output=candidate/safe_rel(rel)
            data=output.read_bytes()
            if len(data)!=row["size_bytes"] or sha(data)!=row["sha256"]:
                raise R13ReplayError("R3 release mismatch: "+rel)
            if rel not in ("assetlinks.json","SHA256SUMS"):
                archival=(r3base/safe_rel(rel)).read_bytes()
                if archival!=data:raise R13ReplayError("R3 canonical archived release mismatch: "+rel)
        return {
            "r13_compiled_input_files":len(rows),
            "r3_verified_release_files":len(wanted),
            "r3_compiled_public_assets_matching_later_search_baseline":len(wanted)-2,
            "r13_compiled_source_recreated_from_editable_react":False,
        }


if __name__=="__main__":
    try:print("OFFLINE_R13_TO_R3_REPLAY_PASS",json.dumps(replay(),sort_keys=True))
    except (R13ReplayError,OSError,ValueError,KeyError,TypeError,subprocess.TimeoutExpired) as err:
        print("R13_R3_REPLAY_STOP",str(err),file=sys.stderr)
        sys.exit(1)
