# V4Y-039 — Compact store statistics and verified store-rating badges

**Date:** October 15, 2026
**Status:** Implemented and tested in an isolated frontend branch. **NOT MERGED / NOT DEPLOYED.**

## Customer request

The large three-card "Store at a glance" and always-visible customer reviews occupy too much vertical space on public store pages. The user wants one small common statistics/info icon opening a dropdown with three sections: **Published products**, **Store rating** (click again to reveal reviews), and **Catalogue activity**. The "New" badge on store-listing cards should display real `5/5`, `4/5`, or fractional verified ratings instead.

## UI behavior

- On `/store/:slug`, a 40 × 40 pixel info (i) icon button appears in the top-left of the existing cover image. **Closed by default**; the entire statistics section has **zero height** below the cover while collapsed. This preserves existing imagery, store logo, name, and inventory.
- Clicking the control shows one compact responsive dropdown below the cover. Three clearly separated rows are visible:
  - **Published products**: uses the authoritative per-store `productCount` when valid, otherwise counts unique published loaded listings.
  - **Store rating**: displays the verified review summary as `5/5`, `4.5/5`, etc., or **Not rated yet**. Clicking this row expands the original full **Store Reviews** experience *inside the dropdown*, including real customer reviews, sorting, verified-purchaser submission/edit/delete and sign-in eligibility. Closing collapses it; a later open reinitializes the review panel closed.
  - **Catalogue activity**: unchanged rolling product-update logic, shows Daily/Weekly/Monthly/No recent updates/Unavailable, latest update date and three clearly spaced counts for updates in 24h/7d/30d. Explicitly says activity is NOT seller login or online status.
- Ratings use a new shared formatter `getStoreRatingLabel` used by the public store cards, cover badge and dropdown, avoiding inconsistent formatting and fabricated ratings. It requires **positive review count and rating 1–5**. Rated cards show `5/5`, `4/5` or `4.5/5`; unrated cards show **Not rated**, not "New".
- Stat and review controls expose `aria-expanded`, `aria-controls`, keyboard-focus styling, button type and accessible labels; review requests are **lazy** until expanded.
- No changes to backend API, payment/checkout, refund, authentication rules, store product data, review moderation, admin portal, database or commission.

## Files

- `src/components/StoreStatistics.tsx`: compact overlay trigger; small three-row dropdown; nested reviews.
- `src/components/StoreReviews.tsx`: optional compact layout when used inside dropdown; logic unchanged.
- `src/pages/StoreDetail.tsx`: groups cover and dropdown for zero-height collapsed state; review panel moved inside Store rating.
- `src/pages/Stores.tsx`: replaces "New" card score with real fractional /5 rating or "Not rated".
- `src/utils/storeRating.ts`: safe shared display formatter.
- `src/tests/storeRating.test.ts`, `src/tests/storeStatistics.test.tsx`, `e2e/specs/store-statistics.spec.ts`: formatting, fallback, zero-height collapse, nested review interaction and real review summary updates.

## Verification on isolated branch

- TypeScript compilation: PASS.
- ESLint on changed frontend and test files: PASS.
- Focused stats/rating tests: 9/9 PASS.
- Full frontend Vitest suite: **191/191 PASS (35 files)**.
- Vite build for browser testing: PASS.
- Vite production bundle build: PASS. Pre-existing package.json duplicate `overrides` warning unchanged.
- Playwright: desktop Chromium PASS; mobile Chromium PASS; iPhone WebKit PASS.
- Tests assert collapsed panel adds zero height, dropdown lists correct counts/activity, verified reviews load **only on expansion**, nested review panel toggles, store cards show `5/5` and "Not rated" rather than "New", and existing store inventory remains visible.

## Deployment boundary

V4Y-038 PR #149 was deployed using a **53-chunk immutable versioned frontend graph** with a precisely updated `/opt/vibe4you-production/.migration/artifact-files-remediated.sha256`. The active production index and static chunks **do not necessarily match a fresh GitHub `dist/` build**.

**DO NOT deploy this branch by replacing all live `dist` assets or restarting the backend.** Finish code review and CI, inspect the **current active live** index/assets/manifest and other releases, build and separately review an exact compatible surgical static-only release with immutable asset names, verify fresh primary/secondary backups and SQLite integrity, approve the release window, then run desktop/mobile/iPhone and relevant safety smoke. Rollback must restore the precise previous public index and startup manifest. No real payment test without explicit owner approval.

**Status: PREPARED LOCALLY; NOT MERGED OR DEPLOYED.**
