# Frontend overlay and PWA source integration — 2026-11-17

## Result

The independent public frontend layer is now represented by a pinned,
offline-only source map and fail-closed assembler. It covers 25 exact live
public files without treating the compiled Search V2 R2 application as
editable React source:

- 14 byte-exact standalone JS/CSS overlays: marketing, Ads/GA4, product
  assurance/gallery/labels, account privacy, category/customer/health cache,
  mobile UI, review-photo experience and social buttons.
- 2 compiled Vite CSS references (`index-BITtbtpM.css` and
  `Home-bVIr0YEJ.css`). These remain compiled acceptance artifacts; authored
  CSS source parity is not established.
- 9 static PWA outputs: service worker, offline fallback, app manifest,
  installer JS/CSS and four icons. The same bytes are produced by the
  hash-pinned historical PWA builder at Vibe4You commit
  `5393594e502b7cc79e74aef7be4e8de4d3a37117`.

The source map is
`deployment-targets/vibe4you-20261116-r2/frontend-overlay-source-map.json`
(SHA-256 `7ef85f1890ce0d69fa742d0495bd29e401f6aea9d52d4919c066135ae89fa1ea`).
Its executable inputs are repository-local paths in the exact-byte frontend
capsule. Historical workspace paths are provenance evidence only and are not
assembly dependencies.

## Corrected PWA capture

The service worker caches `/vibe4you-app/offline.html`; the earlier capsule
omitted that file. Read-only production disk and public HTTPS checks both
returned SHA-256
`8a2c83a487d84927107f641e5fe8d164a01c0e45f7ce9f0a3209eab863c82677`
for the 1,697-byte page. The corrected capsule therefore contains 134 files:
123 production-integrity-manifest entries and 11 separately disk/HTTP-verified
public files.

## Offline assembly boundary

`scripts/assemble_pinned_frontend_overlays.py` validates the 134-file capsule,
the pinned overlay map, all 25 source hashes and sizes, source classifications,
and the complete PWA output graph. Optional staging is restricted to a new
directory under the operating-system temporary directory. Generated
`server/index.html`, the Search V2 R2 main bundle, private runtime data and all
Admin/backend paths are denied.

Validation:

```text
python scripts/verify_pinned_frontend_runtime.py
python scripts/assemble_pinned_frontend_overlays.py --check
python -m unittest server.tests.test_active_frontend_runtime server.tests.test_pinned_frontend_overlay_assembly
```

The focused suite has 16 passing tests, including byte drift, map tampering,
path traversal, external archive dependency, output destination and exact
temporary staging checks.

## Remaining boundary

This tranche makes the independent layer inventory and byte assembly
reproducible; it does not make the complete storefront a reproducible React
build. Typed equivalents/integration for the independently installed overlays,
authored source for both compiled CSS files, browser checkout/review-photo E2E,
and an owner-approved guarded release design are still required. Nothing in
this tranche changes production, customer/payment data, the old Termux
installer, or the original dirty Windows checkout.
