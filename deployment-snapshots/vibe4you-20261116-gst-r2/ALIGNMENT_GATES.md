# Buildable-source alignment gates — Vibe4You, 2026-11-16

**Status:** Draft integration; no production or original Windows worktree changes.
The static Admin UI (HTML/CSS/JS) is now source-aligned, while the
Admin request handler and storefront build are not.

Source of truth: live Ubuntu production integrity manifest:
ec13b4f28f99b26f3cf468412d77a651b8596decc1cb5afb1012170bac11a126

## Measured from the isolated sync worktree

- 59 deployed non-sensitive code files snapshot-verified byte-for-byte.
- 42 of these have a byte-identical mapped source file in the sync worktree.
- 11 map to an existing but different source file.
- 6 lack an existing source path according to the conservative mapper.
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

2a. **Admin HTML/CSS/JS (RESOLVED):** deployed index.html,
   admin.css and admin.js now match the isolated Windows source files
   byte-for-byte. The exact production JS passes Node syntax validation.
   Updated legacy cache-bust, category, bulk-refund and review UI
   assertions to match current production (without dropping safety
   assertions); full suite of 124 backend/Admin/reviews/GST tests passed.
   Admin backend serve.py is STILL divergent and not yet synchronized.

2b. **Admin-only account/permissions source (RESOLVED):**
   scripts/styledash_admin.py was recovered as an exact SHA-256
   match for deployed admin/styledash_admin.py. Admin and security
   suites passed 55/55, then the wider backend/receipt/review/security
   suite passed 144/144. The deployed module is still a component
   of the older build and not an authorized production release.

2c. **Public Firebase account-deletion cleanup (RESOLVED):**
   The exact live server/styledash_firebase.py now matches
   scripts/styledash_firebase.py, including the separate
   delete_firebase_user helper. The pre-existing federation/login
   functions were unchanged in the source delta. All Firebase SDK
   interactions in new regression tests were mocked, with no real
   user-deletion or network activity. Existing federated-auth plus
   mock cleanup checks passed 28/28, and the combined suite passed
   173/173.

3. **Admin/Public divergent modules:** some deploy targets share a filename
   but have different SHA-256 digests. Each must keep a separate build
   mapping or a reviewed common-code extraction, not a blind overwrite.
   Examples include serve.py, tax_classification_registry.py,
   invoice_admin_gateway.py, catalog_normalization.py, styledash_security.py,
   styledash_shops.py, and store_categories.py.

4. **Reviews v5 and photo migration source (RESOLVED):** both deployed
   Admin/Public styledash_reviews.py modules have the identical SHA-256
   and now match the isolated scripts/styledash_reviews.py exactly.
   Updated legacy tests to enforce the deployed signed-in/unverified review
   policy, private-until-approved status, re-moderation after editing,
   IDOR protection, own-store review prohibition and safe v2-v5 schema
   rollback/migration fixtures. Three added tests cover synthetic WebP
   photo privacy, rejects invalid images, and photo_webp migration columns.
   15/15 review tests and 177/177 combined backend/security/GST tests pass.
   This tests source behavior, NOT browser upload success for real customers.
   Live production/SQLite/customer records remain untouched.

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
- 144 backend/Admin/security/review/GST tests: PASS after restoring
  the deployed Admin-only store/permissions source.
- 12 original review unit tests: PASS after restoring older module.
- No changes to Ubuntu production, invoices, customers, backups,
  or the original Windows checkout.

## Proposed next integration sequence

1. Design a dedicated build mapping for the divergent Public/Admin
   entrypoints and tax/shops/security modules.
2. Extend end-to-end invoice issue/read invariants with safe synthetic
   historical-order test fixtures (receipt/registry source now aligned).
3. Validate review-photo browser upload/rendering end-to-end in an isolated
   environment (source and unit-level privacy/migrations now aligned).
4. Validate storefront assets and build output equivalence.
5. Run end-to-end tests, compare the complete production artifact
   manifest and require explicit owner approval before merging main.

The production snapshot and promoted source are **not** an authorized
deployment input yet.
