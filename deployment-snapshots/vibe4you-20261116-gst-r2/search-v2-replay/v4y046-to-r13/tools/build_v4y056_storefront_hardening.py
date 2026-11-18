#!/usr/bin/env python3
"""Build the full V4Y-056 immutable graph from the exact live V4Y-046 graph."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


OLD_MAIN = "index-MMTPd8z_-v4y046-category-social-r1.js"
OLD_PRODUCTS = "Products-DSTsw2bW-v4y046-category-social-r1.js"
OLD_SUFFIX = "-v4y046-category-social-r1.js"
NEW_SUFFIX = "-v4y056-storefront-hardening-r4.js"
NEW_MAIN = "index-MMTPd8z_" + NEW_SUFFIX
NEW_PRODUCTS = "Products-DSTsw2bW" + NEW_SUFFIX

EXPECTED = {
    "index.html": "e9e904068c4a6e3589862363d082f72efb704cb0e80530ae8c31b0c70d6d58f3",
    OLD_MAIN: "ae7a452633379c3dfe982fa30b9ced10863bfb2f6855ece94204777f97f00f9d",
    OLD_PRODUCTS: "d7726a76bb8858530f0be369fc388b19d0f4f0b86f465508a5305c0169d1a225",
    "serve.py": "776207b5903429ef51320ef678147964d762732d72ff8d8aef322bd85b9bf2cc",
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def pinned(path: Path, expected: str) -> bytes:
    data = path.read_bytes()
    actual = digest(data)
    if actual != expected:
        raise SystemExit(f"hash mismatch for {path}: {actual} != {expected}")
    return data


def replace_once(data: bytes, old: str, new: str, label: str) -> bytes:
    before = old.encode()
    count = data.count(before)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    return data.replace(before, new.encode(), 1)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live-baseline", type=Path, required=True)
    parser.add_argument("--patched-backend", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    baseline = args.live_baseline.resolve()
    output = args.output.resolve()
    assets = output / "server" / "assets"
    assets.mkdir(parents=True, exist_ok=False)

    index = pinned(baseline / "index.html", EXPECTED["index.html"])
    main_js = pinned(baseline / "assets" / OLD_MAIN, EXPECTED[OLD_MAIN])
    products_js = pinned(baseline / "assets" / OLD_PRODUCTS, EXPECTED[OLD_PRODUCTS])
    backend = pinned(args.patched_backend.resolve(), EXPECTED["serve.py"])

    manifest = {}
    for line in (baseline / "manifest.sha256").read_text(encoding="utf-8").splitlines():
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        manifest[parts[1].replace("\\", "/")] = parts[0].lower()

    graph = sorted((baseline / "assets").glob(f"*{OLD_SUFFIX}"))
    if len(graph) != 53:
        raise SystemExit(f"expected exact 53-file live graph, found {len(graph)}")
    for source in graph:
        manifest_key = f"server/assets/{source.name}"
        expected = manifest.get(manifest_key)
        if expected is None:
            raise SystemExit(f"live manifest is missing {manifest_key}")
        pinned(source, expected)

    main_js = main_js.replace(OLD_SUFFIX.encode(), NEW_SUFFIX.encode())
    main_js = replace_once(
        main_js,
        "async getAllProducts(){Lt||(Lt=ks(()=>Qr.getAvailability()));const e=await hi(),[t,n]=await Promise.all([Q0(e),Ku(e)]);return qu(t,n)},async getStoreProducts",
        "async getAllProducts(){Lt||(Lt=ks(()=>Qr.getAvailability()));const e=await hi();return Q0(e)},async withReviewSummaries(e){return qu(e,await Ku(e))},async getStoreProducts",
        "page-scoped review repository",
    )

    products_js = products_js.replace(OLD_SUFFIX.encode(), NEW_SUFFIX.encode())
    products_js = replace_once(
        products_js,
        "[E,S]=c.useState(!1),m=a.get",
        "[pageProducts,setPageProducts]=c.useState([]),[E,S]=c.useState(!1),m=a.get",
        "visible page state",
    )
    products_js = replace_once(
        products_js,
        'U=se(k,24,"page",!b,"catalogue-products");return e.jsxs',
        'U=se(k,24,"page",!b,"catalogue-products"),pageKey=U.items.map(t=>t.id).join("|");return c.useEffect(()=>{let t=!1;const n=U.items;return setPageProducts(n),b||n.length===0?()=>{t=!0}:(Q.withReviewSummaries(n).then(u=>{t||setPageProducts(u)}),()=>{t=!0})},[b,pageKey]),e.jsxs',
        "page-scoped review effect",
    )
    products_js = replace_once(
        products_js,
        'e.jsx("p",{className:"text-xs text-neutral-500 mt-1",children:s?',
        'e.jsx("p",{className:"text-xs text-neutral-500 mt-1",role:"status",children:b?e.jsx(e.Fragment,{children:"Loading available products..."}):s?',
        "catalogue loading message",
    )
    products_js = replace_once(
        products_js,
        "children:U.items.map((t,n)=>",
        "children:pageProducts.map((t,n)=>",
        "visible page rendering",
    )
    index = replace_once(index, f"/assets/{OLD_MAIN}", f"/assets/{NEW_MAIN}", "index entry")

    (output / "server" / "index.html").write_bytes(index)
    for source in graph:
        target_name = source.name.removesuffix(OLD_SUFFIX) + NEW_SUFFIX
        data = source.read_bytes().replace(OLD_SUFFIX.encode(), NEW_SUFFIX.encode())
        if source.name == OLD_MAIN:
            data = main_js
        elif source.name == OLD_PRODUCTS:
            data = products_js
        (assets / target_name).write_bytes(data)
    (output / "server" / "serve.py").write_bytes(backend)
    systemd = output / "systemd"
    systemd.mkdir()
    (systemd / "zz-public-origin.conf").write_text(
        "[Service]\n"
        'Environment="STYLEDASH_PUBLIC_ORIGIN=https://vibe4you.in"\n'
        'Environment="STYLEDASH_TRUST_LOOPBACK_PROXY=1"\n',
        encoding="utf-8",
        newline="\n",
    )

    rows = []
    for path in sorted(p for p in output.rglob("*") if p.is_file()):
        rows.append(f"{digest(path.read_bytes())}  {path.relative_to(output).as_posix()}")
    (output / "candidate.sha256").write_text("\n".join(rows) + "\n", encoding="ascii", newline="\n")
    print(f"V4Y056_CANDIDATE_BUILT={output}")
    for row in rows:
        print(row)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
