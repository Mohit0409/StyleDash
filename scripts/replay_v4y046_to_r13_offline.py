"""Offline replay of the original V4Y-046 -> V4Y-056 R13 patch release.

Inputs are already-compiled PUBLIC V4Y046 chunks/index (54 files), the
authentic historical R13 Python builder, and its patched backend code.
All inputs are SHA256-pinned; builder runs only in disposable OS temp.
All 56 release-code/config outputs and the generated candidate.sha256
are verified against the historical R13 release manifest; 54 storefront
code files must also match the pinned R13 input of our later R3 replay.

This does NOT generate the original V4Y046 compiled baseline from React.
It never calls a production host, deploys, or touches private state.
"""
from __future__ import annotations
from pathlib import Path,PurePosixPath
import hashlib,json,re,subprocess,sys,tempfile

ROOT=Path(__file__).resolve().parents[1]
CHAIN=ROOT/"deployment-snapshots/vibe4you-20261116-gst-r2/search-v2-replay"
ARCHIVE=CHAIN/"v4y046-to-r13"
PROOF=ARCHIVE/"replay-manifest.json"
R13_ROOT=CHAIN/"r13-to-r3/live-baseline"
PIN_PROOF_SHA="297f564e81338d9328950f33933de069f0af8517b8ea61a6451907d46976d5ac"
PIN_V4Y046_SHA="038dec55f34f8fdb1f80be5305fe7ad3488267cd87c3c7ea07a3e39065c3430b"
PIN_BUILDER_SHA="c9d7e2d4bde394c8611a3726e3b9a3d2d49520c88fde2ed83c9016ecd6263920"
PIN_BACKEND_SHA="776207b5903429ef51320ef678147964d762732d72ff8d8aef322bd85b9bf2cc"
PIN_R13_MANIFEST_SHA="dd97baecb6edb5f44b58704258f8815507f212117b9c044c9a8d0594311f00ac"
PIN_PRODUCTION_SHA="ec13b4f28f99b26f3cf468412d77a651b8596decc1cb5afb1012170bac11a126"


class V4Y046ReplayError(RuntimeError):
    pass

def sha(raw:bytes)->str:return hashlib.sha256(raw).hexdigest()

def path(rel:str)->Path:
    if not isinstance(rel,str) or not rel or ":" in rel or "\\" in rel:
        raise V4Y046ReplayError("Invalid archive path")
    p=PurePosixPath(rel)
    if p.is_absolute() or ".." in p.parts or p.as_posix()!=rel:
        raise V4Y046ReplayError("Invalid archive path")
    return Path(*p.parts)

def load()->dict:
    raw=PROOF.read_bytes()
    if sha(raw)!=PIN_PROOF_SHA:raise V4Y046ReplayError("V4Y046 replay proof changed")
    p=json.loads(raw)
    if (p.get("schema_version")!=1
        or p.get("production_integrity_manifest_sha256")!=PIN_PRODUCTION_SHA
        or p.get("v4y046_manifest_sha256")!=PIN_V4Y046_SHA
        or p.get("r13_builder_sha256")!=PIN_BUILDER_SHA
        or p.get("r13_backend_sha256")!=PIN_BACKEND_SHA
        or p.get("r13_full_candidate_manifest_sha256")!=PIN_R13_MANIFEST_SHA
        or len(p.get("v4y046_base_files",[]))!=54
        or len(p.get("r13_expected_files",{}))!=56
        or p.get("editable_react_source_to_v4y046_reproduced") is not False):
        raise V4Y046ReplayError("Unexpected compiled source baseline")
    return p

def verify_inputs()->dict:
    p=load()
    src=ARCHIVE/"live-baseline"
    input_manifest=(src/"manifest.sha256").read_bytes()
    if sha(input_manifest)!=PIN_V4Y046_SHA:
        raise V4Y046ReplayError("Input V4Y046 release manifest changed")
    manifest={}
    for line in input_manifest.decode("utf-8").splitlines():
        pieces=line.split(None,1)
        if len(pieces)!=2:continue
        manifest[pieces[1].replace("\\","/")]=pieces[0].lower()
    names=set()
    for item in p["v4y046_base_files"]:
        rel=item["path"]
        if rel in names:
            raise V4Y046ReplayError("Duplicate public V4Y046 source")
        names.add(rel)
        if rel!="index.html" and not re.fullmatch(
            r"assets/[A-Za-z0-9_.-]+-v4y046-category-social-r1\.js",rel
        ):
            raise V4Y046ReplayError("Non-V4Y046 input included")
        path_to_source=src/path(rel)
        if path_to_source.is_symlink() or not path_to_source.is_file():
            raise V4Y046ReplayError("V4Y046 code source missing or link")
        raw=path_to_source.read_bytes()
        if sha(raw)!=item["sha256"] or manifest.get("server/"+rel)!=item["sha256"]:
            raise V4Y046ReplayError("V4Y046 code mismatch: "+rel)
    disk={p.relative_to(src).as_posix() for p in src.rglob("*")
          if p.is_file() and p.name!="manifest.sha256"}
    if names!=disk or len(names)!=54:raise V4Y046ReplayError("Unexpected code files")
    backend=ARCHIVE/"patched-backend/serve.py"
    builder=ARCHIVE/"tools/build_v4y056_storefront_hardening.py"
    if sha(backend.read_bytes())!=PIN_BACKEND_SHA or sha(builder.read_bytes())!=PIN_BUILDER_SHA:
        raise V4Y046ReplayError("Builder/backend code mismatch")
    return p

def replay()->dict:
    p=verify_inputs()
    with tempfile.TemporaryDirectory(prefix="v4y046-r13-compiled-replay-") as temp:
        temp=Path(temp)
        stage=temp/"inputs"
        (stage/"assets").mkdir(parents=True)
        (temp/"tools").mkdir()
        base=ARCHIVE/"live-baseline"
        (stage/"manifest.sha256").write_bytes((base/"manifest.sha256").read_bytes())
        for row in p["v4y046_base_files"]:
            name=row["path"]
            source=base/path(name)
            target=stage/path(name)
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(source.read_bytes())
        builder=temp/"tools"/"build_v4y056_storefront_hardening.py"
        backend=temp/"patched-serve.py"
        builder.write_bytes((ARCHIVE/"tools"/builder.name).read_bytes())
        backend.write_bytes((ARCHIVE/"patched-backend/serve.py").read_bytes())
        out=temp/"r13-candidate"
        run=subprocess.run([
            sys.executable,"-I","-B",str(builder),
            "--live-baseline",str(stage),
            "--patched-backend",str(backend),
            "--output",str(out)],
            cwd=temp,capture_output=True,text=True,timeout=50)
        if run.returncode:
            raise V4Y046ReplayError("Original R13 builder error: "+run.stderr[-380:])
        expected=p["r13_expected_files"]
        actual={file.relative_to(out).as_posix()
                for file in out.rglob("*") if file.is_file()}
        if actual!=set(expected)|{"candidate.sha256"}:
            raise V4Y046ReplayError("R13 output files unexpectedly missing/extra")
        for name,digest in expected.items():
            content=(out/path(name)).read_bytes()
            if sha(content)!=digest:
                raise V4Y046ReplayError("Wrong R13 output bytes: "+name)
            if name=="server/index.html" or name.startswith("server/assets/"):
                archived=(R13_ROOT/path(name.removeprefix("server/"))).read_bytes()
                if content!=archived:
                    raise V4Y046ReplayError("R13 output differs from later canonical replay")
        if sha((out/"candidate.sha256").read_bytes())!=PIN_R13_MANIFEST_SHA:
            raise V4Y046ReplayError("R13 SHA manifest not exactly reproduced")
        return {
            "v4y046_compiled_inputs":54,
            "r13_verified_code_config_outputs":len(expected),
            "r13_stored_candidate_sha256_reproduced":True,
            "r13_storefront_inputs_for_r3_replay":54,
            "editable_react_source_to_v4y046_reproduced":False,
        }

if __name__=="__main__":
    try:print("OFFLINE_V4Y046_TO_R13_REPLAY_PASS",json.dumps(replay(),sort_keys=True))
    except (V4Y046ReplayError,OSError,KeyError,TypeError,ValueError,subprocess.TimeoutExpired) as err:
        print("V4Y046_R13_REPLAY_STOP",str(err),file=sys.stderr);sys.exit(1)
