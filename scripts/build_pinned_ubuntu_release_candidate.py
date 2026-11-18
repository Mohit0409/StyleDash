"""Build or verify the pinned 60-target Vibe4You Ubuntu candidate OFFLINE.

The candidate mirrors the current flat ``admin/`` and ``server/`` code layout
under an isolated payload directory. It deliberately contains no activation,
SSH, systemd mutation, database, backup, secret, or runtime-state capability.
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

from scripts import assemble_pinned_server_code as server_sources

CONTRACT = ROOT / "deployment-targets/vibe4you-20261116-r2/ubuntu-release-contract.json"
CONTRACT_SHA256 = "d7b78dd49e6f06250bb3401f8702723fd8bd50581099b81f6c52d88e885b3909"
SOURCE_MAP_COPY = "source-map.json"
CONTRACT_COPY = "ubuntu-release-contract.json"
MANIFEST_NAME = "candidate-manifest.json"
SHA_LIST_NAME = "SHA256SUMS"
METADATA_NAMES = {SOURCE_MAP_COPY, CONTRACT_COPY, MANIFEST_NAME, SHA_LIST_NAME}
FORBIDDEN_NAME_PARTS = {
    ".env", "backups", "logs", "private", "secrets", "credentials", "__pycache__"
}
FORBIDDEN_SUFFIXES = {".db", ".pyc", ".key", ".pem"}


class UbuntuCandidateError(RuntimeError):
    pass


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_new_temp_directory(output: Path) -> None:
    temp_root = Path(tempfile.gettempdir()).resolve()
    resolved = output.resolve()
    if (
        not resolved.is_relative_to(temp_root) or resolved == temp_root
        or resolved.is_relative_to(ROOT.resolve()) or output.exists()
        or output.is_symlink() or not output.parent.is_dir()
    ):
        raise UbuntuCandidateError("Output must be a new directory under system temp")


def _assert_public_target(target: str) -> None:
    pp = PurePosixPath(target)
    lower_parts = {part.lower() for part in pp.parts}
    if (
        pp.is_absolute() or ".." in pp.parts or pp.as_posix() != target
        or "\\" in target or ":" in target
        or lower_parts.intersection(FORBIDDEN_NAME_PARTS)
        or pp.suffix.lower() in FORBIDDEN_SUFFIXES
        or any("secret" in part.lower() or "token" in part.lower() for part in pp.parts)
    ):
        raise UbuntuCandidateError("Forbidden runtime/private candidate target")


def validate_contract() -> tuple[list[tuple[Path, Path, str]], dict]:
    entries, source_map = server_sources.validate()
    raw = CONTRACT.read_bytes()
    if digest(raw) != CONTRACT_SHA256:
        raise UbuntuCandidateError("Ubuntu release contract pinned hash changed")
    contract = json.loads(raw)
    if (
        contract.get("schema_version") != 1
        or contract.get("production_root") != "/opt/vibe4you-production"
        or contract.get("production_integrity_manifest_sha256") != server_sources.LIVE_MANIFEST_SHA256
        or contract.get("backend_source_map_sha256") != server_sources.MAP_SHA256
        or contract.get("backend_source_map")
        != "deployment-targets/vibe4you-20261116-r2/source-map.json"
    ):
        raise UbuntuCandidateError("Wrong Ubuntu production/source-map baseline")
    payload = contract.get("payload", {})
    if payload != {
        "target_count": 60,
        "admin_target_count": 33,
        "server_target_count": 27,
        "allowed_roots": ["admin", "server"],
        "generated_exclusions": ["server/index.html"],
    }:
        raise UbuntuCandidateError("Wrong Ubuntu payload boundary")
    services = contract.get("service_contract", {})
    public = services.get("public", {})
    admin = services.get("admin", {})
    tunnel = services.get("tunnel", {})
    if (
        (public.get("unit"), public.get("exec_start"), public.get("working_directory"),
         public.get("user"), public.get("group"), public.get("bind"), public.get("port"),
         public.get("public_ingress"), public.get("no_new_privileges"))
        != ("vibe4you-production-public.service", "/opt/vibe4you-production/run-public.sh",
            "/opt/vibe4you-production", "vibe4you", "vibe4you", "127.0.0.1", 8080,
            True, True)
        or (admin.get("unit"), admin.get("exec_start"), admin.get("working_directory"),
            admin.get("user"), admin.get("group"), admin.get("bind"), admin.get("port"),
            admin.get("public_ingress"), admin.get("no_new_privileges"))
        != ("vibe4you-production-admin.service", "/opt/vibe4you-production/run-admin.sh",
            "/opt/vibe4you-production", "vibe4you", "vibe4you", "127.0.0.1", 8081,
            False, True)
        or tunnel.get("unit") != "vibe4you-cloudflared.service"
        or tunnel.get("public_ingress_must_target") != "127.0.0.1:8080"
        or tunnel.get("admin_ingress_forbidden") is not True
        or tunnel.get("credential_contents_in_repository") is not False
    ):
        raise UbuntuCandidateError("Public/Admin/tunnel isolation contract changed")
    activation = contract.get("activation", {})
    if (
        activation.get("implemented") is not False
        or activation.get("authorized") is not False
        or activation.get("old_termux_installer_allowed") is not False
        or activation.get("database_rollback_allowed") is not False
    ):
        raise UbuntuCandidateError("Candidate must not authorize activation or database rollback")
    preserve = set(contract.get("preserve_paths", []))
    required_preserve = {
        "/opt/vibe4you-production/run-public.sh",
        "/opt/vibe4you-production/run-admin.sh",
        "/opt/vibe4you-production/bin/**",
        "/opt/vibe4you-production/venv/**",
        "/opt/vibe4you-production/private/**",
        "/opt/vibe4you-production/server/assets/**",
        "/opt/vibe4you-production/server/index.html",
        "/etc/vibe4you-production/**",
    }
    if preserve != required_preserve or len(contract.get("required_gates_before_any_future_activation", [])) != 9:
        raise UbuntuCandidateError("Preservation or human-gate contract changed")
    target_counts = Counter(target.parts[0] for target, _, _ in entries)
    if target_counts != {"admin": 33, "server": 27}:
        raise UbuntuCandidateError("Admin/Public target separation changed")
    by_target = {target.as_posix(): (source, sha) for target, source, sha in entries}
    if (
        "server/index.html" in by_target
        or "admin/serve.py" not in by_target or "server/serve.py" not in by_target
        or by_target["admin/serve.py"][1] == by_target["server/serve.py"][1]
        or source_map.get("generated_exclusions") != ["server/index.html"]
    ):
        raise UbuntuCandidateError("Generated homepage or divergent entrypoint boundary changed")
    for target in by_target:
        _assert_public_target(target)
    return entries, contract


def _candidate_manifest(entries: list[tuple[Path, Path, str]]) -> dict:
    files = [
        {
            "target": target.as_posix(),
            "sha256": sha,
            "size_bytes": len(source.read_bytes()),
        }
        for target, source, sha in entries
    ]
    files.sort(key=lambda row: row["target"])
    return {
        "schema_version": 1,
        "scope": "offline Ubuntu candidate payload; activation not implemented or authorized",
        "production_integrity_manifest_sha256": server_sources.LIVE_MANIFEST_SHA256,
        "source_map_sha256": server_sources.MAP_SHA256,
        "ubuntu_release_contract_sha256": CONTRACT_SHA256,
        "activation_implemented": False,
        "files": files,
    }


def verify_candidate(candidate: Path) -> dict:
    entries, _ = validate_contract()
    root = candidate.resolve(strict=True)
    temp_root = Path(tempfile.gettempdir()).resolve()
    if not root.is_relative_to(temp_root) or root == temp_root or candidate.is_symlink():
        raise UbuntuCandidateError("Candidate verification is restricted to OS temp")
    for name in METADATA_NAMES:
        path = root / name
        if path.is_symlink() or not path.is_file():
            raise UbuntuCandidateError("Candidate metadata absent or symlinked")
    if (root / CONTRACT_COPY).read_bytes() != CONTRACT.read_bytes():
        raise UbuntuCandidateError("Candidate contract bytes changed")
    if (root / SOURCE_MAP_COPY).read_bytes() != server_sources.MAP.read_bytes():
        raise UbuntuCandidateError("Candidate source map bytes changed")
    expected_manifest = _candidate_manifest(entries)
    actual_manifest = json.loads((root / MANIFEST_NAME).read_text("utf-8"))
    if actual_manifest != expected_manifest:
        raise UbuntuCandidateError("Candidate manifest changed")
    expected_files = set()
    sha_lines = []
    for target, _, sha in entries:
        relative = "payload/" + target.as_posix()
        path = root / relative
        if path.is_symlink() or not path.is_file() or digest(path.read_bytes()) != sha:
            raise UbuntuCandidateError("Candidate payload byte/hash mismatch: " + relative)
        expected_files.add(relative)
        sha_lines.append(sha + "  " + relative)
    expected_sha_list = "\n".join(sorted(sha_lines)) + "\n"
    if (root / SHA_LIST_NAME).read_text("utf-8") != expected_sha_list:
        raise UbuntuCandidateError("Candidate SHA256SUMS changed")
    on_disk = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*") if path.is_file()
    }
    if on_disk != expected_files.union(METADATA_NAMES):
        raise UbuntuCandidateError("Unexpected file in Ubuntu candidate")
    return {"payload_files": 60, "metadata_files": 4, "admin_targets": 33, "server_targets": 27}


def build_temp(output: Path) -> None:
    _safe_new_temp_directory(output)
    entries, _ = validate_contract()
    output.mkdir(mode=0o700)
    try:
        payload = output / "payload"
        server_sources.assemble_temp(payload)
        shutil.copyfile(server_sources.MAP, output / SOURCE_MAP_COPY)
        shutil.copyfile(CONTRACT, output / CONTRACT_COPY)
        manifest = _candidate_manifest(entries)
        (output / MANIFEST_NAME).write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
        )
        sha_lines = [sha + "  payload/" + target.as_posix() for target, _, sha in entries]
        (output / SHA_LIST_NAME).write_text(
            "\n".join(sorted(sha_lines)) + "\n", encoding="utf-8", newline="\n"
        )
        result = verify_candidate(output)
    except Exception:
        shutil.rmtree(output)
        raise
    print(
        "OFFLINE_UBUNTU_CANDIDATE_PASS payload_files=60 metadata_files=4"
        " admin_targets=33 server_targets=27 activation=no output=" + str(output)
    )
    if result["payload_files"] != 60:
        raise UbuntuCandidateError("Candidate verification result changed")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate source and Ubuntu contract only")
    parser.add_argument("--output", type=Path, help="Build into a new directory under OS temp")
    options = parser.parse_args(argv)
    if options.check and options.output:
        parser.error("Select --check or --output, not both")
    try:
        if options.output:
            build_temp(options.output)
        else:
            entries, _ = validate_contract()
            print(
                "OFFLINE_UBUNTU_RELEASE_CONTRACT_PASS targets=" + str(len(entries))
                + " admin=33 server=27 activation=no termux_installer=no"
            )
    except (OSError, KeyError, ValueError, TypeError, UbuntuCandidateError,
            server_sources.PinnedSourceError) as exc:
        print("UBUNTU_CANDIDATE_CHECK_STOP " + str(exc), file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
