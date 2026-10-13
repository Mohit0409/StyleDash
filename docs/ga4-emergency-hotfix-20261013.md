# Vibe4You GA4 — emergency tracking loader and retirement procedure

Updated: 2026-10-13 (India Standard Time)

## Current production state (verified)

Production origin: Ubuntu, `vibeadmin@192.168.1.6` via Windows SSH alias `vibe4you-prod`.
Live website: `https://vibe4you.in`.

On 2026-10-13, the deployed main entry bundle embedded `GOOGLE_MEASUREMENT_ID:""`, so consented visitors were not sending GA4 data. The intended GA4 property web measurement ID is `G-PSHXB46P50`. PR #144 fixes the build-time fallback in `src/config/index.ts`, and a unit test guards against empty configuration.

A temporary production-only **separate deferred GA4 loader** was deployed with no change to application JS, payments, orders, the admin interface, or databases. Its artifacts are:

- HTML: `/opt/vibe4you-production/server/index.html`.
- Loader: `/opt/vibe4you-production/server/assets/vibe4you-ga4-consent-3c9d1b529f9a.js`.
- Loader SHA-256: `3c9d1b529f9ae0e78e3c8665ceeba8f6c71d96bac8b6070691b542156e8d93e1`.
- Patched HTML SHA-256 at deployment: `498064ff5b498901266cd7e74dd55b86425810634774ba99cf54beda144df939`.
- Pre-patch HTML SHA-256: `885b93058f74269b21265e9d0ecda633c04c7f70c208ac5968b8c01a1c051fe0`.
- Rollback copy: `/opt/vibe4you-production/.rollback-ga4-shim-20261013T155740Z/index.html`.
- Old bundle stays `/assets/index-v4y-pr143-b4319e7efaa4.js`; it uses a production import map. Do not casually rename that entry.

### Live verification performed

Using Chromium browser sessions and real GA4 network requests:
- Before consent or after choosing "Only necessary": no gtag script or GA collection.
- After choosing "Allow analytics": `G-PSHXB46P50` tag loaded and `page_view` collector returns HTTP 204.
- Fresh desktop/mobile visits, returning visitors, and consent withdrawal verified; consent withdrawal stopped new events and cleared the `_ga` cookie.
- No tracking on sensitive password-reset route.
- SPA navigation `/` to `/stores` produced exactly one `page_view` for each route. The second collection request may be delayed by several seconds, so assertions should wait up to ~15 s.
- No JavaScript page errors in the successful loader tests; homepage, product listing, stores, and API health returned HTTP 200.

HTTP 204 only proves Google's collection endpoint accepted the request, **not** the GA4 property report. Confirm using GA4 Realtime and DebugView.

## Permanent release procedure

1. Ensure PR #144 passes required CI, is independently reviewed, and the production release is approved. Confirm fresh primary and secondary backups, their verification, and a rollback plan.
2. Build/deploy a **coherent frontend release** that includes all its Vite JS/CSS assets and the entry HTML/import map together. Do not patch or rename only the root JS entry; the first GA4 emergency attempt did that and caused React invariant #321 and DOM `removeChild` errors, even with consent declined. That attempt was rolled back.
3. The new bundled frontend must have non-empty `GOOGLE_MEASUREMENT_ID:"G-PSHXB46P50"` (or the approved replacement property ID).
4. **Remove** the separate `/assets/vibe4you-ga4-consent-3c9d1b529f9a.js` script tag from the new production HTML **in the same atomic release**. If the old tag is retained, the new built-in GA4 bootstrap could duplicate data or conflict with consent management. The old asset itself may remain unreferenced until retention cleanup.
5. After deployment, verify exactly **one** Google tag bootstrap and **one** GA4 `page_view` per path for consented browsing, including an internal link such as `/stores`. Verify zero tracking with consent declined, sensitive-route suppression, and tracking cessation after consent withdrawal. Validate no uncaught React/DOM errors.
6. Validate homepage/products/stores/checkout smoke and API health, and verify events in GA4 Realtime/DebugView. Monitor 5xx errors, SEO routes, 429s, and orders. Roll back the **whole frontend release** if tests fail.
7. Do **not** blindly restore the emergency HTML after further releases: check the current index SHA-256 and snapshot first. Restoring `/opt/vibe4you-production/.rollback-ga4-shim-20261013T155740Z/index.html` reverts to the former GA4-disabled frontend. Create a fresh rollback snapshot for each new release.

## Operational restrictions

- Never deploy new frontend code by mixing new main JS with old chunks or import maps.
- Do not change server rate limits, payment state, shop inventory, customer records, or DB to fix this issue.
- Do not publish any private credentials or raw customer tracking identifiers in reports.
- GA4 property access was not available during the emergency repair; dashboard-side confirmation remains outstanding.
