#!/usr/bin/env python3
"""Build the deterministic, allowlisted Vibe4You deployment-v2 artifact."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import tarfile
import re
from pathlib import Path, PurePosixPath


PROCEDURE_VERSION = 2
FILE_TARGETS = {
    "scripts/termux-spa-server.py": [("server/serve.py", 0o755)],
    "scripts/termux-admin-server.py": [("admin/serve.py", 0o600)],
    "scripts/styledash_admin.py": [("admin/styledash_admin.py", 0o600)],
    "scripts/styledash_security.py": [
        ("server/styledash_security.py", 0o600),
        ("admin/styledash_security.py", 0o600),
    ],
    "scripts/styledash_reviews.py": [
        ("server/styledash_reviews.py", 0o600),
        ("admin/styledash_reviews.py", 0o600),
    ],
    "scripts/styledash_delivery_zone.py": [
        ("server/styledash_delivery_zone.py", 0o600),
        ("admin/styledash_delivery_zone.py", 0o600),
    ],
    "scripts/styledash_delivery_zone_store.py": [
        ("server/styledash_delivery_zone_store.py", 0o600),
        ("admin/styledash_delivery_zone_store.py", 0o600),
    ],
    "scripts/styledash_mail.py": [("server/styledash_mail.py", 0o600)],
    "scripts/styledash_notify.py": [
        ("server/styledash_notify.py", 0o600),
        ("admin/styledash_notify.py", 0o600),
    ],
    "scripts/styledash_firebase.py": [("server/styledash_firebase.py", 0o600)],
    "scripts/receipt_pdf.py": [("server/receipt_pdf.py", 0o600)],
    "scripts/catalog_normalization.py": [
        ("server/catalog_normalization.py", 0o600),
        ("admin/catalog_normalization.py", 0o600),
    ],
    "scripts/styledash_shops.py": [
        ("server/styledash_shops.py", 0o600),
        ("admin/styledash_shops.py", 0o600),
    ],
    "scripts/termux/backup-styledash-data": [("bin/backup-styledash-data", 0o755)],
    "scripts/termux/start-styledash-cloudflare": [("bin/start-styledash-cloudflare", 0o700)],
    "scripts/termux/start-styledash": [("bin/start-styledash", 0o700)],
    "scripts/termux/start-styledash-admin": [("bin/start-styledash-admin", 0o700)],
    "scripts/termux/start-styledash-stack": [("bin/start-styledash-stack", 0o700)],
    "scripts/termux/start-styledash-ngrok": [("bin/start-styledash-ngrok", 0o700)],
    "scripts/termux/start-styledash-tunnel": [("bin/start-styledash-tunnel", 0o700)],
    "scripts/termux/start-styledash-cloudflare-rollback": [("bin/start-styledash-cloudflare-rollback", 0o700)],
    "scripts/termux/stop-styledash-ngrok": [("bin/stop-styledash-ngrok", 0o700)],
    "scripts/termux/boot-start-styledash": [(".termux/boot/start-styledash", 0o700)],
    "scripts/termux/styledash-health": [("bin/styledash-health", 0o700)],
    "scripts/termux/backup-styledash-recovery": [("bin/backup-styledash-recovery", 0o700)],
    "scripts/termux/styledash-notify": [("bin/styledash-notify", 0o700)],
    "scripts/termux/verify-styledash-processes": [("bin/verify-styledash-processes", 0o700)],
    "scripts/termux/styledash-process-lib": [("bin/styledash-process-lib", 0o755)],
    "scripts/termux/vibe-deploy": [("bin/vibe-deploy", 0o700)],
    "scripts/termux/vibe_deploy.py": [("bin/vibe_deploy.py", 0o600)],
}
EXTRA_FILES = ("ops/deployment-v2-bootstrap.json",)
FRONTEND_TOP_LEVEL = {
    "index.html",
    "favicon.svg",
    "manifest.json",
    "product-placeholder.svg",
    "robots.txt",
}
SECRET_VALUE_PATTERNS = (
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(rb"gh[pousr]_[A-Za-z0-9_]{30,}"),
    re.compile(rb"AKIA[0-9A-Z]{16}"),
    re.compile(
        rb"(?im)^\s*(?:export\s+)?(?:RAZORPAY_(?:LIVE|TEST)_(?:KEY_SECRET|WEBHOOK_SECRET)|SMTP_PASSWORD|STYLEDASH_TOTP_ENCRYPTION_KEY)\s*=\s*[^$\s#\"']"
    ),
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def reject_secret_material(name: str, data: bytes) -> None:
    if any(pattern.search(data) for pattern in SECRET_VALUE_PATTERNS):
        raise SystemExit(f"release secret scan failed: {name}")


def frontend_files(source: Path) -> list[Path]:
    dist = source / "dist"
    if not dist.is_dir():
        raise SystemExit("production dist/ is missing; build the exact release SHA first")
    top_files = {path.name for path in dist.iterdir() if path.is_file()}
    top_dirs = {path.name for path in dist.iterdir() if path.is_dir()}
    if top_files != FRONTEND_TOP_LEVEL or top_dirs != {"assets"}:
        raise SystemExit("dist/ contains an unexpected production layout")
    files = sorted(path for path in dist.rglob("*") if path.is_file())
    if not files or not any(path.suffix == ".js" for path in files):
        raise SystemExit("dist/ has no JavaScript assets")
    return files


def tree_manifest(root: Path, files: list[Path]) -> tuple[list[dict[str, object]], str]:
    entries: list[dict[str, object]] = []
    digest_lines: list[str] = []
    for path in files:
        relative = path.relative_to(root).as_posix()
        digest = sha256_file(path)
        entries.append({"path": relative, "sha256": digest, "size": path.stat().st_size})
        digest_lines.append(f"{digest}  {relative}\n")
    tree_hash = hashlib.sha256("".join(digest_lines).encode("utf-8")).hexdigest()
    return entries, tree_hash


def validate_public_config(source: Path) -> dict[str, str]:
    firebase_project = os.environ.get("VITE_FIREBASE_PROJECT_ID", "").strip()
    firebase_fields = {
        "apiKey": os.environ.get("VITE_FIREBASE_API_KEY", "").strip(),
        "authDomain": os.environ.get("VITE_FIREBASE_AUTH_DOMAIN", "").strip(),
        "projectId": firebase_project,
        "appId": os.environ.get("VITE_FIREBASE_APP_ID", "").strip(),
    }
    if any(not value or value.startswith("replace_") or value.startswith("your-") for value in firebase_fields.values()):
        raise SystemExit("complete production VITE_FIREBASE_* values are required")
    bundle = b"\n".join(path.read_bytes() for path in frontend_files(source) if path.suffix == ".js")
    for value in firebase_fields.values():
        if value.encode("utf-8") not in bundle:
            raise SystemExit("built frontend does not contain the expected Firebase public configuration")
    google_id = os.environ.get("VITE_GA_MEASUREMENT_ID", "").strip()
    meta_id = os.environ.get("VITE_META_PIXEL_ID", "").strip()
    if google_id and google_id.encode("utf-8") not in bundle:
        raise SystemExit("built frontend does not contain the expected Google Analytics ID")
    if meta_id and meta_id.encode("utf-8") not in bundle:
        raise SystemExit("built frontend does not contain the expected Meta Pixel ID")
    return {
        "firebaseProjectId": firebase_project,
        "googleMeasurementId": google_id,
        "metaPixelId": meta_id,
    }


def add_bytes(archive: tarfile.TarFile, name: str, data: bytes, mode: int) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mode = mode
    info.mtime = 0
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    archive.addfile(info, io.BytesIO(data))


def build(args: argparse.Namespace) -> tuple[Path, Path]:
    source = Path(args.source).resolve()
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    release_sha = args.release_sha.lower()
    if len(release_sha) != 40 or any(char not in "0123456789abcdef" for char in release_sha):
        raise SystemExit("release SHA must be a full 40-character Git commit")

    managed: list[dict[str, object]] = []
    payload: list[tuple[str, bytes, int]] = []
    for relative, targets in FILE_TARGETS.items():
        path = source / relative
        if not path.is_file() or path.is_symlink():
            raise SystemExit(f"required artifact file is missing or linked: {relative}")
        data = path.read_bytes()
        reject_secret_material(relative, data)
        digest = hashlib.sha256(data).hexdigest()
        payload.append((f"payload/{relative}", data, max(mode for _, mode in targets)))
        for target, mode in targets:
            managed.append(
                {"source": relative, "target": target, "mode": mode, "sha256": digest}
            )

    for relative in EXTRA_FILES:
        path = source / relative
        if not path.is_file() or path.is_symlink():
            raise SystemExit(f"required artifact metadata is missing: {relative}")
        data = path.read_bytes()
        reject_secret_material(relative, data)
        payload.append((f"payload/{relative}", data, 0o600))

    dist_files = frontend_files(source)
    frontend_entries, frontend_hash = tree_manifest(source / "dist", dist_files)
    for path in dist_files:
        payload.append((f"payload/dist/{path.relative_to(source / 'dist').as_posix()}", path.read_bytes(), 0o644))

    public_config = validate_public_config(source)
    created_at = args.created_at
    metadata = {
        "schemaVersion": 1,
        "procedureVersion": PROCEDURE_VERSION,
        "releaseSha": release_sha,
        "repository": args.repository,
        "createdAt": created_at,
        "ci": {
            "workflow": "Vibe4You CI",
            "requiredCheck": "StyleDash Required CI",
            "runId": str(args.ci_run_id),
            "url": args.ci_url,
            "conclusion": "success",
            "headSha": release_sha,
        },
        "pullRequests": [value for value in args.pull_request if value],
        "managedFiles": sorted(managed, key=lambda item: str(item["target"])),
        "frontend": {"treeSha256": frontend_hash, "files": frontend_entries},
        "publicConfig": public_config,
    }
    payload.append(
        (
            "deployment-v2.json",
            (json.dumps(metadata, indent=2, sort_keys=True) + "\n").encode("utf-8"),
            0o600,
        )
    )

    raw_tar = io.BytesIO()
    with tarfile.open(fileobj=raw_tar, mode="w", format=tarfile.PAX_FORMAT) as archive:
        for name, data, mode in sorted(payload, key=lambda item: item[0]):
            safe = PurePosixPath(name)
            if safe.is_absolute() or ".." in safe.parts:
                raise SystemExit(f"unsafe artifact path: {name}")
            add_bytes(archive, name, data, mode)
    raw_tar.seek(0)
    with output.open("wb") as destination:
        with gzip.GzipFile(filename="", mode="wb", fileobj=destination, mtime=0) as compressor:
            compressor.write(raw_tar.read())

    checksum = sha256_file(output)
    checksum_path = output.with_suffix(output.suffix + ".sha256")
    checksum_path.write_text(f"{checksum}  {output.name}\n", encoding="ascii", newline="\n")
    print(f"artifact={output}")
    print(f"artifact_sha256={checksum}")
    print(f"release_sha={release_sha}")
    return output, checksum_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--release-sha", required=True)
    parser.add_argument("--repository", default="Mohit0409/StyleDash")
    parser.add_argument("--ci-run-id", required=True)
    parser.add_argument("--ci-url", required=True)
    parser.add_argument("--created-at", required=True, help="immutable commit timestamp in ISO-8601 form")
    parser.add_argument("--pull-request", action="append", default=[])
    return parser.parse_args()


if __name__ == "__main__":
    build(parse_args())
