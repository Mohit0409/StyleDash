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
