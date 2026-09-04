# Vibe4You Dev Coordination

Canonical cross-chat coordination file: `C:\movieXsuggestion\MyProject\VIBE4YOU_DEV_COORDINATION.md`

## DEV1 handoff — COD payment status + profile persistence — 2026-09-04

### Ownership
- **Issue 1 — COD Payment Status:** DEV1 complete, pending DEV2 integration review.
- **Issue 3 — Profile Persistence:** DEV1 complete, pending integration review.
- Branch/worktree: `agent/dev1-cod-profile-persistence` / `StyleDash-dev1-cod-profile`.
- Base commit: `6148037e57ac26831d83f0cc2e5d0ba03934899b`.
- Implementation commit: `58b3b9c02d59f7d74d2724d8e31076b1125c189a`.
- Deployment: **NOT PERFORMED**. Do not deploy before DEV2 integration review and the required independent review gates.

### Files modified by DEV1
- `scripts/termux-admin-server.py` — private admin COD payment mutation and audit.
- `server/admin/admin.js` — eligible COD `Mark as Paid` UI and Cash / UPI-at-delivery collection dialog.
- `scripts/termux-spa-server.py` — customer order DTO payment-field exposure and authoritative profile hydration on register/password/federated authentication responses.
- `src/services/paymentApi.ts` — additive `ServerOrder` payment collection fields.
- `server/tests/test_admin.py` — COD lifecycle, admin auth/CSRF, audit, Razorpay rejection regressions.
- `server/tests/test_styledash_server.py` — password/profile persistence and returning Google/mobile OTP identity regressions.
- `e2e/specs/profile-persistence.spec.ts` — browser regression for save profile → logout → login → persisted address.
- `docs/DEV_COORDINATION.md` — this handoff record.

### Issue 1 — API and payment contract
Private admin endpoint:

`PATCH /api/admin/orders/:orderId/payment`

Request body:

```json
{"collectionMethod":"cash"}
```

or:

```json
{"collectionMethod":"upi_at_delivery"}
```

Rules:
- COD continues to be created with `paymentMethod="cod"` and `paymentStatus="pending"`.
- `Confirm Order` remains a fulfillment/status operation only; it does not change `paymentStatus`.
- Only the authenticated private admin service with a valid admin CSRF token can mark a COD payment paid.
- Successful collection changes only the payment lifecycle to `paymentStatus="paid"` and records the collection metadata below.
- Manual payment marking is rejected for Razorpay `upi` / `card` orders, payment-test orders, cancelled orders, and orders whose payment is no longer pending.
- Successful manual collection writes the private audit action `cod_payment_marked_paid` with collection method and payment timestamp.

### Exact payment fields exposed to DEV2
The existing customer order APIs (`/api/orders` and `/api/orders/:id`) expose the normal payment fields plus these additive collection fields:

- `paymentMethod`: existing field; COD remains `"cod"`.
- `paymentStatus`: existing field; COD is `"pending"` before collection and `"paid"` after the private admin operation.
- `paymentCollectionMethod?: "cash" | "upi_at_delivery"` — additive; absent until COD money is recorded as collected.
- `paymentCollectedAt?: string` — additive ISO-8601 UTC timestamp; absent until collection.

DEV2 may use these fields for receipt/tracking display only. DEV2 must not infer a second payment state or mutate payment lifecycle from receipt/UI code. DEV1 intentionally did not own the professional receipt renderer so DEV2 can consume these fields without a receipt-layout merge collision.

### Database / persistence contract
- No customer database schema migration was required.
- Authoritative profile data remains SQLite `users` + `user_addresses`.
- Profile reproduction before the fix showed that the address remained in SQLite while the login response omitted `addresses`; the frontend then replaced the hydrated profile with this reduced auth DTO, making the address appear lost.
- Password registration/login and Google/mobile OTP federated responses now hydrate the returned user from the authoritative server profile before returning it to the client.
- Existing canonical identity constraints and `customer_auth_identities` remain unchanged; returning Google/mobile OTP sessions reuse the existing customer rather than creating a duplicate.
- COD collection fields are additive properties in the existing authoritative order/payment state JSON; no destructive payment migration/backfill was added.
- Administrator collection audit remains private in the existing local admin audit store; admin identity is not exposed in customer order APIs.

### Regression / validation results
- Focused post-overlap backend checks: **5/5 PASS** for COD lifecycle, private-admin auth/CSRF, Razorpay rejection, password profile persistence, returning Google/mobile OTP identity reuse, plus receipt ownership/readiness.
- `npm run verify:fast` with the repository-supported Python override pointing to Python 3.12: **PASS** — typecheck PASS, lint PASS, frontend unit **82/82 PASS**, backend **211 PASS + 1 host-specific symlink skip**.
- Full Playwright with `STYLEDASH_E2E_PYTHON` set to Python 3.12: **126/126 PASS** across desktop/mobile, including the new profile persistence browser regression.
- Targeted profile persistence Playwright: **2/2 PASS** across desktop/mobile.
- Production build: **PASS**.
- `git diff --check` / staged diff check: **PASS**.
- Heuristic staged secret scan: **PASS**; no obvious secret-shaped additions found.
- Public admin-lockdown coverage remains green in the backend suite (`/admin` and public `/api/admin/*` remain unavailable).

### Blockers / dependencies
- DEV2 owns Issue 2 professional receipt and Issue 4 homepage merchandising. DEV1 has published the final payment field contract in the canonical coordination file; DEV2 receipt code should consume it read-only.
- DEV2 is concurrently changing `scripts/termux-spa-server.py` only around receipt renderer integration; DEV1 removed receipt-layout-specific edits and retains only order DTO/payment/profile changes to minimize conflict.
- Integration of DEV1 `58b3b9c02d59f7d74d2724d8e31076b1125c189a` with DEV2 must be reviewed and regression-tested before any production deployment.
- Independent Tester/Security review remains required before a release decision because this change touches payment/auth/admin paths.
- Validation-host note: the default Windows `python` resolves to an old Python 3.7 without project dependencies. Tests pass with the supported `STYLEDASH_VERIFY_PYTHON` / `STYLEDASH_E2E_PYTHON` override to installed Python 3.12; this is a local validation-environment issue, not an application failure.

## DEV 2 handoff - 2026-09-04
- Issues owned: Issue 2 Professional Receipt; Issue 4 Homepage merchandising.
- Branch/worktree: `agent/dev2-receipt-home-merch` / `StyleDash-dev2-receipt-home-merch`.
- Base: `6148037e57ac26831d83f0cc2e5d0ba03934899b`.
- Implementation commit: `3c1b9879f57172230d2e1b3a8ee66fd814585b61` (`feat: add professional receipts and homepage merchandising`).
- Frozen UI verification: header, navigation, hero and Shop by Department markup are byte-for-byte unchanged through the frozen boundary.
- Receipt files: `scripts/receipt_pdf.py`, receipt-only wiring in `scripts/termux-spa-server.py`, runtime packaging guard/install in `scripts/termux/deploy-payment-release`, `server/tests/test_receipt_pdf.py`.
- Homepage files: `src/pages/Home.tsx` below frozen area, `src/components/HomepageMerchandising.tsx`, `src/utils/homeMerchandising.ts`, bounded homepage selection in `src/repositories/productRepository.ts`, focused unit/E2E tests.
- DEV 1 dependency resolved: consume existing `paymentStatus` plus optional `paymentCollectionMethod: "cash" | "upi_at_delivery"` and `paymentCollectedAt` read-only. No DEV 2 payment mutation/status source.
- COD receipt behavior: pending => Pending / Pay on Delivery; collected => Paid / Cash or UPI at Delivery using DEV 1 authoritative fields.
- Receipt output: branded A4 invoice, readable IST dates, references, customer/delivery blocks, item table, subtotal/discount/delivery/tax/grand total, payment details, pagination and punctuation normalization.
- Homepage behavior: bounded rows (max 5), View All, duplicate minimization, Weekend Express/New/Trending/Under G�499/Women/Men/Accessories/Beauty & Care plus Local Stores; empty categories are not fabricated.
- Responsive browser coverage: 390, 1366, 1920 and 2560 widths with no page-level horizontal overflow.

## Validation / integration review
- DEV 2 branch: typecheck PASS; lint PASS; frontend 88/88 PASS; backend 213 PASS + 1 host-specific symlink skip; production build PASS; full Playwright 128/128 PASS.
- Receipt-focused tests: 6/6 PASS. Homepage-focused unit tests: 6/6 PASS. Focused homepage Playwright: desktop 2/2 + mobile 2/2 PASS.
- Receipt visual preflight: generated realistic collected-COD A4 PDF and rendered page; no clipping, overlap, broken glyphs, or `?` punctuation corruption observed.
- Hygiene: `bash -n scripts/termux/deploy-payment-release` PASS; `git diff --check` PASS; changed-file secret signature scan 0 findings.
- DEV 1 handoff: implementation `58b3b9c02d59f7d74d2724d8e31076b1125c189a`, docs `992e821166fae01e1b940768f88cc36988e072d8`; branch clean/pushed.
- Disposable DEV1+DEV2 merge review: automatic merge PASS with no conflicts; merged typecheck/lint PASS; frontend 88/88 PASS; backend 217 PASS + 1 host-specific symlink skip; production build PASS; full Playwright 130/130 PASS across 17 files.
- Blockers: no implementation blocker. Release remains blocked on independent Tester + Security + Manager review/approval of the integrated commit.
- Deployment: NOT PERFORMED by DEV 2.

## DEV1 Issue 5 implementation handoff - 2026-09-05
- **TASK:** Issue 5 - secure private-admin product image upload for single-product creation and bulk CSV import.
- **ROLE:** Developer (DEV1). Branch/worktree: `agent/dev1-admin-product-image-upload` / `StyleDash-dev1-admin-image-upload`.
- **BASE COMMIT:** `22d4825724e24c47129ab9cd7b322947e2b68e7b` (approved integrated Issues 1-4 baseline).
- **FILES CHANGED:** `scripts/termux-spa-server.py`, `scripts/termux-admin-server.py`, `server/admin/admin.js`, `server/admin/admin.css`, `server/tests/test_admin.py`, `server/tests/test_styledash_server.py`, this coordination file.
- **Shared media implementation:** seller `/api/shop-product-images` and private admin `/api/admin/product-images` now use the same `store_product_image_payload` storage/validation helper and the existing product-image directory.
- **Admin upload API:** `POST /api/admin/product-images` keeps `{fileName,contentType,dataBase64}` and returns `{success:true,image:{url,bytes,contentType}}`; canonical URL remains `/media/product-images/<32hex>.(webp|jpg|png)`.
- **Admin security:** existing administrator session/TOTP, CSRF, loopback host/origin boundary, generated filenames and fixed media directory are preserved. The public customer server still returns 404 for `/api/admin/product-images`.
- **Validation:** only JPEG/PNG/WebP; strict base64; 500 KB optimized-server limit; structural image checks; dimension bounds; traversal/control-character rejection; client filenames never control stored paths; canonical internal media paths must reference an existing stored file.
- **Single-product UI:** active-shop selector, local multi-image picker as primary workflow, preview, remove/reselect before publish, automatic WebP optimization/upload, generated media paths inserted automatically; HTTPS URLs remain optional compatibility fallback.
- **Bulk contract:** CSV supports `imageFile` plus optional `imageUrls`; admin selects CSV and local files together; exact case-sensitive filename matching; duplicate selected filenames are rejected; required images upload first.
- **Bulk API:** `/api/admin/shop-products/bulk` accepts `{applicationId,csvText,images}` where `images` maps exact CSV filenames to generated canonical media paths; legacy `{applicationId,products}` remains supported.
- **Bulk safety:** server reparses CSV, validates mapped paths and file existence, max 100 product rows / 1 MB request, and refuses the entire publish if a required row image is missing or invalid.
- **Row errors:** missing image example is `Row 1: Image file "missing.jpg" was not selected.`; invalid prices/variants also identify the exact product row.
- **Focused regression:** post-final-change upload/bulk/seller/public-lockdown tests 4/4 PASS; complete admin suite previously 22/22 PASS.
- **Full verification:** `npm run verify:fast` PASS - typecheck PASS, lint PASS, frontend unit 88/88 PASS, backend 219 PASS + 1 host-specific skip.
- **Browser regression:** full Playwright 130/130 PASS across desktop/mobile; production build completed as part of the E2E run.
- **Hygiene:** `git diff --check` PASS; JS syntax PASS; Python compile PASS; changed-diff secret signature scan 0 findings.
- **Real Goutam Shoes preflight:** laptop `product1.jpg`, `product2.jpg`, `product3.jpg` all pass the shared server validator in isolated storage and map exactly to Campus/JQR/Adidas with sizes 6-10 stock 5 each. No production data was changed.
- **DEPLOYMENT:** NOT PERFORMED. No new shop or production product was created and no real payment was executed.
- **RESULT:** Developer PASS for Issue 5 implementation and local regression scope only; this is not production approval.
- **KNOWN RISKS:** successful image uploads can remain unreferenced if a later image/import step fails; they do not cause product publication and remain content-addressed media only.
- **NEXT ROLE:** independent Tester, then Security (admin/CSRF/network-boundary change), then Manager release decision before deployment/production verification.
