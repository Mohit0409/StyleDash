# Vibe4You production commission reconciliation — 2026-10-22

## Status: backend draft only; NOT deployed

This branch reconciles one production-only pricing capability with the editable StyleDash backend. It is stacked on sync/vibe4you-mobile-ui-20261021 (PR #161), itself stacked on taxonomy PR #160. It must NOT be deployed as a complete replacement for Ubuntu production.

## Verified source provenance

- Production manifest SHA-256: 0548d8067964ea4fcd62ba364f5501fb781b3b78806e7924c83d1e9b10197db2
- Public shop Python SHA-256: 91d427737cad6bf1edd12a3ce2e6c45b92d811586881b280fd78379b45da96cf
- Private admin shop Python SHA-256: 7731b786364fcf45d7eb0078518a3dc68a07a028cb46333b4ec8e7d3580b3cca

The October 21 archive was independently checked against live Ubuntu on October 22. Only source text was inspected. No customer records, environment values or private credentials were copied into public Git.

## Scoped source changes

- Match the live **5% default commission**, replacing the older editable 10/8/6% tier calculation.
- Add admin-only per-product commission overrides in basis points (0-10000, null to use default).
- Add idempotent shop SQLite migration version 11 for nullable commission_override_bps with a CHECK constraint.
- Preserve an existing product override when validating seller edits against the recorded MRP.
- Calculate storefront and checkout catalogue customer prices consistently; never increase the shop's recorded MRP.
- Keep private commission metadata on admin serialization only, not public or seller product DTOs.
- Reconcile admin single-product and atomic bulk commission operations, with authorization, MRP prevalidation, all-or-nothing updates and audit.
- Add private PATCH commission endpoints using existing admin session and CSRF middleware and strict request fields.

## Explicitly outside this PR

- Live-only GST/invoice/tax/refund/ledger modules.
- Live 100-variant product limits, shop rating aggregation, and private-admin category vocabulary drift.
- Live private-admin JS controls, bulk selection UI and CSV commission column.
- Remaining public/private server runtime differences and the admin service source gap.
- Ubuntu service restart, data migration, any live database change or deployment.

## Local validation

- Shop-workflow regression with new single/bulk override tests: passed.
- Focused 39-test shop/admin HTTP/checkout regression group: 39/39 passed, including CSRF, MRP and bulk commission checks.
- Admin Python handler syntax and new private PATCH routes tested through authenticated localhost HTTP requests: passed.
- Eight selected production commission functions matched the verified snapshot at Python AST level before bulk method and route addition.
- Final full backend synthetic suite: 342 tests executed, 4 skipped, 0 failures, 0 errors, exit 0 (October 22, 2026). The prior stale published-price assertion was corrected.
- The parent PR #160 GitHub checks failed before running any steps (no runner assigned); no hosted test success is claimed.

## Merge and deploy policy

Keep this PR DRAFT. Require final backend tests, private admin endpoint integration coverage, review of commission/MRP/tax implications, and successful GitHub-hosted checks before merge. Public StyleDash main still does not equal production; never deploy this partial reconciliation over the live Ubuntu server.
