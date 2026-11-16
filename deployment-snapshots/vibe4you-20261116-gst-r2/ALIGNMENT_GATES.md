# Buildable-source alignment gates — Vibe4You, 2026-11-16

**Status:** Draft integration; no production or original Windows worktree changes.

Source of truth: live Ubuntu production integrity manifest:
ec13b4f28f99b26f3cf468412d77a651b8596decc1cb5afb1012170bac11a126

## Measured from the isolated sync worktree

- 59 deployed non-sensitive code files snapshot-verified byte-for-byte.
- 32 of these have a byte-identical mapped source file in the sync worktree.
- 20 map to an existing but different source file.
- 7 lack an existing source path according to the conservative mapper.
- Two additional Phase 1 registry files remain unreadable by nonroot SFTP
  (their names appear in code-manifest.json, without their contents).
- The previously existing source files were not overwritten in tranche 1.
- Ten unambiguous missing Python modules are now in scripts/.
  Five public production pages/assets are now in public/.
  All 15 are checked by server/tests/test_production_snapshot_parity.py.

These numbers describe source-path hash matches, not a production-ready build.

## Highest-priority unresolved dependencies

1. **GST Phase 1 registry:** production receipt module imports
   gst_phase1_registry.py, but the live version is not readable by the
   non-root SSH account. The 479-byte test shim in prior Windows release
   staging is NOT the real production registry and must never replace it.
   An owner-authorized private inspection or separate vetted reproduction
   is required before promoting scripts/receipt_pdf.py.

2. **Receipt GST module:** both live Admin and Public receipt_pdf.py
   files match exactly and include the 2026-11-16 state alias and
   ancillary-delivery approval gate. The existing Windows
   scripts/receipt_pdf.py still uses an older, unverified implementation.
   The exact production bytes are retained in deployed/admin and
   deployed/server, not substituted into the legacy script.

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
- 10 missing Python modules promoted into clean branch scripts/.
- 5 public pages/assets promoted into clean branch public/.
- Git staged object hashes for those ten matched live production bytes.
- 11 parity plus existing receipt unit tests: PASS.
- 81 admin/shop/reliability regression tests: PASS.
- 12 original review unit tests: PASS after restoring older module.
- No changes to Ubuntu production, invoices, customers, backups,
  or the original Windows checkout.

## Proposed next integration sequence

1. Acquire **genuine** live Phase 1 registry through an approved
   root-only read-only route, with hash and secret review.
2. Design a dedicated build mapping for the divergent Public/Admin
   entrypoints and tax/shops/security modules.
3. Promote receipt/GST source with full historical-order regression
   tests and invoice issue/read invariants.
4. Reconcile reviews and photo migrations against current requirements.
5. Validate frontend assets and build output equivalence.
6. Run end-to-end tests, compare the complete production artifact
   manifest and require explicit owner approval before merging main.

The production snapshot and promoted source are **not** an authorized
deployment input yet.
