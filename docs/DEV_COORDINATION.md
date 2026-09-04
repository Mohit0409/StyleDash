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
