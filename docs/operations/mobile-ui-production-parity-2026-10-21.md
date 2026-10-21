# Mobile storefront UI parity — 21 October 2026

This source branch ports the following safe, existing production mobile UI behaviors into editable React, instead of depending on the separately deployed v4y-mobile-ui-fix-20261021.js DOM overlay.

## Changes

- Add circular shortcuts for Watches, Groceries and Nutrition to the mobile header while retaining the existing categories and scroll behavior.
- Keep the mobile filters overlay above fixed mobile navigation.
- Use viewport-sized filter dialog with a separate scrollable content area; keep the Apply Filters button visible and respect mobile safe-area padding.
- Define shortcut data in a typed module and cover category destinations, uniqueness, filter dialog structure and rendering with Vitest.

## Validation

- Full frontend Vitest: **197 passed in 37 test files**.
- ESLint: exit 0.
- TypeScript typecheck: exit 0.
- Production frontend build: exit 0.
- Node bulk CSV and image-selection UI tests: exit 0.
- Separate parent taxonomy branch had 339 backend tests passed, 4 skipped. This branch only changes frontend code.

## Deployment policy

This branch is intended as a **stacked draft PR** against sync/vibe4you-production-20261021 (taxonomy parity). That parent branch itself is not merged to main.

Do not redeploy this frontend alone: many other direct-to-production fixes remain to be reconciled and the GitHub Actions runner is still failing to acquire jobs. The exact production code remains preserved separately in the private Vibe4You-Production-Mirror.