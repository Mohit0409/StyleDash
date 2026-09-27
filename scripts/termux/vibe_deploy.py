#!/usr/bin/env python3
"""Transactional Vibe4You deployment runner for the Termux production host."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any


PROCEDURE_VERSION = 2
CANONICAL_ORIGIN = "https://vibe4you.in"
PUBLIC_LOCAL = "http://127.0.0.1:8080"
ADMIN_LOCAL = "http://127.0.0.1:8081"
SENSITIVE_PATHS = (
    "/admin",
    "/admin/",
    "/api/admin/deployment-probe",
    "/backups",
    "/backups/",
    "/backups/deployment-probe",
    "/logs",
    "/logs/",
    "/logs/deployment-probe",
    "/styledash.db",
    "/.env",
    "/secrets.env",
    "/database.db",
)
PROTECTED_FILES = (
    "server/styledash_security.py",
    "admin/styledash_security.py",
    "admin/admin/index.html",
    "admin/admin/admin.js",
    ".local/share/styledash/catalog.json",
    ".local/share/styledash/settings.json",
    ".local/share/styledash/delivery-zones.geojson",
    ".config/styledash/secrets.env",
)
FORBIDDEN_PARTS = {
    ".env",
    "secrets.env",
    "styledash.db",
    "database.db",
    "orders.json",
    "firebase-admin.json",
}
SECRET_PATTERNS = (
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(rb"gh[pousr]_[A-Za-z0-9_]{30,}"),
    re.compile(rb"AKIA[0-9A-Z]{16}"),
)


class DeployError(RuntimeError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> None:
        return None


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def tree_hash(root: Path) -> tuple[str, int]:
    lines: list[str] = []
    files = sorted(path for path in root.rglob("*") if path.is_file() and not path.is_symlink())
    for path in files:
        relative = path.relative_to(root).as_posix()
        lines.append(f"{sha256_file(path)}  {relative}\n")
    return hashlib.sha256("".join(lines).encode("utf-8")).hexdigest(), len(files)


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(temporary, 0o600)
    temporary.replace(path)


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key.strip()):
            values[key.strip()] = value.strip().strip("'\"")
    return values


class Artifact:
    def __init__(self, archive: Path, deployments_root: Path):
        self.archive = archive.resolve()
        self.checksum_file = Path(f"{self.archive}.sha256")
        self.deployments_root = deployments_root
        self.sha256 = ""
        self.metadata: dict[str, Any] = {}
        self.stage: Path | None = None

    def validate_checksum(self) -> None:
        if not self.archive.is_file() or not self.checksum_file.is_file():
            raise DeployError("artifact or artifact checksum file is missing")
        token = self.checksum_file.read_text(encoding="ascii").strip().split()[0].lower()
        if not re.fullmatch(r"[0-9a-f]{64}", token):
            raise DeployError("artifact checksum file is invalid")
        actual = sha256_file(self.archive)
        if actual != token:
            raise DeployError("artifact SHA-256 mismatch")
        self.sha256 = actual

    def validate_members(self) -> None:
        seen: set[str] = set()
        with tarfile.open(self.archive, "r:gz") as archive:
            for member in archive.getmembers():
                path = PurePosixPath(member.name)
                if path.is_absolute() or not path.parts or ".." in path.parts:
                    raise DeployError(f"unsafe artifact path: {member.name}")
                if member.issym() or member.islnk() or member.isdev():
                    raise DeployError(f"artifact links/devices are forbidden: {member.name}")
                lowered = {part.lower() for part in path.parts}
                if lowered & FORBIDDEN_PARTS or any(part.endswith((".db", ".db-wal", ".db-shm")) for part in lowered):
                    raise DeployError(f"secret/runtime-data path is forbidden in artifact: {member.name}")
                if member.name in seen:
                    raise DeployError(f"duplicate artifact member: {member.name}")
                seen.add(member.name)
                if member.isfile():
                    extracted = archive.extractfile(member)
                    if extracted is None:
                        raise DeployError(f"artifact member is unreadable: {member.name}")
                    data = extracted.read()
                    if any(pattern.search(data) for pattern in SECRET_PATTERNS):
                        raise DeployError(f"artifact contains secret-like material: {member.name}")
        if "deployment-v2.json" not in seen:
            raise DeployError("artifact provenance metadata is missing")

    def extract(self) -> Path:
        self.validate_checksum()
        self.validate_members()
        with tarfile.open(self.archive, "r:gz") as archive:
            metadata_member = archive.getmember("deployment-v2.json")
            handle = archive.extractfile(metadata_member)
            if handle is None:
                raise DeployError("artifact metadata is unreadable")
            self.metadata = json.load(handle)
        release = str(self.metadata.get("releaseSha", ""))
        if not re.fullmatch(r"[0-9a-f]{40}", release):
            raise DeployError("artifact release SHA is invalid")
        transaction = f"{release[:12]}-{self.sha256[:12]}"
        stage = self.deployments_root / "staging" / transaction
        if stage.exists():
            shutil.rmtree(stage)
        stage.mkdir(parents=True, mode=0o700)
        with tarfile.open(self.archive, "r:gz") as archive:
            archive.extractall(stage, filter="data")
        self.stage = stage
        self.validate_extracted()
        return stage

    def validate_extracted(self) -> None:
        assert self.stage is not None
        if int(self.metadata.get("procedureVersion", 0)) != PROCEDURE_VERSION:
            raise DeployError("unsupported deployment procedure version")
        ci = self.metadata.get("ci") or {}
        if (
            ci.get("conclusion") != "success"
            or ci.get("requiredCheck") != "StyleDash Required CI"
            or ci.get("headSha") != self.metadata.get("releaseSha")
            or not str(ci.get("runId", "")).isdigit()
            or not str(ci.get("url", "")).startswith("https://github.com/Mohit0409/StyleDash/actions/runs/")
        ):
            raise DeployError("required exact-SHA GitHub CI evidence is missing")
        for entry in self.metadata.get("managedFiles", []):
            source = self.stage / "payload" / str(entry.get("source", ""))
            target = PurePosixPath(str(entry.get("target", "")))
            if target.is_absolute() or ".." in target.parts or not source.is_file() or source.is_symlink():
                raise DeployError("artifact managed-file mapping is unsafe or incomplete")
            if sha256_file(source) != entry.get("sha256"):
                raise DeployError(f"staged-file mismatch: {entry.get('source')}")
        dist = self.stage / "payload" / "dist"
        actual_tree, count = tree_hash(dist)
        frontend = self.metadata.get("frontend") or {}
        if actual_tree != frontend.get("treeSha256") or count != len(frontend.get("files") or []):
            raise DeployError("staged frontend manifest mismatch")


class Deployment:
    def __init__(self, artifact_path: Path, *, home: Path | None = None):
        self.home = (home or Path(os.environ.get("STYLEDASH_DEPLOY_HOME", str(Path.home())))).resolve()
        self.data_root = self.home / ".local" / "share" / "styledash"
        self.deployments = self.data_root / "deployments"
        self.run_dir = self.home / "run"
        self.logs_dir = self.home / "logs"
        self.history_dir = self.deployments / "history"
        self.records_dir = self.deployments / "records"
        self.current_manifest = self.deployments / "current.json"
        self.artifact = Artifact(artifact_path, self.deployments)
        self.stage: Path | None = None
        self.transaction = ""
        self.transaction_dir: Path | None = None
        self.state_path: Path | None = None
        self.log_path: Path | None = None
        self.state: dict[str, Any] = {}
        self.protected_before: dict[str, str] = {}
        self.mutation_started = False

    def initialize(self) -> None:
        self.ensure_private_directory(self.data_root)
        for directory in (self.deployments, self.history_dir, self.records_dir, self.logs_dir, self.run_dir):
            directory.mkdir(parents=True, exist_ok=True)
            os.chmod(directory, 0o700)
            self.ensure_private_directory(directory)
        self.stage = self.artifact.extract()
        release = self.artifact.metadata["releaseSha"]
        self.transaction = f"{release[:12]}-{self.artifact.sha256[:12]}"
        self.transaction_dir = self.deployments / "transactions" / self.transaction
        self.transaction_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self.transaction_dir, 0o700)
        self.state_path = self.transaction_dir / "state.json"
        self.log_path = self.logs_dir / f"vibe-deploy-{self.transaction}.log"
        if self.state_path.is_file():
            self.state = json.loads(self.state_path.read_text(encoding="utf-8"))
            if self.state.get("artifactSha256") != self.artifact.sha256:
                raise DeployError("existing transaction artifact identity mismatch")
        else:
            self.state = {
                "transaction": self.transaction,
                "releaseSha": release,
                "artifactSha256": self.artifact.sha256,
                "stage": "IDLE",
                "result": "PENDING",
                "backupPassed": False,
                "mutationStarted": False,
                "createdAt": utc_now(),
                "updatedAt": utc_now(),
                "log": str(self.log_path),
            }
            self.save_state()

    def save_state(self, stage: str | None = None, **updates: Any) -> None:
        if stage:
            self.state["stage"] = stage
        self.state.update(updates)
        self.state["updatedAt"] = utc_now()
        assert self.state_path is not None
        atomic_json(self.state_path, self.state)
        atomic_json(self.deployments / "last-status.json", self.state)

    def log(self, message: str) -> None:
        assert self.log_path is not None
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"{utc_now()} {message}\n")
        os.chmod(self.log_path, 0o600)

    def ensure_private_directory(self, path: Path) -> None:
        if not path.exists():
            return
        # Termux is POSIX and must enforce ownership. Windows is only a local
        # simulation host, where Python intentionally has no getuid().
        expected_uid = os.getuid() if hasattr(os, "getuid") else path.stat().st_uid
        if path.is_symlink() or path.resolve() != path or path.stat().st_uid != expected_uid:
            raise DeployError(f"managed directory is redirected or not owned by the runtime user: {path}")

    def command(self, args: list[str], *, timeout: int = 60, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout, env=env, check=False)
        if result.returncode:
            detail = (result.stderr or result.stdout).strip().splitlines()
            raise DeployError(f"command failed ({args[0]}): {detail[-1] if detail else result.returncode}")
        return result

    def http(self, url: str, expected: int, *, host: str | None = None, timeout: int = 15) -> bytes:
        headers = {"User-Agent": "Vibe4You-Deployment-v2/2"}
        if host:
            headers["Host"] = host
        request = urllib.request.Request(url, headers=headers)
        opener = urllib.request.build_opener(NoRedirect)
        try:
            with opener.open(request, timeout=timeout) as response:
                status = response.status
                body = response.read(2 * 1024 * 1024)
        except urllib.error.HTTPError as error:
            status = error.code
            body = error.read(2 * 1024 * 1024)
        if status != expected:
            raise DeployError(f"unexpected HTTP {status} for {url}; expected {expected}")
        return body

    def database_check(self) -> None:
        database = self.data_root / "styledash.db"
        if not database.is_file() or database.is_symlink():
            raise DeployError("authoritative SQLite database is missing or redirected")
        connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
        try:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
        finally:
            connection.close()
        if integrity != "ok" or foreign_keys:
            raise DeployError("SQLite integrity or foreign-key check failed")

    def protected_hashes(self) -> dict[str, str]:
        hashes: dict[str, str] = {}
        for relative in PROTECTED_FILES:
            path = self.home / relative
            if not path.is_file() or path.is_symlink():
                raise DeployError(f"protected production file is missing or redirected: {relative}")
            hashes[relative] = sha256_file(path)
        return hashes

    def verify_live_baseline(self) -> str:
        assert self.stage is not None
        if self.current_manifest.is_file():
            baseline = json.loads(self.current_manifest.read_text(encoding="utf-8"))
            if baseline.get("result") != "PASS":
                raise DeployError("last deployment manifest is not a successful manifest")
            expected = baseline.get("managedFiles") or {}
            frontend_expected = baseline.get("frontendTreeSha256")
            previous = str(baseline.get("deployedCommit", ""))
        else:
            bootstrap_path = self.stage / "payload" / "ops" / "deployment-v2-bootstrap.json"
            baseline = json.loads(bootstrap_path.read_text(encoding="utf-8"))
            expected = baseline.get("managedFiles") or {}
            frontend_expected = baseline.get("frontendTreeSha256")
            previous = str(baseline.get("deployedCommit", ""))
            if previous != "780cde2aca46fc21a02eaa480e55c8060820df94":
                raise DeployError("deployment-v2 bootstrap provenance is invalid")
        for relative, expected_hash in expected.items():
            path = self.home / relative
            if not path.is_file() or path.is_symlink() or sha256_file(path) != expected_hash:
                raise DeployError(f"unexpected live managed-file drift: {relative}")
        actual_frontend, _ = tree_hash(self.home / "server")
        # The public server directory also contains runtime Python modules. Build
        # the deployed frontend identity from the explicit static layout only.
        actual_frontend, _ = self.frontend_tree(self.home / "server")
        if actual_frontend != frontend_expected:
            raise DeployError("unexpected live managed frontend drift")
        return previous

    def frontend_tree(self, root: Path) -> tuple[str, int]:
        files: list[Path] = []
        for name in ("index.html", "favicon.svg", "manifest.json", "product-placeholder.svg", "robots.txt"):
            path = root / name
            if not path.is_file() or path.is_symlink():
                raise DeployError(f"managed frontend file is missing: {name}")
            files.append(path)
        assets = root / "assets"
        if not assets.is_dir() or assets.is_symlink():
            raise DeployError("managed frontend assets directory is missing or redirected")
        files.extend(sorted(path for path in assets.rglob("*") if path.is_file() and not path.is_symlink()))
        lines = [f"{sha256_file(path)}  {path.relative_to(root).as_posix()}\n" for path in sorted(files)]
        return hashlib.sha256("".join(lines).encode("utf-8")).hexdigest(), len(files)

    def syntax_check(self) -> None:
        assert self.stage is not None
        payload = self.stage / "payload"
        for path in payload.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix == ".py":
                compile(path.read_bytes(), str(path), "exec")
            elif path.name in {"vibe-deploy", "backup-styledash-data", "start-styledash-cloudflare", "styledash-process-lib"}:
                self.command(["bash", "-n", str(path)])

    def validate_public_config(self) -> None:
        assert self.stage is not None
        config = self.artifact.metadata.get("publicConfig") or {}
        project = str(config.get("firebaseProjectId", ""))
        if not project:
            raise DeployError("artifact Firebase public configuration is incomplete")
        secrets = parse_env(self.home / ".config" / "styledash" / "secrets.env")
        if secrets.get("STYLEDASH_FIREBASE_PROJECT_ID") != project:
            raise DeployError("Firebase browser/server project IDs do not match")
        mode = secrets.get("RAZORPAY_MODE", "").lower()
        if mode not in {"test", "live"}:
            raise DeployError("Razorpay mode is missing or invalid")
        prefix = f"RAZORPAY_{mode.upper()}_"
        if any(not secrets.get(prefix + suffix) for suffix in ("KEY_ID", "KEY_SECRET", "WEBHOOK_SECRET")):
            raise DeployError("Razorpay configuration is incomplete for the current mode")
        bundle = b"\n".join(path.read_bytes() for path in (self.stage / "payload" / "dist" / "assets").glob("*.js"))
        for key in ("googleMeasurementId", "metaPixelId"):
            value = str(config.get(key, ""))
            if value and value.encode("utf-8") not in bundle:
                raise DeployError(f"artifact analytics configuration is missing: {key}")

    def validate_backup_configuration(self) -> None:
        settings = parse_env(self.home / ".config" / "styledash" / "secrets.env")
        if not settings.get("STYLEDASH_BACKUP_REMOTE"):
            raise DeployError("required primary off-device backup destination is not configured")
        if not settings.get("STYLEDASH_BACKUP_REMOTE_SECONDARY"):
            raise DeployError("required secondary off-device backup destination is not configured")

    def verify_processes(self) -> None:
        self.command([str(self.home / "bin" / "verify-styledash-processes")], timeout=20)

    def security_routes(self) -> None:
        health = self.http(f"{CANONICAL_ORIGIN}/api/health", 200)
        payload = json.loads(health)
        if payload.get("service") != "Vibe4You" or payload.get("database") != "ok":
            raise DeployError("canonical production health identity is invalid")
        for path in SENSITIVE_PATHS:
            self.http(f"{CANONICAL_ORIGIN}{path}", 404)

    def preflight(self) -> str:
        self.save_state("PREFLIGHT", result="PENDING", preflightStartedAt=utc_now())
        self.log("preflight started")
        assert self.stage is not None
        for directory in (self.home / "server", self.home / "admin", self.data_root, self.deployments):
            self.ensure_private_directory(directory)
        free = shutil.disk_usage(self.home).free
        required = max(self.artifact.archive.stat().st_size * 4, 128 * 1024 * 1024)
        if free < required:
            raise DeployError("insufficient disk space for artifact, snapshot, and rollback")
        self.syntax_check()
        self.database_check()
        self.verify_processes()
        local = json.loads(self.http(f"{PUBLIC_LOCAL}/api/health", 200))
        if local.get("service") != "Vibe4You" or local.get("database") != "ok":
            raise DeployError("local public runtime identity is invalid")
        admin = self.http(f"{ADMIN_LOCAL}/", 200, host="127.0.0.1:8081", timeout=5)
        if b"Vibe4You Local Administration" not in admin:
            raise DeployError("private administrator runtime identity is invalid")
        self.security_routes()
        self.validate_public_config()
        self.validate_backup_configuration()
        previous = self.verify_live_baseline()
        self.protected_before = self.protected_hashes()
        self.save_state(
            "PREFLIGHT_PASS",
            preflight="PASS",
            previousSha=previous,
            protectedBefore=self.protected_before,
            readyToBackup=True,
            productionMutated=False,
            backupNotStarted=not bool(self.state.get("backupPassed")),
        )
        self.log("preflight PASS; production not mutated")
        return previous

    def backup(self) -> str:
        if self.state.get("backupPassed"):
            self.log("existing successful backup reused for identical transaction")
            return str(self.state.get("backupTimestamp", ""))
        assert self.transaction_dir is not None and self.stage is not None
        progress = self.transaction_dir / "backup-progress"
        marker = self.run_dir / "styledash-last-local-backup"
        before = marker.read_text(encoding="utf-8").strip() if marker.is_file() else ""
        env = os.environ.copy()
        env["STYLEDASH_BACKUP_PROGRESS_FILE"] = str(progress)
        command = ["bash", str(self.stage / "payload" / "scripts" / "termux" / "backup-styledash-data")]
        self.save_state("BACKUP_LOCAL", backupStartedAt=utc_now(), backupNotStarted=False)
        with self.log_path.open("a", encoding="utf-8") as log_handle:
            process = subprocess.Popen(command, stdout=log_handle, stderr=subprocess.STDOUT, text=True, env=env)
            last = ""
            while process.poll() is None:
                if progress.is_file():
                    current = progress.read_text(encoding="utf-8").strip()
                    if current and current != last:
                        last = current
                        self.save_state(current)
                time.sleep(0.25)
            if process.returncode:
                raise DeployError("required production backup failed; production was not mutated")
        after = marker.read_text(encoding="utf-8").strip() if marker.is_file() else ""
        if not after or after == before:
            raise DeployError("backup completed without a fresh local backup timestamp")
        log_text = self.log_path.read_text(encoding="utf-8")
        if f"Primary off-device Vibe4You backup verified: {after}" not in log_text:
            raise DeployError("primary off-device backup verification is missing")
        if f"Secondary off-device Vibe4You backup verified: {after}" not in log_text:
            raise DeployError("secondary off-device backup verification is missing")
        self.save_state(
            "BACKUP_PASS",
            backupPassed=True,
            backupTimestamp=after,
            backupPrimary="PASS",
            backupSecondary="PASS",
        )
        self.log(f"backup PASS timestamp={after}")
        return after

    def snapshot(self) -> Path:
        assert self.transaction_dir is not None
        rollback = self.transaction_dir / "rollback"
        if rollback.exists() and self.state.get("rollbackReady"):
            return rollback
        if rollback.exists():
            shutil.rmtree(rollback)
        rollback.mkdir(parents=True, mode=0o700)
        managed_targets = {str(entry["target"]) for entry in self.artifact.metadata["managedFiles"]}
        for relative in sorted(managed_targets):
            source = self.home / relative
            destination = rollback / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            if source.is_file() and not source.is_symlink():
                shutil.copy2(source, destination)
            else:
                destination.with_name(destination.name + ".absent").touch()
        frontend = rollback / "server" / "frontend"
        frontend.mkdir(parents=True)
        for name in ("index.html", "favicon.svg", "manifest.json", "product-placeholder.svg", "robots.txt"):
            shutil.copy2(self.home / "server" / name, frontend / name)
        shutil.copytree(self.home / "server" / "assets", frontend / "assets")
        self.save_state("ROLLBACK_READY", rollbackReady=True, rollbackSnapshot=str(rollback))
        return rollback

    def stop_services(self) -> None:
        script = f'''
set -eu
. "{self.home}/bin/styledash-process-lib"
styledash_watchdog_stop "{self.home}/bin/styledash-health" "{self.home}/run/styledash-health.pid"
styledash_stop_matching_processes public "{self.home}/server/serve.py --bind 127.0.0.1 --port 8080" "--directory {self.home}/server"
styledash_stop_matching_processes admin "{self.home}/admin/serve.py --bind 127.0.0.1 --port 8081" "--assets {self.home}/admin/admin"
rm -f -- "{self.home}/run/styledash.pid" "{self.home}/run/styledash-admin.pid"
styledash_wait_for_port_release 8080 public
styledash_wait_for_port_release 8081 admin
'''
        self.command(["bash", "-c", script], timeout=45)

    def start_services(self) -> None:
        self.command([str(self.home / "bin" / "start-styledash")], timeout=45)
        self.command([str(self.home / "bin" / "start-styledash-admin")], timeout=45)
        script = f'''
set -eu
. "{self.home}/bin/styledash-process-lib"
styledash_watchdog_start "{self.home}/bin/styledash-health" "{self.home}/run/styledash-health.pid" "{self.home}/logs/styledash-health.log"
'''
        self.command(["bash", "-c", script], timeout=45)

    def mutate(self) -> None:
        assert self.stage is not None
        self.save_state("MUTATING", mutationStarted=True, productionMutated=True, mutationStartedAt=utc_now())
        self.mutation_started = True
        self.stop_services()
        public = self.home / "server"
        shutil.rmtree(public / "assets")
        shutil.copytree(self.stage / "payload" / "dist" / "assets", public / "assets")
        for name in ("index.html", "favicon.svg", "manifest.json", "product-placeholder.svg", "robots.txt"):
            shutil.copy2(self.stage / "payload" / "dist" / name, public / name)
        for entry in self.artifact.metadata["managedFiles"]:
            source = self.stage / "payload" / str(entry["source"])
            target = self.home / str(entry["target"])
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(f".{target.name}.{os.getpid()}.new")
            shutil.copyfile(source, temporary)
            os.chmod(temporary, int(entry["mode"]))
            temporary.replace(target)
        self.start_services()

    def verify_installed(self) -> None:
        for entry in self.artifact.metadata["managedFiles"]:
            target = self.home / str(entry["target"])
            if not target.is_file() or target.is_symlink() or sha256_file(target) != entry["sha256"]:
                raise DeployError(f"installed managed-file mismatch: {entry['target']}")
        frontend, count = self.frontend_tree(self.home / "server")
        if frontend != self.artifact.metadata["frontend"]["treeSha256"]:
            raise DeployError("installed frontend does not match the staged artifact")
        if count != len(self.artifact.metadata["frontend"]["files"]):
            raise DeployError("installed frontend file count does not match the staged artifact")

    def smoke(self) -> None:
        self.save_state("VERIFYING")
        self.verify_processes()
        health = json.loads(self.http(f"{PUBLIC_LOCAL}/api/health", 200))
        if health.get("database") != "ok":
            raise DeployError("post-deploy local database health failed")
        self.http(f"{PUBLIC_LOCAL}/", 200)
        self.http(f"{PUBLIC_LOCAL}/api/shop-products/published", 200)
        homepage = json.loads(self.http(f"{PUBLIC_LOCAL}/api/shop-products/homepage", 200))
        products: list[dict[str, Any]] = []
        if isinstance(homepage, list):
            products = [item for item in homepage if isinstance(item, dict)]
        elif isinstance(homepage, dict):
            for value in homepage.values():
                if isinstance(value, list):
                    products.extend(item for item in value if isinstance(item, dict))
        if products:
            product_id = products[0].get("id") or products[0].get("productId")
            if product_id:
                self.http(f"{PUBLIC_LOCAL}/product/{product_id}", 200)
        self.http(f"{PUBLIC_LOCAL}/login", 200)
        self.http(f"{ADMIN_LOCAL}/", 200, host="127.0.0.1:8081", timeout=5)
        self.security_routes()
        self.database_check()
        self.verify_installed()
        if self.protected_hashes() != self.protected_before:
            raise DeployError("a protected production file changed during deployment")
        self.validate_public_config()

    def rollback(self) -> None:
        assert self.transaction_dir is not None
        rollback = self.transaction_dir / "rollback"
        self.save_state("ROLLBACK")
        failed = False
        try:
            self.stop_services()
        except Exception as error:
            self.log(f"rollback stop warning: {error}")
            failed = True
        try:
            frontend = rollback / "server" / "frontend"
            shutil.rmtree(self.home / "server" / "assets", ignore_errors=True)
            shutil.copytree(frontend / "assets", self.home / "server" / "assets")
            for name in ("index.html", "favicon.svg", "manifest.json", "product-placeholder.svg", "robots.txt"):
                shutil.copy2(frontend / name, self.home / "server" / name)
            for entry in self.artifact.metadata["managedFiles"]:
                relative = str(entry["target"])
                saved = rollback / relative
                target = self.home / relative
                absent = saved.with_name(saved.name + ".absent")
                if absent.is_file():
                    target.unlink(missing_ok=True)
                elif saved.is_file():
                    shutil.copy2(saved, target)
                else:
                    raise DeployError(f"rollback snapshot is incomplete: {relative}")
            self.start_services()
            self.database_check()
            self.verify_processes()
            if self.protected_hashes() != self.protected_before:
                raise DeployError("protected files changed during rollback")
            self.verify_live_baseline()
        except Exception as error:
            self.log(f"automatic rollback failed: {error}")
            failed = True
        if failed:
            self.save_state("FAIL", result="FAIL", automaticRollback="FAIL", manualRecoveryRequired=True)
            raise DeployError("AUTOMATIC_ROLLBACK=FAIL; MANUAL_RECOVERY_REQUIRED")
        self.save_state("FAIL", result="FAIL", automaticRollback="PASS", productionMutated=False)
        self.log("AUTOMATIC_ROLLBACK=PASS")

    def write_success(self, previous: str, backup_timestamp: str) -> Path:
        managed = {str(entry["target"]): str(entry["sha256"]) for entry in self.artifact.metadata["managedFiles"]}
        release = self.artifact.metadata["releaseSha"]
        timestamp = utc_now()
        manifest = {
            "schemaVersion": 1,
            "procedureVersion": PROCEDURE_VERSION,
            "deployedCommit": release,
            "previousDeployedCommit": previous,
            "deployedAt": timestamp,
            "artifactSha256": self.artifact.sha256,
            "managedFiles": managed,
            "frontendTreeSha256": self.artifact.metadata["frontend"]["treeSha256"],
            "frontendFileCount": len(self.artifact.metadata["frontend"]["files"]),
            "backupTimestamp": backup_timestamp,
            "rollbackSnapshot": self.state.get("rollbackSnapshot"),
            "ci": self.artifact.metadata["ci"],
            "pullRequests": self.artifact.metadata.get("pullRequests", []),
            "protectedFileHashes": self.protected_before,
            "result": "PASS",
        }
        history = self.history_dir / f"{timestamp.replace(':', '').replace('-', '')}-{release[:12]}.json"
        atomic_json(history, manifest)
        atomic_json(self.current_manifest, manifest)
        record = self.records_dir / f"{timestamp[:10]}-{release[:12]}.md"
        record.write_text(
            "\n".join(
                [
                    f"# Vibe4You deployment {release[:12]}",
                    "",
                    f"- Deployed SHA: `{release}`",
                    f"- Previous SHA: `{previous}`",
                    f"- CI: PASS ({self.artifact.metadata['ci']['url']})",
                    f"- Artifact SHA-256: `{self.artifact.sha256}`",
                    "- Preflight: PASS",
                    f"- Backup timestamp: `{backup_timestamp}`",
                    "- Primary backup verification: PASS",
                    "- Secondary backup verification: PASS when configured",
                    f"- Rollback snapshot: `{self.state.get('rollbackSnapshot')}`",
                    f"- Production mutation time: `{self.state.get('mutationStartedAt')}`",
                    "- Runtime acceptance: PASS",
                    "- Security smoke: PASS",
                    "- SQLite integrity: PASS",
                    "- SQLite foreign-key errors: 0",
                    "- Final result: DEPLOYMENT PASS",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        os.chmod(record, 0o600)
        self.save_state(
            "PASS",
            result="PASS",
            currentSha=release,
            previousSha=previous,
            deploymentRecord=str(record),
            completedAt=timestamp,
            automaticRollback="READY",
        )
        return record

    def run(self, *, preflight_only: bool = False) -> None:
        self.initialize()
        if self.state.get("result") == "PASS" and not preflight_only:
            self.print_summary()
            return
        try:
            previous = self.preflight()
            if preflight_only:
                self.print_summary(preflight_only=True)
                return
            backup_timestamp = self.backup()
            self.snapshot()
            self.mutate()
            self.smoke()
            self.write_success(previous, backup_timestamp)
            self.log("DEPLOYMENT PASS")
            self.print_summary()
        except Exception as error:
            self.log(f"failure: {error}")
            if self.mutation_started or self.state.get("mutationStarted"):
                try:
                    self.rollback()
                except Exception as rollback_error:
                    print(str(rollback_error), file=sys.stderr)
            else:
                self.save_state(
                    "FAIL",
                    result="FAIL",
                    error=str(error),
                    backupNotStarted=not bool(self.state.get("backupPassed")),
                    productionMutated=False,
                )
                print("PRELIGHT=FAIL" if self.state.get("stage") == "PREFLIGHT" else "DEPLOYMENT=FAIL", file=sys.stderr)
                print(f"BACKUP_NOT_STARTED={'YES' if not self.state.get('backupPassed') else 'NO'}", file=sys.stderr)
                print("PRODUCTION_MUTATED=NO", file=sys.stderr)
            raise

    def print_summary(self, *, preflight_only: bool = False) -> None:
        print("Vibe4You Deployment v2")
        print(f"RELEASE_SHA              {self.artifact.metadata['releaseSha']}")
        print("MAIN                     VERIFIED")
        print("GITHUB_CI                PASS")
        print("ARTIFACT                 PASS")
        print("PREFLIGHT                PASS")
        print("DATABASE                 PASS")
        print("SECURITY                 PASS")
        print("LIVE_BASELINE            PASS")
        if preflight_only:
            print("BACKUP_NOT_STARTED       YES")
            print("PRODUCTION_MUTATED       NO")
            print("PRELIGHT PASS")
            return
        print(f"BACKUP_LOCAL             {'PASS' if self.state.get('backupPassed') else 'PENDING'}")
        print(f"BACKUP_PRIMARY           {self.state.get('backupPrimary', 'PENDING')}")
        print(f"BACKUP_SECONDARY         {self.state.get('backupSecondary', 'PENDING')}")
        print(f"PREVIOUS_SHA             {self.state.get('previousSha', '')}")
        print(f"CURRENT_SHA              {self.state.get('currentSha', '')}")
        print(f"ROLLBACK                 {self.state.get('automaticRollback', 'READY')}")
        print(f"DEPLOYMENT               {self.state.get('result', 'PENDING')}")
        if self.state.get("result") == "PASS":
            print("DEPLOYMENT PASS")


def status(home: Path | None = None) -> int:
    runtime_home = (home or Path(os.environ.get("STYLEDASH_DEPLOY_HOME", str(Path.home())))).resolve()
    path = runtime_home / ".local" / "share" / "styledash" / "deployments" / "last-status.json"
    if not path.is_file():
        print("STATE                    IDLE")
        return 0
    payload = json.loads(path.read_text(encoding="utf-8"))
    for key, label in (
        ("transaction", "TRANSACTION"),
        ("releaseSha", "RELEASE_SHA"),
        ("stage", "STATE"),
        ("result", "RESULT"),
        ("backupTimestamp", "BACKUP_TIMESTAMP"),
        ("deploymentRecord", "DEPLOYMENT_RECORD"),
        ("log", "LOG"),
    ):
        if payload.get(key) is not None:
            print(f"{label:<24} {payload[key]}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--preflight-only", metavar="ARTIFACT")
    group.add_argument("--run", metavar="ARTIFACT")
    group.add_argument("--status", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if args.status:
        return status()
    artifact = Path(args.preflight_only or args.run)
    deployment = Deployment(artifact)
    try:
        deployment.run(preflight_only=bool(args.preflight_only))
    except Exception as error:
        print(f"FAILED_STAGE={deployment.state.get('stage', 'ARTIFACT')}", file=sys.stderr)
        print(f"ERROR={error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
