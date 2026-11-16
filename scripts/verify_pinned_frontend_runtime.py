"""Verify the pinned Vibe4You public frontend runtime capsule (OFFLINE).

This is an integrity check on *deployed public artifacts*, not a
React/Vite build or a production deployment capability. No writes/network.
"""
from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
import hashlib
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
CAPSULE = ROOT / "deployment-snapshots/vibe4you-20261116-gst-r2/frontend-runtime"
MANIFEST = CAPSULE / "asset-manifest.json"
SITE = CAPSULE / "site"
PINNED_MANIFEST_SHA256 = "a32a2fa9130a53abd16709bc6b2018e72011c8c29c01b78a25727d61a86b36aa"
PINNED_PROD_SHA256 = "ec13b4f28f99b26f3cf468412d77a651b8596decc1cb5afb1012170bac11a126"
ALLOWED_EXTENSIONS = {".js", ".css", ".json", ".svg", ".png", ".jpg", ".jpeg", ".webp", ".html"}
PWA_EXTRA = {
    "server/sw.js",
    "server/vibe4you-app/icons/icon-192.png",
    "server/vibe4you-app/icons/icon-512.png",
    "server/vibe4you-app/icons/icon-maskable-512.png",
}


class FrontendCapsuleError(RuntimeError):
    pass


def hash_data(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def clean_target_path(target: str) -> Path:
    if not isinstance(target, str):
        raise FrontendCapsuleError("Target is not text")
    p = PurePosixPath(target)
    if (not target.startswith("server/") or p.is_absolute() or ".." in p.parts
        or "\\" in target or ":" in target or len(target)>210
        or p.suffix not in ALLOWED_EXTENSIONS or len(p.parts)>5
        or p.parts[1] not in ("assets", "vibe4you-app","favicon.svg","index.html","sw.js")
        or p.as_posix()!=target):
        raise FrontendCapsuleError("Non-public or unsafe target path")
    return Path(*p.parts[1:])


def check_file(row: dict, site_root: Path = SITE) -> None:
    rel = clean_target_path(row["target"])
    expected = row["sha256"]
    actual_path = site_root / rel
    if actual_path.is_symlink() or not actual_path.is_file():
        raise FrontendCapsuleError("Snapshot file absent or symlink: "+str(rel))
    data = actual_path.read_bytes()
    if hash_data(data)!=expected or len(data)!=row["size_bytes"]:
        raise FrontendCapsuleError("Public asset byte/hash mismatch: "+str(rel))


class HomeReferences(HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs=set()
    def handle_starttag(self, tag, attrs):
        props=dict(attrs)
        if tag=="script" and props.get("src"):
            self.refs.add("server/"+props["src"].lstrip("/"))
        if tag=="link" and props.get("href"):
            rel=props.get("rel")
            if rel in ("stylesheet","manifest","apple-touch-icon","icon"):
                self.refs.add("server/"+props["href"].lstrip("/"))


def verify() -> dict:
    raw=MANIFEST.read_bytes()
    if hash_data(raw)!=PINNED_MANIFEST_SHA256:
        raise FrontendCapsuleError("Frontend capsule manifest has changed")
    meta=json.loads(raw)
    if (meta.get("schema_version")!=1
        or meta.get("production_integrity_manifest_sha256")!=PINNED_PROD_SHA256
        or len(meta.get("files",[]))!=133):
        raise FrontendCapsuleError("Wrong public runtime baseline")
    paths=set()
    pinned=0
    pwa_derived=set()
    potential=set()
    direct=set()
    for row in meta["files"]:
        path=row["target"]
        if path in paths:
            raise FrontendCapsuleError("Duplicate target")
        paths.add(path)
        check_file(row)
        if row["production_integrity_manifest"]:
            pinned+=1
            if row["provenance"]!="pinned_live_integrity_manifest":
                raise FrontendCapsuleError("Manifest provenance inconsistent")
        elif row["provenance"]!="live_readonly_sftp_and_http_sha256":
            raise FrontendCapsuleError("Unmanifested provenance inconsistent")
        if row["direct_index_link"]:direct.add(path)
        if row["potential_vite_asset_dependency"]:potential.add(path)
        if row["pwa_derived"]:pwa_derived.add(path)
    if pinned!=123 or len(paths)!=133 or len(potential)!=123 or pwa_derived!=PWA_EXTRA:
        raise FrontendCapsuleError("Unexpected file/asset coverage")
    if "server/index.html" not in paths or "server/assets/index-MMTPd8z_-v4y-search-v2-r2.js" not in paths:
        raise FrontendCapsuleError("Missing active Search V2 R2 entrypoint")
    on_disk={"server/"+p.relative_to(SITE).as_posix()
             for p in SITE.rglob("*") if p.is_file()}
    if on_disk!=paths:
        raise FrontendCapsuleError("Unexpected/missing file in public capsule")
    parser=HomeReferences()
    parser.feed((SITE/"index.html").read_text(encoding="utf-8"))
    if parser.refs!=direct or len(direct)!=21:
        raise FrontendCapsuleError("Current homepage links do not match pinned captures")
    pwa=json.loads((SITE/"vibe4you-app/manifest.json").read_text(encoding="utf-8"))
    icon_set={"server/"+str(icon["src"]).lstrip("/") for icon in pwa.get("icons",[])}
    if icon_set!=PWA_EXTRA-{"server/sw.js"}:
        raise FrontendCapsuleError("PWA icon references changed")
    installer=(SITE/"vibe4you-app/pwa-install.js").read_text("utf-8")
    if "/sw.js" not in installer:
        raise FrontendCapsuleError("PWA registration path changed")
    return {"files":133,"pinned":pinned,"unmanifested":133-pinned,
            "index_direct_refs":len(direct),"potential_vite_assets":len(potential)}


if __name__=="__main__":
    try:
        result=verify()
        print("V4Y_OFFLINE_FRONTEND_RUNTIME_INTEGRITY_PASS",json.dumps(result,sort_keys=True))
        print("FRONTEND_IS_DEPLOYED_ARTIFACT_SNAPSHOT_NOT_EDITABLE_SOURCE=yes")
    except (FrontendCapsuleError,OSError,KeyError,ValueError,TypeError) as exc:
        print("FRONTEND_SNAPSHOT_CHECK_STOP",str(exc),file=sys.stderr)
        raise SystemExit(1) from None
