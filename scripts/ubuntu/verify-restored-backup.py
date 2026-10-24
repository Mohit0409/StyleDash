#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import sqlite3
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify an isolated Vibe4You backup restore without touching production."
    )
    parser.add_argument("source", type=Path, help="Read-only backup source directory")
    parser.add_argument("restored", type=Path, help="Isolated restored directory")
    return parser.parse_args()


def file_map(root: Path) -> dict[str, Path]:
    return {
        path.relative_to(root).as_posix(): path
        for path in root.rglob("*")
        if path.is_file()
    }


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sqlite_integrity(db_path: Path) -> str:
    uri = db_path.resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    try:
        return str(connection.execute("PRAGMA integrity_check").fetchone()[0])
    finally:
        connection.close()


def main() -> int:
    args = parse_args()
    source = args.source.resolve()
    restored = args.restored.resolve()

    if not source.is_dir():
        raise SystemExit(f"Source backup directory does not exist: {source}")
    if not restored.is_dir():
        raise SystemExit(f"Restored directory does not exist: {restored}")

    source_files = file_map(source)
    restored_files = file_map(restored)

    missing = sorted(set(source_files) - set(restored_files))
    unexpected = sorted(set(restored_files) - set(source_files))
    mismatched = []

    for relative_path in sorted(set(source_files) & set(restored_files)):
        if sha256(source_files[relative_path]) != sha256(restored_files[relative_path]):
            mismatched.append(relative_path)

    source_images = sum(
        1 for path in (source / "product-images").rglob("*") if path.is_file()
    ) if (source / "product-images").is_dir() else 0
    restored_images = sum(
        1 for path in (restored / "product-images").rglob("*") if path.is_file()
    ) if (restored / "product-images").is_dir() else 0

    restored_db = restored / "styledash.db"
    if not restored_db.is_file():
        print("RESTORE_VERIFY=FAIL")
        print("reason=missing_styledash_db")
        return 1

    integrity = sqlite_integrity(restored_db)

    print(f"source_files={len(source_files)}")
    print(f"restored_files={len(restored_files)}")
    print(f"source_product_images={source_images}")
    print(f"restored_product_images={restored_images}")
    print(f"missing_files={len(missing)}")
    print(f"unexpected_files={len(unexpected)}")
    print(f"hash_mismatches={len(mismatched)}")
    print(f"sqlite_integrity={integrity}")

    passed = (
        not missing
        and not unexpected
        and not mismatched
        and source_images == restored_images
        and integrity == "ok"
    )
    print("RESTORE_VERIFY=" + ("PASS" if passed else "FAIL"))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())