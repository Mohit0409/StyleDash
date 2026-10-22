# Vibe4You CSV commission parity — October 22, 2026

## Status: DRAFT, editable source only, NOT deployed

- Branch: sync/vibe4you-csv-commission-parity-20261022
- Parent: sync/vibe4you-admin-commission-ui-20261022 (draft PR #163)
- Stack also depends on commission backend PR #162, mobile PR #161 and taxonomy PR #160.
- The original Windows StyleDash checkout, public main and Ubuntu production were not modified.
- The production references below came from the verified 1122-file snapshot.

## Verified live reference SHA-256

- Admin serve.py: 5f8fd8035c68df7fe7456fac8314c4a489a5fc819cbcf2a9b2f1ad2fee895afe
- Admin styledash_shops.py: 7731b786364fcf45d7eb0078518a3dc68a07a028cb46333b4ec8e7d3580b3cca
- Private admin/admin.js: f72c4aaee101355a6adb553bd0537dd9fb842e30cf4c53d4a7ec4c705d26968e

## Backported and protected

- Optional commissionPercent CSV column. Empty means default 5%. Values 0 through 100 with at most two decimal places are accepted.
- Strict row-level CSV validation before uploading images.
- Validated integer basis points (0 to 10000) are handled privately by the backend and are not exposed to storefront DTOs.
- Each row is validated against the real MRP at its effective customer price before publishing; any invalid row rejects the entire batch.
- New product and override are committed in the same SQLite transaction.
- CSV sample changed from invalid price=MRP 1720/1720 to 1720/1999, satisfying the 5% default.
- Explicit fail-closed rejection of productGroup grouped-colour CSV rows, preventing silent product splitting while that separate production feature remains unreconciled.
- Updated admin JavaScript query cache key with matching private admin test assertions.
- Added synthetic public/checkout/admin atomicity, MRP, zero-rate, partial percentage and invalid-rate tests.

## Not ported

- The production colour-group aggregation and up-to-100 variants require a separate source-parity PR and review. Current editable source still has legacy variant limits.
- GST/invoicing, ledger, refunds, orders and payment code untouched.
- No live prices, product records or customer/business data changed or added to Git.
- No production deployment and no merge to public main.

## Local validation

- Existing shop workflow suite before changes: 37 tests passed.
- Focused private backend CSV commission, atomicity test: 2 tests passed.
- Authenticated admin CSV upload integration passed (invalid rates, no partial writes on MRP failure, unsupported grouping failure).
- Node admin UI and bulk CSV suites: 18 passed, zero failed.
- Python syntax, admin JavaScript syntax and Git diff checks passed.
- Full backend synthetic suite: 343 tests run, 4 skipped, 0 failures, 0 errors, exit 0 (October 22, 2026).

## Review gates

Keep the PR in draft, review financial invariants, enable successful hosted CI, and finish outstanding production runtime parity before merging or deploying. An isolated local green suite does not make the entire editable repository production-equivalent.
