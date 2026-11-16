# Frontend build-vs-production parity — 2026-11-16

## Build verification (isolated Windows sync worktree)

- 370 packages installed offline from existing npm cache with scripts disabled.
- TypeScript typecheck: **PASS**
- Vitest frontend: **192/192 tests PASS** across 34 files.
- Vite 5 build: **PASS**, 1,675 modules transformed.
- Build output generated in ignored dist/ only; nothing deployed.
- The five Vibe4You public pages and Android assetlinks in the source
  are individually byte-for-byte equal to their live production versions.
- Git attributes for those exact files were moved to ROOT .gitattributes,
  because attributes inside public/ would themselves be served by Vite.

## Manifest comparison against active Ubuntu production

- Active integrity manifest SHA-256:
  ec13b4f28f99b26f3cf468412d77a651b8596decc1cb5afb1012170bac11a126
- Built dist total files: **66**
- Byte-identical files present in live manifest: **14**
- Same path but different bytes: **1**, specifically server/index.html
- Built dist files not present in live production manifest: **51**
- Built asset chunks: **56**
- Versioned asset files recorded in live manifest: **1388**
  (includes historic/unused assets; this number is NOT a count of
  currently loaded modules).
- Live asset paths absent from local dist: **1383**

The live index currently selects the main bundle:
  /assets/index-MMTPd8z_-v4y-search-v2-r2.js

The isolated source build selects:
  /assets/index-BE461cSq.js

Production also includes separately deployed scripts and overlays,
including a review-experience overlay, seller-label overlay, and
GA4 ecommerce overlay, absent from the current old source build.

**Conclusion:** the old GitHub/Vite source builds successfully but is
NOT byte-identical to the live storefront. Do not deploy it as a replacement
for Ubuntu production or claim full Windows/main/production synchronization.

## Existing tooling warning

The existing package.json contains duplicate 'overrides' keys with
identical current entries. Vite warns about the duplicate. We have
not changed dependency policy as part of source alignment.

## Recommended remaining work

1. Identify the newest complete source for active Search V2 R2,
   review-experience UI, seller-label, category, SEO and GA4 overlays.
2. Integrate those assets into a reproducible build without changing
   business behavior or checkout security.
3. Require exact build asset hashes and full checkout/browser regressions
   before contemplating a production deployment.
4. Keep PR #180 as draft until the source changes can build the deployed
   application and guarded parity checks pass.

All comparisons here were read-only for Ubuntu; production files,
billing records, and customer data were not changed.

## November 16 live runtime capture

An additional exact-byte frontend-runtime/ capsule now captures 133 public
site/PWA artifacts, verified against the live Ubuntu server. This includes
the active Search V2 R2 entry JS, direct overlay CSS/JS, potential dynamic
Vite asset dependencies and PWA icons/service worker. 123 assets match
the deployed integrity manifest; 10 publicly served files do not appear
in that manifest but matched both nonroot filesystem and HTTP body hashes.
This fixes our baseline *visibility*, not production's manifest coverage
or the actual React source/build reproducibility.

The files remain **deployed artifacts, not editable application source**.
Do not substitute them for authored Vite src code or deploy this snapshot
without a separate guarded build and owner-approved release.

## Editable Search V2 R2 source recovery

The source from StyleDash-search-v2-relevance-r2-20261114 has been
restored (11 TS/TSX changes) and 225/225 Vitest tests pass.
The isolated Vite build now matches **all 61 files** of that
archived candidate's *prepatch* dist/ by name and SHA-256, plus
five extra production public pages/assets.

This does NOT contradict the earlier production mismatch: the
active live Search V2 R2 bundle has postprocessed filenames and code.
Those compiled assets, CSS and overlays remain separate from the
reconstructed editable build. No one should deploy dist/ as-is.
See SEARCH_V2_EDITABLE_SOURCE_RECOVERY.md and
search-v2-source-build-proof.json for exact SHA evidence.
