# Vibe4You deployed-code baseline - 16 November 2026

Reference: Active Ubuntu production after owner-approved GST delivery R2.
Production integrity manifest SHA-256:
ec13b4f28f99b26f3cf468412d77a651b8596decc1cb5afb1012170bac11a126

## Contents

- deployed/: 59 exact-byte copies of production Public/Admin
  source and relevant static admin/HTML code, each independently checked against
  the production manifest.
- code-manifest.json: expected SHA-256 per deployed file, and exclusions.
- source-mapping-audit.json: mapping from deploy paths to
  Windows source paths and their exact SHA-256 comparison status.

## Important limitations

This is NOT yet a complete three-way source synchronization. It deliberately
excludes compiled server/assets chunks, runtime catalogs/state, private
customer/payment data, backup files, credentials and databases.
Two service-restricted GST registry modules cannot be fetched non-root and are
not copied: admin/gst_phase1_registry.py and server/gst_phase1_registry.py.

The live manifest covers 1463 tracked artifacts, so 59 files are a code subset,
not an exact copy of the full production filesystem. Some Admin and Public
modules have separate hashes while Windows source has a single module path.
Do not flatten their copies or overwrite sources without a validated build map.

## Why this separate branch?

Original Windows checkout on agent/dev-admin-session-reset-main has 68 modified
tracked files. A combined-release checkout also has two modified catalog JSON
files. No existing checkout, catalog, production service or production data
was altered for this snapshot.

Comparisons:
- Main Windows checkout: 24/59 exact production matches,
  46 recognized source mappings.
- Combined release checkout: 28/59 exact matches,
  51 recognized mappings.

## Verification and next phase

All 59 snapshot files match individual production manifest SHA256 digests.
A conservative secret-pattern screen flagged zero files; all Python files
parsed successfully. Security review is still required for future changes.

Before actual source alignment to main, reconcile distinct Admin/Public build
mappings, compare generated assets, run backend/frontend regression tests, and
verify reproducibility. Ubuntu production remains the behavior reference.
Never overwrite production from this branch.

Deployment verified GST R2 calculations for two orders after release:
SD-20261107-D5F89A: INR 3.67; SD-20261102-D798E8: INR 346.88.
The code snapshot does not alter invoices, orders, or tax classifications.

## Source promotion tranche 1 (draft branch only)

Ten previously missing, non-divergent production Python modules have been copied
byte-for-byte into isolated Git worktree scripts/ tree. A stdlib unittest verifies
them against the pinned live production snapshot.

Previously existing scripts/receipt_pdf.py and both server entrypoints remain
unchanged. The protected Phase 1 registry module remains unavailable via
non-root SSH; never substitute the test-only shim for actual production code.

This is not yet a complete runnable production application. Do not deploy
from this branch until dependencies, Admin/Public divergences and full tests
are reconciled.

## Frontend build verification

Typecheck, 192/192 frontend unit tests, and Vite build all pass in the
isolated Windows sync worktree. However, the generated frontend is NOT the
same as the deployed Search V2 R2 plus overlays. See BUILD_PARITY.md
for the exact hash/entrypoint comparison. This branch remains a draft source
alignment effort, not an authorized production deployment package.

## GST source reconciliation completed in isolated branch

- Authentic 12-identity GST Phase 1 registry (3720 bytes) proven equal to
  both service-restricted deployed registry SHA-256 values.
- Exact receipt_pdf.py production source now promoted to scripts/, shared
  by both Admin and Public deployed copies.
- Updated tests for deployed Customer Bill/PAYMENT RECEIPT format.
- 30 focused GST/receipt parity tests passed, including synthetic
  5% and 18% customer GST figures, fail-closed policy, historical
  state alias, and unchanged customer totals.
- 93 backend/Admin/review tests passed with deployed receipt source.

Production payments, orders, GST registry and services were not touched.
The source snapshot is still NOT an authorized live deployment package;
other Admin/Public and frontend source alignment gates remain.

## Static Admin UI source reconciliation

The deployed Admin index.html, admin.css and admin.js now match the
isolated source at server/admin/ exactly, including the currently live
2026-11-15 month-end-delivery cache version and moderation UI.
Full backend/Admin/reviews/GST tests: 124 passed. Node syntax: PASS.
The Admin backend server entrypoint is still divergent, and the Vite
storefront remains non-identical to production. No production deployment.

## Admin-only account model source alignment

The active Ubuntu production admin/styledash_admin.py was restored
byte-for-byte to the isolated Windows scripts/styledash_admin.py.
The source SHA-256 agrees with the pinned deployed-code manifest.
Admin/security 55 tests and the broader 144-test backend regression
suite passed. No production access or writes occurred for this promotion.

## Firebase account deletion source alignment

The exact server/styledash_firebase.py production module is now aligned
with scripts/styledash_firebase.py (same SHA-256 as the pinned live manifest).
The deployed delta adds best-effort Firebase Auth account cleanup on
customer deletion. New tests mock every Firebase call, checking valid,
invalid, already-deleted, and backend-error paths; no real deletion occurs.
28 Firebase/federated-auth tests and 173 combined backend tests passed.
This is source synchronization only; production remains untouched.

## Review v5 moderation source alignment

Both deployed Admin/Public review modules were proven to have the identical
SHA-256, and the exact production module is restored to
scripts/styledash_reviews.py in this isolated branch.
The tests now use the deployed signed-in/unverified review policy, enforce
private-until-approved publication, reset to pending on edit, retain cross-
user edit/delete and own-store review restrictions, and exercise v2-v5
migration fixture consistency.
A synthetic 2x2 WebP covers photo access before/after moderation and
malformed-photo denial, not real-world browser upload rendering.
Focused review 15 tests and combined backend/security/GST 177 tests PASS.
Live server and user data were not touched.


## Distinct Admin/Public source targets

The original captured 59 non-sensitive files remain immutable.
A new source map under deployment-targets/vibe4you-20261116-r2/
tracks 60 hash-verified backend/static targets: 58 directly observed
production-code files plus 2 genuine Phase 1 GST registry targets.
Sixteen source files with divergent or missing legacy source paths
are stored separately by their Admin/Public runtime destination.
The generated server/index.html is excluded.

scripts/assemble_pinned_server_code.py --check performs zero-write
validation. Its --output option only permits a new OS-temp staging
directory. Ten targeted safety tests passed. The obsolete Termux
deployment installer is unchanged and must NOT be used to deploy
this code. This is not a complete website/source/production match.

The 60-target map now also feeds an offline Ubuntu-layout candidate builder.
It emits separate 33-file Admin and 27-file Public payloads plus deterministic
manifest/SHA256SUMS metadata under a new OS-temp directory. The read-only
observed service contract preserves the current systemd run scripts, loopback
8080/8081 isolation, venv, frontend assets, credentials and all runtime state.
Activation is not implemented or authorized. See
UBUNTU_BACKEND_RELEASE_ARCHITECTURE.md.

## Live storefront runtime acceptance baseline

frontend-runtime/ contains a captured, exact-byte, read-only reference of
134 publicly served current storefront/PWA files, including all 21
direct homepage links, the Search V2 R2 bundle's conservatively
discovered potential asset dependencies and PWA manifest icons/SW/offline fallback.
123 are in the existing server integrity manifest and eleven have
independent current disk/HTTP SHA-256 proof but lack manifest coverage.
No customer or private server data is included. A secret-pattern screen
found no flagged files. Source-lineage inventory identified 14 of
21 direct homepage references in older exact-byte Windows release
artifacts; a compiled file is not necessarily editable source.

scripts/verify_pinned_frontend_runtime.py is an OFFLINE integrity check;
server/tests/test_active_frontend_runtime.py tests its paths, PWA
links, tamper detection and source classification. The Vite build
does not yet reproduce current production, and no deployer consumes
this snapshot. These eleven out-of-manifest assets should be included
in a separately reviewed future guarded integrity/backup release.

## Recovered editable Search V2 R2 source

The archived November 14 Search V2 R2 source candidate has been
incorporated (eleven TS/TSX changes). The isolated Vite build now
reproduces all 61 files from its normal prepatch dist/, plus five
already-recovered public static assets. TypeScript and 225 frontend
unit tests pass. The final versioned production bundle and all overlays
still require an auditable release transformation and browser E2E.
Do not deploy this intermediate build. See
SEARCH_V2_EDITABLE_SOURCE_RECOVERY.md for the evidence and limits.


## Search V2 compiled release replay

search-v2-replay/ now stores only the PUBLIC compiled V4Y-055 R3
53-module baseline plus its homepage, and source needed to recompile
the historical Search V2 bridge. scripts/relevance-r2-runtime-bridge.ts
uses the recovered editable Search V2 R2 modules in src/.
scripts/replay_compiled_search_v2_r2.py recompiles the two bridges
and replays the exact compiled R3 -> V2 -> R2 transformations.

The tool passes 54/54 archived hashes for each release and 54/54
final byte-hash comparisons with current public Ubuntu assets.
It creates only disposable OS-temp output. The earlier R3 base remains
already-compiled; full React-source-to-live parity is NOT yet proven.


## R13 -> R3 historical compiled builder

search-v2-replay/r13-to-r3/ contains the historical public
V4Y-056 R13 baseline and original V4Y-055 R3 builder.
scripts/replay_r13_to_r3_offline.py reproduces all 56 archived
R3 candidate files, including 54 source-to-Search V2 code files.
Combined with existing Search V2/R2 replay, the full **historical
compiled release-patch sequence** is now testable offline.

This is NOT a full editable React source-to-production build,
because its earliest R13 baseline is already compiled. The
independently deployed overlays and payment/Admin browser E2E
are also not yet integrated. No production deployment is allowed.


## Full archived compiled release transformations from V4Y-046

The additional v4y046-to-r13 public archive and offline replay
now extend the historically verified chain to:

V4Y-046 -> V4Y-056 R13 -> V4Y-055 R3 -> Search V2 -> Search V2 R2.

R13: 56/56 code/config files and exact SHA manifest recreated;
R3: 56/56 files; Search V2: 54/54 public storefront files;
Search V2 R2: 54/54 final files match the verified Ubuntu runtime.

The original V4Y-046 code is compiled rather than editable React
source, and independently released overlays remain separately
deployed. This branch is NOT an authorized production release.
