"""Build the V4Y-055 r3 candidate from the pinned live baseline (V4Y-056 R13).

Run with: python -I -B tools/build_candidate.py   (from the package folder)

Inputs (pinned, never fetched here):
  live-baseline/index.html        server/index.html after V4Y-056 R13 (594628d3...)
  live-baseline/assets/*.js       the 53 live v4y056 r4 chunks, each checked against
                                  live-baseline/r13-candidate.sha256 (the R13 payload manifest)

Output:
  candidate/index.html
  candidate/assets/*-v4y055-r3.js  the same 53 chunks under new names, with two
                                   chunks patched:
    - paymentApi: one safe retry of create-order / place-cod-order /
      verify-payment when the reply is not JSON or the connection drops,
      plus clearer messages (same behaviour as src/services/paymentApi.ts
      on branch agent/fix-razorpay-first-load-category-icons).
    - Home: relevant icons for every homepage section instead of the Gem
      fallback, including the live-only Health & Nutrition section.

Every live chunk is cached by browsers and Cloudflare as immutable, and every
chunk imports the main bundle by name, so the whole set is re-suffixed (the
same approach as the v4y046 release). Old files stay on the host for pages
that are already open.
"""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
BASE = HERE / "live-baseline"
OUT = HERE / "candidate"
OLD_SUFFIX = "-v4y056-storefront-hardening-r4.js"
NEW_SUFFIX = "-v4y055-r3.js"
INDEX_SHA = "594628d38bace652d3a32cec86f5e2ae2ec779142f8bfe84bdfdde5c353c04cd"
CHUNK_COUNT = 53


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fail(message: str) -> None:
    print(f"STOP: {message}", file=sys.stderr)
    raise SystemExit(1)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        fail(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new)


# ---------------------------------------------------------------- paymentApi
PAYMENT_OLD = (
    'async function u(a,e,t,r=fetch){try{const n={"Content-Type":"application/json",...t?{"Idempotency-Key":t}:{}};'
    'return await C(a,{method:"POST",headers:n,body:JSON.stringify(e)},r)}catch(n){throw n instanceof P?'
    'new o(n.message,n.code,n.status):new o("The secure checkout server is unavailable. Please try again.",'
    '"server_unavailable")}}function _(a,e,t){return u("/api/create-order",a,e,t)}function O(a,e,t){'
    'return u("/api/place-cod-order",a,e,t)}function g(a,e,t){return u("/api/verify-payment",'
    '{...a,styleDashOrderId:e},void 0,t)}'
)
# Same request as before (u1 is the old u), then one retry for replies that
# never came from the server as JSON. The server dedupes create-order and COD
# by Idempotency-Key and finalizes a payment exactly once, so a retry cannot
# create a second order or charge.
PAYMENT_NEW = (
    'async function u1(a,e,t,r){try{const n={"Content-Type":"application/json",...t?{"Idempotency-Key":t}:{}};'
    'return await C(a,{method:"POST",headers:n,body:JSON.stringify(e)},r)}catch(n){throw n instanceof P?'
    'new o(n.message,n.code,n.status):new o("The secure checkout server is unavailable. Please try again.",'
    '"server_unavailable")}}'
    'const v4yT=new Set(["invalid_response","server_unavailable"]);'
    'async function u(a,e,t,r=fetch){try{return await u1(a,e,t,r)}catch(n){'
    'if(!(n instanceof o)||!v4yT.has(n.code))throw n;'
    'await new Promise(s=>setTimeout(s,700));return u1(a,e,t,r)}}'
    'const v4yS=s=>s?` (HTTP ${s})`:"";'
    'const v4yM=(n,m)=>{if(n instanceof o&&v4yT.has(n.code))throw new o(m(n.status),n.code,n.status);throw n};'
    'function _(a,e,t){return u("/api/create-order",a,e,t).catch(n=>v4yM(n,s=>'
    '`Secure checkout could not start${v4yS(s)}. Payment was not taken. Please try again.`))}'
    'function O(a,e,t){return u("/api/place-cod-order",a,e,t).catch(n=>v4yM(n,s=>'
    '`We could not confirm your order${v4yS(s)}. Check Your Orders before trying again.`))}'
    'function g(a,e,t){return u("/api/verify-payment",{...a,styleDashOrderId:e},void 0,t).catch(n=>v4yM(n,s=>'
    '`Your payment was sent, but we could not confirm it yet${v4yS(s)}. '
    'Do not pay again. Check Your Orders in a few minutes.`))}'
)

# ---------------------------------------------------------------- Home icons
LICENSE = (
    "/**\n * @license lucide-react v0.428.0 - ISC\n *\n * This source code is licensed under the ISC license.\n"
    " * See the LICENSE file in the root directory of this source tree.\n */"
)
GEM_DEF = (
    'const $=h("Gem",[["path",{d:"M6 3h12l4 6-10 13L2 9Z",key:"1pcd5k"}],'
    '["path",{d:"M11 3 8 9l4 13 4-13-3-6",key:"1fcu3u"}],["path",{d:"M2 9h20",key:"16fsjt"}]]);'
)
# Icon nodes copied from lucide-react 0.428.0 (the version the live bundle was
# built with; see the license banners in the chunk).
NEW_ICONS = (
    'const v4yShirt=h("Shirt",[["path",{d:"M20.38 3.46 16 2a4 4 0 0 1-8 0L3.62 3.46a2 2 0 0 0-1.34 2.23l.58 3.47a1 1 0 0 0 .99.84H6v10c0 1.1.9 2 2 2h8a2 2 0 0 0 2-2V10h2.15a1 1 0 0 0 .99-.84l.58-3.47a2 2 0 0 0-1.34-2.23z",key:"1wgbhj"}]]);'
    'const v4yFootprints=h("Footprints",[["path",{d:"M4 16v-2.38C4 11.5 2.97 10.5 3 8c.03-2.72 1.49-6 4.5-6C9.37 2 10 3.8 10 5.5c0 3.11-2 5.66-2 8.68V16a2 2 0 1 1-4 0Z",key:"1dudjm"}],["path",{d:"M20 20v-2.38c0-2.12 1.03-3.12 1-5.62-.03-2.72-1.49-6-4.5-6C14.63 6 14 7.8 14 9.5c0 3.11 2 5.66 2 8.68V20a2 2 0 1 0 4 0Z",key:"l2t8xc"}],["path",{d:"M16 17h4",key:"1dejxt"}],["path",{d:"M4 13h4",key:"1bwh8b"}]]);'
    'const v4yWatch=h("Watch",[["circle",{cx:"12",cy:"12",r:"6",key:"1vlfrh"}],["polyline",{points:"12 10 12 12 13 13",key:"19dquz"}],["path",{d:"m16.13 7.66-.81-4.05a2 2 0 0 0-2-1.61h-2.68a2 2 0 0 0-2 1.61l-.78 4.05",key:"18k57s"}],["path",{d:"m7.88 16.36.8 4a2 2 0 0 0 2 1.61h2.72a2 2 0 0 0 2-1.61l.81-4.05",key:"16ny36"}]]);'
    'const v4ySmartphone=h("Smartphone",[["rect",{width:"14",height:"20",x:"5",y:"2",rx:"2",ry:"2",key:"1yt0o3"}],["path",{d:"M12 18h.01",key:"mhygvu"}]]);'
    'const v4yGift=h("Gift",[["rect",{x:"3",y:"8",width:"18",height:"4",rx:"1",key:"bkv52"}],["path",{d:"M12 8v13",key:"1c76mn"}],["path",{d:"M19 12v7a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2v-7",key:"6wjy6b"}],["path",{d:"M7.5 8a2.5 2.5 0 0 1 0-5A4.8 8 0 0 1 12 8a4.8 8 0 0 1 4.5-5 2.5 2.5 0 0 1 0 5",key:"1ihvrl"}]]);'
    'const v4ySofa=h("Sofa",[["path",{d:"M20 9V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v3",key:"1dgpiv"}],["path",{d:"M2 16a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-5a2 2 0 0 0-4 0v1.5a.5.5 0 0 1-.5.5h-11a.5.5 0 0 1-.5-.5V11a2 2 0 0 0-4 0z",key:"xacw8m"}],["path",{d:"M4 18v2",key:"jwo5n2"}],["path",{d:"M20 18v2",key:"1ar1qi"}],["path",{d:"M12 4v9",key:"oqhhn3"}]]);'
    'const v4yHeartPulse=h("HeartPulse",[["path",{d:"M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z",key:"c3ymky"}],["path",{d:"M3.22 12H9.5l.5-1 2 4.5 2-7 1.5 3.5h5.27",key:"1uw2ng"}]]);'
)
ICON_FN_OLD = (
    'J=r=>r==="express"?e.jsx(q,{className:"h-5 w-5"}):r==="new"||r==="beauty"?e.jsx(z,{className:"h-5 w-5"}):'
    'r==="trending"?e.jsx(G,{className:"h-5 w-5"}):r==="under499"?e.jsx(K,{className:"h-5 w-5"}):'
    'r==="women"?e.jsx(Z,{className:"h-5 w-5"}):r==="men"?e.jsx(Y,{className:"h-5 w-5"}):'
    'e.jsx($,{className:"h-5 w-5"}),'
)
# q=Zap z=Sparkles G=TrendingUp K=WalletCards Z=UsersRound Y=UserRound (as before).
# Unknown future ids fall back to Sparkles, never the Gem.
ICON_FN_NEW = (
    'v4yIcons={express:q,new:z,trending:G,under499:K,women:Z,men:Y,clothing:v4yShirt,footwear:v4yFootprints,'
    'accessories:v4yWatch,beauty:z,electronics:v4ySmartphone,gifts:v4yGift,home:v4ySofa,nutrition:v4yHeartPulse},'
    'J=r=>e.jsx(Object.prototype.hasOwnProperty.call(v4yIcons,r)?v4yIcons[r]:z,{className:"h-5 w-5","aria-hidden":"true"}),'
)


def main() -> None:
    manifest = {}
    for line in (BASE / "r13-candidate.sha256").read_text(encoding="utf-8").splitlines():
        digest, path = line[:64], line[66:]
        manifest[path] = digest

    index = (BASE / "index.html").read_bytes()
    if sha(index) != INDEX_SHA:
        fail("live-baseline/index.html is not the pinned V4Y-056 R13 index")
    if manifest.get("server/index.html") != INDEX_SHA:
        fail("R13 payload manifest does not pin the same index.html")

    chunks = sorted((BASE / "assets").glob(f"*{OLD_SUFFIX}"), key=lambda p: p.name)
    if len(chunks) != CHUNK_COUNT:
        fail(f"expected {CHUNK_COUNT} baseline chunks, found {len(chunks)}")
    listed = sorted(p for p in manifest if p.startswith("server/assets/") and p.endswith(OLD_SUFFIX))
    if [f"server/assets/{c.name}" for c in chunks] != listed:
        fail("baseline chunk files differ from the R13 manifest rows")

    out_assets = OUT / "assets"
    out_assets.mkdir(parents=True, exist_ok=True)
    for stale in out_assets.glob("*"):
        stale.unlink()

    patched = {"paymentApi": False, "Home": False}
    for chunk in chunks:
        data = chunk.read_bytes()
        if sha(data) != manifest[f"server/assets/{chunk.name}"]:
            fail(f"{chunk.name} does not match its manifest row")
        text = data.decode("utf-8")
        text = text.replace(OLD_SUFFIX, NEW_SUFFIX)
        if chunk.name.startswith("paymentApi-"):
            text = replace_once(text, PAYMENT_OLD, PAYMENT_NEW, "paymentApi request functions")
            patched["paymentApi"] = True
        if chunk.name.startswith("Home-"):
            text = replace_once(text, GEM_DEF, GEM_DEF + LICENSE + NEW_ICONS, "Home Gem definition")
            text = replace_once(text, ICON_FN_OLD, ICON_FN_NEW, "Home section icon function")
            patched["Home"] = True
        if OLD_SUFFIX in text or "v4y046" in text or "v4y056" in text:
            fail(f"{chunk.name} still references the old suffix")
        (out_assets / chunk.name.replace(OLD_SUFFIX, NEW_SUFFIX)).write_bytes(text.encode("utf-8"))
    if not all(patched.values()):
        fail(f"not every chunk was patched: {patched}")

    new_index = replace_once(
        index.decode("utf-8"),
        f'src="/assets/index-MMTPd8z_{OLD_SUFFIX}"',
        f'src="/assets/index-MMTPd8z_{NEW_SUFFIX}"',
        "index.html main bundle",
    )
    (OUT / "index.html").write_bytes(new_index.encode("utf-8"))

    # Every relative import in every new chunk must resolve inside the new set.
    names = {p.name for p in out_assets.iterdir()}
    for path in out_assets.iterdir():
        for ref in re.findall(r'"\./([^"]+\.js)"', path.read_text(encoding="utf-8")):
            if ref not in names:
                fail(f"{path.name} imports missing ./{ref}")
        for ref in re.findall(r'"assets/([^"]+\.js)"', path.read_text(encoding="utf-8")):
            if ref not in names:
                fail(f"{path.name} preloads missing assets/{ref}")

    wk_src = HERE / "assetlinks.json"
    if not wk_src.is_file():
        fail("assetlinks.json (the Play Console Digital Asset Links file) is missing from the package folder")
    (OUT / "assetlinks.json").write_bytes(wk_src.read_bytes())
    with open(OUT / "SHA256SUMS", "w", encoding="utf-8", newline="\n") as sums:
        sums.write(f"{sha((OUT / 'index.html').read_bytes())}  index.html\n")
        sums.write(f"{sha((OUT / 'assetlinks.json').read_bytes())}  assetlinks.json\n")
        for path in sorted(out_assets.iterdir(), key=lambda p: p.name):
            sums.write(f"{sha(path.read_bytes())}  assets/{path.name}\n")
    print(f"candidate built: index.html + {len(names)} chunks; patched paymentApi and Home")


if __name__ == "__main__":
    main()
