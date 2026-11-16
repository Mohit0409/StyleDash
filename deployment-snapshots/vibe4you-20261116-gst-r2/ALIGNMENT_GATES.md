# Buildable-source alignment gates — Vibe4You, 2026-11-16

**Status:** Draft integration; no production or original Windows worktree changes.

Source of truth: live Ubuntu production integrity manifest:
ec13b4f28f99b26f3cf468412d77a651b8596decc1cb5afb1012170bac11a126

## Measured from the isolated sync worktree

- 59 deployed non-sensitive code files snapshot-verified byte-for-byte.
- 34 of these have a byte-identical mapped source file in the sync worktree.
- 18 map to an existing but different source file.
- 7 lack an existing source path according to the conservative mapper.
- Two Phase 1 GST registry modules remain unreadable by nonroot SFTP, but
  an exact-SHA copy of their genuine 3720-byte source was recovered in an
  older Windows worktree and promoted to scripts/gst_phase1_registry.py.
  Its SHA was checked against both live production manifest entries.
- The previously existing source files were not overwritten in tranche 1.
- Eleven missing Python modules (including the authentic Phase 1 registry)
  are now in scripts/, and five production public pages/assets are in public/.
  The existing scripts/receipt_pdf.py was aligned to its exact deployed
  Admin/Public bytes. Provenance and synthetic GST unit tests cover these
  files alongside the existing public-file parity tests.

These numbers describe source-path hash matches, not a production-ready build.

## Highest-priority unresolved dependencies

1. **GST Phase 1 registry (RESOLVED):** exact 3720-byte source recovered
   from a Windows worktree with SHA-256 matching BOTH service-restricted
   Ubuntu production files. The test-only shim has not been used.

2. **Receipt GST module (RESOLVED):** the old Windows source was replaced
   on this isolated branch with the exact production receipt bytes
   (SHA-256 eee783b343739237d9bcab2e59e5fe1c0c9d6b35300733bb6edaa64db9f84c3f).
   Both Admin and Public sources have the same hash. Legacy receipt design
   assertions were updated to the deployed Customer Bill format;
   30 focused GST/receipt tests and 93 backend/Admin/review tests passed.
   Production remains unchanged. Historical real-order validation is
   supported by the existing owner-privileged deployment logs; new unit
   fixtures are synthetic only.

3. **Admin/Public divergent modules:** some deploy targets share a filename
   but have different SHA-256 digests. Each must keep a separate build
   mapping or a reviewed common-code extraction, not a blind overwrite.
   Examples include serve.py, tax_classification_registry.py,
   invoice_admin_gateway.py, catalog_normalization.py, styledash_security.py,
   styledash_shops.py, and store_categories.py.

4. **Review policy + schema migrations:** production's common
   styledash_reviews.py is newer. An isolated trial replacement caused
   4 older baseline test failures and 2 errors: legacy delivered-purchase
   expectations no longer match deployed review eligibility; migration
   fixtures lack the photo_webp column. The attempted replacement was
   REVERTED in the branch. The original 12 review tests pass again.
   Correctly update migrations and contractual tests to reflect the
   desired current policy before moving this module.

5. **Generated frontend:** the old Vite source and current deployed index
   and generated JS assets are not yet reproducibly mapped. Do not assume
   copying built dist files back into src makes a valid source build.

6. **Owner's Windows edits:** the root Windows checkout has 68 existing
   modified tracked files; a separate combined release checkout has two
   modified catalog JSONs. These must be reviewed, not overwritten or
   force-merged.

## Verified safe steps already completed

- 59 deployed files individually hash-verified against live manifest.
- 11 missing Python modules (including genuine GST Phase 1 source) promoted.
- 5 public pages/assets promoted into clean branch public/.
- Exact SHA-256 source provenance verified for receipt and GST Phase 1.
- 30 focused GST/receipt tests: PASS after restoring production receipt.
- 93 backend/admin/review regression tests: PASS with production receipt.
- 12 original review unit tests: PASS after restoring older module.
- No changes to Ubuntu production, invoices, customers, backups,
  or the original Windows checkout.

## Proposed next integration sequence

1. Design a dedicated build mapping for the divergent Public/Admin
   entrypoints and tax/shops/security modules.
2. Extend end-to-end invoice issue/read invariants with safe synthetic
   historical-order test fixtures (receipt/registry source now aligned).
3. Reconcile reviews and photo migrations against current requirements.
4. Validate frontend assets and build output equivalence.
5. Run end-to-end tests, compare the complete production artifact
   manifest and require explicit owner approval before merging main.

The production snapshot and promoted source are **not** an authorized
deployment input yet.
