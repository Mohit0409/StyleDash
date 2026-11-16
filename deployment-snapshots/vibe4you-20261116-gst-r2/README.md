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
