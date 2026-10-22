# Vibe4You admin commission UI source reconciliation — October 22, 2026

## Status: DRAFT / source only / NOT deployed

This patch backports a narrowly scoped subset of private production admin UI functionality from the October 21, 2026 verified production code snapshot. It is based on the commission backend branch sync/vibe4you-commission-parity-20261022 (draft PR #162), itself stacked on the mobile and taxonomy draft PRs.

**Do not deploy this branch wholesale to Ubuntu**: the editable StyleDash repository still differs materially from production.

## Verified source input

Live production admin JS source SHA-256:
f72c4aaee101355a6adb553bd0537dd9fb842e30cf4c53d4a7ec4c705d26968e

Live baseline 1,122-file manifest SHA-256:
0548d8067964ea4fcd62ba364f5501fb781b3b78806e7924c83d1e9b10197db2

All 1,122 files had matched Ubuntu and Windows SHA-256 at the read-only live audit on October 22. The matching production source was consulted locally; no customer database or secrets were accessed.

## Exactly what is backported

- Set commission button on each private admin product card.
- Explicit commission percentage label and default (5%) / custom distinction in private admin.
- Default/custom commission modal for one product, including preview MRP cap, correct integer basis points and authenticated private PATCH endpoint.
- Set commission as an option in the existing products bulk action selector.
- Bulk commission modal for selected products; verify every selected product against MRP before one atomic private PATCH.
- Cancelled bulk dialog returns cleanly without issuing a request, clearing selections or unnecessarily refreshing the view.
- Existing private session and CSRF handling is preserved (the already merged commission backend PR #162 supplies protected routes).
- Cache-bust the private /admin.js asset using the index.html query string, updating the test assertions accordingly.
- Add 10 independent synthetic Node admin-UI tests and include them in GitHub Actions backend job.

## Exclusions / known integration gaps

- CommissionPercent CSV column and live bulk-CSV per-product commission import are NOT backported here. Editable backend parsing and atomic-create behavior need separate review.
- All other live-only admin UI functions (GST, official watch tax rates, product pagination, 100-variant editor, extra bulk product feature actions) stay out of this patch.
- GST invoice issuance remains locked/not enabled by this source patch; MRP, checkout, orders and customer prices in live production are untouched.
- Editable StyleDash main remains NOT production equivalent; draft PRs do not authorize deploy.
- Live private GST/admin JavaScript source must never be copied wholesale over editable code without a distinct security/accounting review.

## Validation and safety evidence

- New Node VM interactive tests: 10 passed, zero failures.
- Existing Node CSV/multiple-image selection tests: 4 passed.
- Existing Python private-admin full suite: 36 tests passed, exit 0. GET for new versioned admin JS returned 200.
- Admin JS syntax check: passed.
- Diff whitespace check: passed.
- Full Python backend regression: 342 tests run, 4 skipped, 0 failures, 0 errors, exit code 0; isolated synthetic suite on October 22.
- New GitHub Actions step will run the UI synthetic Node tests after hosted runner availability is restored. A previous GitHub CI failure occurred before any job steps were executed.

This branch modifies only private admin front-end source, its asset version, the matching synthetic tests, and CI/test documentation. No Ubuntu writes, production database updates, owner credentials or GitHub main merges.
