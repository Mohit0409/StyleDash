# V4Y-038 — Store Profile Statistics

**Date:** October 14, 2026
**Status:** Implemented in isolated branch, tested locally, awaiting release coordination. **NOT DEPLOYED.**

## Customer-visible feature

A new **Store at a glance** section appears directly below the cover banner of every public store profile (`/store/:slug`) and before Store Reviews.

The section shows:

1. **Published products:** authoritative backend productCount for the active store, with a fallback to the number of unique loaded listings if that metadata is missing. This avoids falsely showing zero products when the per-store catalogue response is temporarily incomplete. Sizes/colour variants do not multiply the count. This is a **listing count**, not a guarantee every size is in stock.
2. **Store rating:** the existing verified customer-review rating (out of 5) and total published/verified review count. If no verified reviews, show **Not rated yet**, not an invented star rating.
3. **Catalogue activity:** **Daily active**, **Weekly active**, **Monthly active**, **No recent updates**, or **Activity unavailable**. Activity refers strictly to public product listing updates, **not seller login/online status, visits, store operating hours or order volume**.
4. **Most recent product update date** in the India timezone where a valid timestamp exists.
5. **Products updated in 24h / 7 days / 30 days** as distinct, cumulative updated-listing counts.

## Business rules

Activity is derived from the backend's existing `Product.updatedAt` field on public `PUBLISHED`/active products. A new publication has a product update timestamp; approved admin or seller listing changes may also update it.

The calculations use rolling elapsed windows, not calendar weekdays:
- A valid latest update **less than 24 hours old** → Daily active.
- Otherwise **less than 7 days old** → Weekly active.
- Otherwise **less than 30 days old** → Monthly active.
- Older than or equal to 30 days → No recent updates.
- No valid timestamps / no published products → Activity unavailable.

A listing's update must have a valid date **not in the future**. Invalid, missing and future dates do not create false activity. Duplicate product IDs count once, using the latest valid timestamp. Unpublished/inactive products are excluded.

The counts show how many distinct published listings have their **latest** update timestamp within each window, **not how many individual edits were made**.

## Implementation

No new tables, migrations, backend endpoints, credentials or admin permissions are required.

- `src/utils/storeStatistics.ts`: pure calculation with an injectable clock.
- `src/components/StoreStatistics.tsx`: responsive accessible store statistics cards.
- `src/pages/StoreDetail.tsx`: mounts statistics under the existing cover and feeds it the already loaded per-store catalogue and live review summary.
- `src/tests/storeStatistics.test.tsx`: date boundary, duplicate, missing timestamp, unrated and rendering checks.
- `e2e/specs/store-statistics.spec.ts`: mocked product/review integration in both desktop/mobile Chromium.

The live `/api/shop-products/published?vendorId=...` and `/api/store-reviews` endpoints remain authoritative. Other features, including seller products, storefront pagination, cart, checkout, reviews moderation and inventory availability, are unchanged.

## Completed local validations

- 10 utility/component tests: **PASS**.
- 192 full frontend Vitest tests (34 test files): **PASS**.
- TypeScript project build: **PASS**.
- Focused ESLint for all modified/added frontend files: **PASS**.
- Vite production bundle build: **PASS**.
- Store profile Playwright E2E: **desktop PASS, mobile PASS** (2/2).
- Known pre-existing `package.json` warning: duplicate `overrides` keys. Not changed by this feature.

## Deployment gate

**Do not deploy** from the isolated branch while any other StyleDash/Vibe4You release is underway. Coordinate the final production revision; compare branch diff to latest main, rerun affected tests, confirm verified backups and rollback procedures. Build an exact compatible release and follow normal protected-branch CI/review/merge rules. Do not hot-swap the live frontend or restart services without an approved release window.

## Local code location

`C:\movieXsuggestion\MyProject\StyleDash\.worktrees\store-profile-statistics-20261014`

Branch: `feature/store-profile-statistics-20261014`, based on `origin/main` at `e6d6892`.

**Release status: NOT DEPLOYED.**
