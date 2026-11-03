"""Read-only integrity and role-import preflight for an externally supplied runtime snapshot.

Never copies files, imports application modules, reads configuration/secrets,
accesses a database, or writes into public/admin runtime directories.

Usage:
  python qa/ci_role_source_preflight.py --manifest MANIFEST \
      --public-dir PUBLIC_MIRROR --admin-dir ADMIN_MIRROR \
      --report-json REPORT.json

The source manifest may contain many non-Python assets. Only direct
server/*.py and admin/*.py entries are evaluated. Import resolution
warnings are diagnostic because optional import paths may be intentional.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
from pathlib import Path

ROLE_SOURCE = re.compile(
    r"^([0-9a-f]{64})  (server|admin)/([A-Za-z_][A-Za-z0-9_]*\.py)$"
)
PROJECT_PREFIXES = (
    "styledash_", "gst_", "tax_", "invoice_", "catalog_",
    "store_", "receipt_", "audit_",
)


def _source_imports(tree: ast.AST) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                found.add(node.module.split(".")[0])
            elif node.level:
                found.update(alias.name.split(".")[0] for alias in node.names)
    return {name for name in found if name.startswith(PROJECT_PREFIXES)}


def inspect(manifest: Path, public_dir: Path, admin_dir: Path) -> dict:
    """Validate exact runtime bytes by role without executing the code."""
    errors: list[str] = []
    warnings: list[str] = []
    expected: dict[str, dict[str, str]] = {"server": {}, "admin": {}}

    try:
        lines = manifest.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        return {"passed": False, "errors": [f"manifest unreadable: {type(exc).__name__}"],
                "warnings": [], "roles": {}, "divergent_shared_modules": []}

    for line in lines:
        match = ROLE_SOURCE.fullmatch(line)
        if match:
            digest, role, filename = match.groups()
            if filename in expected[role]:
                errors.append(f"duplicate source manifest entry: {role}/{filename}")
            else:
                expected[role][filename] = digest
        elif "  server/" in line or "  admin/" in line:
            # Reject unsafe Python paths instead of ever joining them to a base.
            if line.rstrip().endswith(".py"):
                errors.append("invalid role Python path in manifest")

    roots = {"server": Path(public_dir), "admin": Path(admin_dir)}
    result_roles = {}
    for role in ("server", "admin"):
        role_expected = expected[role]
        if not role_expected:
            errors.append(f"no {role} Python entries in manifest")
        names = {name[:-3] for name in role_expected}
        details = []
        for filename, digest in sorted(role_expected.items()):
            path = roots[role] / filename
            status = "missing"
            unresolved: list[str] = []
            if path.is_symlink() or not path.is_file():
                errors.append(f"missing or symlinked source: {role}/{filename}")
            else:
                try:
                    payload = path.read_bytes()
                    got = hashlib.sha256(payload).hexdigest()
                    if got != digest:
                        errors.append(f"checksum mismatch: {role}/{filename}")
                        status = "checksum_mismatch"
                    else:
                        status = "verified"
                        try:
                            tree = ast.parse(payload.decode("utf-8-sig"), filename=filename)
                            unresolved = sorted(_source_imports(tree) - names)
                            for name in unresolved:
                                warnings.append(f"unresolved role-local import: {role}/{filename} -> {name}")
                        except (SyntaxError, UnicodeError):
                            status = "invalid_syntax"
                            errors.append(f"Python syntax/decode failure: {role}/{filename}")
                except OSError:
                    errors.append(f"unreadable source: {role}/{filename}")
                    status = "unreadable"
            details.append({"file": filename, "status": status,
                            "unresolved_role_local_imports": unresolved})
        result_roles[role] = {
            "expected": len(role_expected),
            "verified": sum(item["status"] == "verified" for item in details),
            "files": details,
        }

    common = set(expected["server"]) & set(expected["admin"])
    divergent = sorted(
        name for name in common
        if expected["server"][name] != expected["admin"][name]
    )
    return {
        "passed": not errors,
        "errors": errors,
        "warnings": warnings,
        "roles": result_roles,
        "shared_modules": len(common),
        "divergent_shared_modules": divergent,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--public-dir", type=Path, required=True)
    parser.add_argument("--admin-dir", type=Path, required=True)
    parser.add_argument("--report-json", type=Path)
    parser.add_argument("--strict-imports", action="store_true")
    args = parser.parse_args()
    result = inspect(args.manifest, args.public_dir, args.admin_dir)
    if args.strict_imports and result["warnings"]:
        result["passed"] = False
        result["errors"].append("strict role-local import validation failed")
    if args.report_json:
        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        args.report_json.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    for role in ("server", "admin"):
        item = result["roles"].get(role, {})
        print(f"{role}: {item.get('verified', 0)}/{item.get('expected', 0)} source hashes verified")
    print(f"shared modules with role differences: {len(result['divergent_shared_modules'])}")
    for entry in result["warnings"]:
        print(f"WARNING: {entry}")
    for entry in result["errors"]:
        print(f"ERROR: {entry}")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
