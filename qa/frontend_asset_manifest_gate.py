"""Review-only guard for packaged production HTML and its asset checksum manifest.

Checks an *offline artifact*, never contacts a website or modifies deployment files.
This does not establish a complete release or validate protected server-side files.
"""
from __future__ import annotations

import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path, PurePosixPath
import re
from urllib.parse import urlsplit


class StaticAssetParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.references: list[str] = []
        self.module_scripts: list[str] = []
        self.stylesheets: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        if tag == "script" and attr.get("src"):
            self.references.append(attr["src"])
            if (attr.get("type") or "").casefold() == "module":
                self.module_scripts.append(attr["src"])
        if tag == "link" and attr.get("href"):
            relationship = (attr.get("rel") or "").casefold().split()
            if {"icon", "apple-touch-icon", "manifest", "stylesheet"} & set(relationship):
                self.references.append(attr["href"])
            if "stylesheet" in relationship:
                self.stylesheets.append(attr["href"])


def _manifest_mapping(raw: str) -> tuple[dict[str, str], list[str]]:
    entries: dict[str, str] = {}
    problems: list[str] = []
    for line_no, line in enumerate(raw.splitlines(), 1):
        if "  " not in line:
            problems.append(f"malformed_manifest_line_{line_no}")
            continue
        sha, path = line.split("  ", 1)
        rel = PurePosixPath(path)
        if (
            not re.fullmatch(r"[0-9a-f]{64}", sha)
            or not path
            or path.startswith("/")
            or ".." in rel.parts
            or chr(92) in path
        ):
            problems.append(f"invalid_manifest_entry_{line_no}")
            continue
        if path in entries:
            problems.append(f"duplicate_manifest_entry_{line_no}")
        entries[path] = sha
    return entries, problems


def _same_origin_manifest_path(link: str) -> str | None:
    if not link.startswith("/") or link.startswith("//"):
        return None
    parsed = urlsplit(link)
    path = parsed.path
    parts = PurePosixPath(path).parts
    if not path or ".." in parts or chr(92) in path:
        raise ValueError("Unsafe local asset path")
    return "server/" + path.lstrip("/")


def inspect(
    html: bytes,
    manifest: bytes,
    required_script: str | None = None,
    checked_asset_root: Path | None = None,
) -> dict:
    issues: list[str] = []
    html_text = html.decode("utf-8-sig")
    manifest_text = manifest.decode("utf-8-sig")
    entries, malformed = _manifest_mapping(manifest_text)
    issues.extend(malformed)
    # A literal PowerShell backtick+n between HEAD script tags causes the
    # HTML5 parser to close the HEAD and move following nodes into the BODY.
    if chr(96) + "n" in html_text:
        issues.append("literal_backtick_n_in_html")
    match = re.search(r"<head\b[^>]*>(.*?)</head\s*>", html_text, re.I | re.S)
    if match is None:
        issues.append("head_element_missing")
        head = ""
    else:
        head = match.group(1)
    full_parser = StaticAssetParser()
    head_parser = StaticAssetParser()
    full_parser.feed(html_text)
    head_parser.feed(head)
    references = sorted(set(full_parser.references))
    local_refs: list[str] = []
    for reference in references:
        try:
            target = _same_origin_manifest_path(reference)
        except ValueError:
            issues.append("unsafe_asset_reference")
            continue
        if target is None:
            continue
        local_refs.append(target)
        if target not in entries:
            issues.append("unmanifested_asset:" + target)
    if not head_parser.module_scripts:
        issues.append("module_script_missing_from_head")
    if not any(PurePosixPath(urlsplit(s).path).name.startswith("index-") for s in head_parser.stylesheets):
        issues.append("main_stylesheet_missing_from_head")
    if required_script and required_script not in references:
        issues.append("required_script_not_referenced:" + required_script)
    if "server/index.html" not in entries:
        issues.append("html_not_in_manifest")
    elif entries["server/index.html"] != hashlib.sha256(html).hexdigest():
        issues.append("html_checksum_mismatch")
    asset_bytes_verified = 0
    if checked_asset_root is not None:
        for path in sorted(set(local_refs)):
            local = checked_asset_root / path.removeprefix("server/")
            if local.is_symlink():
                issues.append("local_asset_symlink:" + path)
                continue
            if local.is_file():
                asset_bytes_verified += 1
                if entries.get(path) != hashlib.sha256(local.read_bytes()).hexdigest():
                    issues.append("local_asset_checksum_mismatch:" + path)
    return {
        "passed": not issues,
        "problems": sorted(set(issues)),
        "manifest_entries": len(entries),
        "local_asset_references": len(set(local_refs)),
        "local_asset_bytes_verified": asset_bytes_verified,
        "head_module_scripts": len(head_parser.module_scripts),
        "head_stylesheets": len(head_parser.stylesheets),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline production HTML + manifest preflight, no mutations")
    parser.add_argument("--html", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--required-script")
    parser.add_argument("--asset-root", type=Path)
    parser.add_argument("--report-json", type=Path)
    args = parser.parse_args()
    result = inspect(
        args.html.read_bytes(), args.manifest.read_bytes(),
        required_script=args.required_script,
        checked_asset_root=args.asset_root,
    )
    output = json.dumps(result,indent=2)
    print(output)
    if args.report_json is not None:
        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        args.report_json.write_text(output + "\n", encoding="utf-8")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

