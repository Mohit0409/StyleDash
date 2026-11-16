# Editable Search V2 R2 source recovery — 2026-11-16

## Verified lineage

Original Windows candidate:
StyleDash-search-v2-relevance-r2-20261114

This Windows worktree was NOT a Git repository. Its guarded R2 release
payload includes exact SHA-256 matches to the active Ubuntu production
Search V2 R2 homepage, main JavaScript entrypoint and Products JS chunk.
The release manifest identified it as V4Y-SEARCH-V2-RELEVANCE-R2-20261114.

The candidate contains 11 source changes relative to the isolated
GitHub source-alignment branch: six modified existing TypeScript/TSX
files and five new source/tests, including searchEngine.ts,
localSearch.ts and dedicated relevance tests. All eleven are copied
with their original source-byte digests recorded in
search-v2-source-build-proof.json.

## Reproducible intermediate build

TypeScript checks: PASS.
Vitest frontend tests: 225/225 PASS in 37 test modules
(previously 192/192 in 34 modules).
Vite build: PASS (no payment catalog generation).
All 61 files in the archived candidate's Vite dist/ are exactly
reproduced by the isolated source branch's dist/ (61/61 name+SHA),
plus five public account/verification/assetlinks files added earlier
from the production static-source recovery.

Source/build verification:
scripts/verify_search_v2_source_build.py
- default: validate all 11 recovered source file hashes
- --dist: validate all 66 intermediate generated files and names

Four offline Python tests guard the source proof and unsafe paths.
The checkout retry tests verify only one retry on transient non-JSON
errors, stable Idempotency-Key reuse for create-order/COD, and
no optimistic payment confirmation if verification is unavailable.
These were imported from the archived candidate and all 225
front-end tests passed; independent payment backend behavior must
still be checked before a live deploy.

## Important distinction — NOT the deployed frontend build

The archived candidate's final, guarded R2 release payload contains
postprocessed versioned JS assets and a modified homepage matching
the current live server. Those files are tracked in the exact-byte
frontend-runtime/ reference, and the three selected QA payload
checksums are recorded in search-v2-source-build-proof.json.

However the base Vite output still uses a different entrypoint
(index-D85cLADH.js) than the live versioned Search V2 R2
(index-MMTPd8z_-v4y-search-v2-r2.js), which has additional
postprocessed assets and separately deployed marketing/review/cache
overlays. The compiled release transformation is not yet
reconstructed as an auditable source-build step.

Do not replace Ubuntu production with the intermediate dist or
promote this PR to GitHub main yet.

## Production safety

No production service, order, customer, invoice, tax classification,
payment or backup was modified. The source imports are confined to
StyleDash-production-sync-20261116, preserving the owner's original
Windows checkout with 68 tracked edits.
