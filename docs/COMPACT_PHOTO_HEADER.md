# Compact photo header — implementation handoff

Date: 2026-10-04

TASK: Reduce mobile header size, replace category outlines with photo artwork,
and remove scroll-collapse jumps.

ROLE: Developer implementation, with independent Tester static review.

BASE COMMIT: `806dd2477e4a543398402ae7bf51862c5726e0c5` (PR #128).

WORKING/TESTED COMMIT: Focused changes on `agent/dev-compact-photo-header`.

RESULT: Local implementation verified. Production release remains MANUAL ACTION
REQUIRED, not release-approved or deployed.

## Changes

- `src/components/Header.tsx`: 154px mobile header (approximately 30% shorter
  than the preceding ~220px design), existing six category links, 48px photo
  tiles and 44px controls. Desktop and four-item bottom navigation retained.
- `src/components/Header.css`: fixed mobile chrome with stable in-flow space,
  220ms collapse animation, 104px/32px hysteresis, reduced-motion support.
  Collapsed shell is 53px including border, containing only Search and Menu.
- `src/assets/category-artwork.jpg`: 194,443-byte sprite adapted from the
  user-supplied reference. No remote image dependency or new package dependency.
- `e2e/specs/compact-header.mobile.spec.ts`: four new browser tests covering
  320–767px layouts, images/routes, scroll geometry, animation, threshold
  stability, reduced motion, search/menu, route cleanup and desktop restoration.
- This handoff and two header-only preview images.

## Verification

- Typecheck: PASS.
- Lint: PASS after correcting the new test's regex escape.
- Frontend unit suite: 150/150 PASS, 27 files.
- Focused mobile/browser navigation suite: 13/13 PASS (including four new tests).
- Desktop navigation regression: 4/4 PASS.
- Full Python suite: 332 run, 328 passed, 4 skipped; no failures.
- E2E build and production build: PASS. Existing duplicate `overrides` warning
  in package.json is unchanged.
- Production build loads only the four existing browser Firebase config values
  into the build process without printing them. The Firebase chunk remains
  `firebaseClient-B8Q2FPL-.js`, SHA-256
  `e9912cda8c8aa7631961f380f2adb4f5aadd99a3a0d8112ee9f0563aef4793ed`.
- Independent static review found a fixed search/menu panel could obscure a
  destination page; resolved by closing panels on `location.key` changes,
  including same-route navigation. Regression assertions passed; re-review PASS.
- Frame-by-frame browser checks observed no scrollY or document-content-position
  shift during collapse, with intermediate animated heights.
- `git diff --check`: PASS.

## Safety and remaining gates

SECURITY IMPACT: Presentation only; no authentication, authorization, secret,
administrator-isolation or public-routing changes.

DATABASE IMPACT: None. No production database accessed or changed.

PAYMENT IMPACT: None. No real payment, credential or configuration change.

DEPLOYMENT: NOT PERFORMED. Dirty primary checkout preserved. Build-generated
catalog files are not part of the change or a release candidate.

KNOWN LIMITATIONS: User's phrase "to 30%" is ambiguous. The implemented preview
is 30% shorter, not reduced to one-third. Artwork is an image-tool adaptation,
not a pixel-exact crop of the original attachment. Chromium emulation is not a
physical Android/iPhone smoothness test. No broad full-browser-suite release
certification is claimed.

MANUAL ACTION REQUIRED / NEXT ROLE: Review the preview and confirm intended
height. Before production, complete the human release gate, required CI/security
release review, fresh primary backup and independent verification, and report
secondary DR status separately. Use Ubuntu artifact-manifest release tooling
and preserve the existing code rollback, live data, secrets and routing.

CONFLICT: Repository AGENTS references Android/Termux and ngrok; the owner's
current Ubuntu/systemd/Cloudflare instructions supersede those old details.
Do not use a Termux deployment or deploy the dirty primary working tree.

## Artwork provenance

Prepared with the built-in image-editing tool under the imagegen skill, using
the user's attached category sheet as the edit target. Generated PNG was
encoded to JPEG at quality 82 without changing its composition or dimensions.
Project asset: `src/assets/category-artwork.jpg`.

Final tool prompt:

> Use case: precise-object-edit. Input Image 1 is the edit target: the user's two-row category artwork sheet. Prepare this artwork as one web sprite sheet, preserving the exact subjects, faces, clothing, objects, colors and photorealistic style from the reference. Remove all text labels only and place the FIRST ROW's six circular artworks in an evenly spaced 3-column by 2-row square-cell grid on white. Order row 1: Women, Men, Kids. Order row 2: Footwear, Beauty, Jewellery. Each circle centered in its equal square cell, with circle diameter 90% of cell width; the grid must fill the canvas with equal cells and no outer margin beyond the 5% cell margins. Output landscape 1536x1024 (six 512x512 cells). Do not include the second row of original categories. No labels, no text, no outlines, no extra objects. This is extraction/layout of the provided artwork, not a new design. Preserve the reference images as closely as possible.
