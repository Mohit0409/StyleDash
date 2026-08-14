# StyleDash self-hosted services

The Android/Termux deployment has two deliberately separate listeners:

- `127.0.0.1:8080`: public customer SPA, customer APIs, Razorpay API and webhook.
- `127.0.0.1:8081`: private administrator UI/API, reachable only through SSH forwarding.

The public listener has no `/admin` route, no administrator login, and no
`/api/admin/*` implementation. Customer registration always creates a customer.
The private listener uses separate Argon2id administrator identities, hashed
sessions, password then encrypted-TOTP verification, one-use recovery codes,
separate CSRF, shorter timeouts, and local audit records. See `ADMIN.md`.

## Private Termux environment

Server secrets belong only in `~/.config/styledash/secrets.env` with mode 600:

```bash
RAZORPAY_MODE=test
RAZORPAY_TEST_KEY_ID=rzp_test_replace_with_fresh_key
RAZORPAY_TEST_KEY_SECRET=replace_with_fresh_api_secret
RAZORPAY_TEST_WEBHOOK_SECRET=replace_after_creating_the_test_webhook
RAZORPAY_LIVE_KEY_ID=rzp_live_replace_only_when_ready
RAZORPAY_LIVE_KEY_SECRET=replace_only_when_ready
RAZORPAY_LIVE_WEBHOOK_SECRET=replace_with_the_existing_live_webhook_secret
STYLEDASH_TOTP_ENCRYPTION_KEY=generate_privately_on_the_phone
STYLEDASH_ENABLE_TEST_PRODUCT=false
STYLEDASH_TEST_PRODUCT_ALLOWED_EMAILS=owner-account@example.invalid
```

Never use a `VITE_*` variable for credentials. Only a Razorpay key ID is
returned to an authenticated browser after server-side order creation.

## Authoritative data

- Catalog: `~/.local/share/styledash/catalog.json`
- Service/pricing settings: `~/.local/share/styledash/settings.json`
- Proven payment/order/inventory state: `~/.local/share/styledash/runtime/orders.json`
- Customer and separate local-admin SQLite data: `~/.local/share/styledash/styledash.db`
- Private backups: `~/.local/share/styledash/backups/`
- Private environment: `~/.config/styledash/secrets.env`

The payment JSON is intentionally retained during this staged migration to
protect the already-proven exactly-once Razorpay/inventory behavior. Both Python
processes coordinate access with a Termux `flock`, reload state after acquiring
the process lock, and use atomic replacement. Migration to SQLite remains a
separate backup-and-reconciliation-gated operation.

## Public customer endpoints

- `GET /api/health`
- `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me`
- `POST /api/auth/logout`, `POST /api/auth/change-password`
- `POST /api/auth/password-reset/request`, `POST /api/auth/password-reset/confirm`
- `GET /api/profile`, `PATCH /api/profile`
- `GET /api/orders`, `GET /api/orders/:id`
- `POST /api/vendor-applications`
- `POST /api/create-order`, `POST /api/verify-payment`, `POST /api/place-cod-order`
- mailbox-verified owner session only: `GET /api/payment-test-product/styledash-payment-test-item`
- mailbox-verified owner session only: `POST /api/payment-test-product/styledash-payment-test-item/create-order`
- `POST /api/webhooks/razorpay`

Razorpay Test and Live credentials are isolated. Keep `RAZORPAY_MODE=test` until
all manual customer/admin/reboot gates pass; deployment never enables Live Mode.

The temporary ₹10 payment-validation item is disabled unless
`STYLEDASH_ENABLE_TEST_PRODUCT=true`. Access is authorized exclusively from the
normalized authenticated-session email against the comma-separated private
`STYLEDASH_TEST_PRODUCT_ALLOWED_EMAILS` value **and** a server-stored
`email_verified_at` mailbox-possession proof. Registration and ordinary login do
not establish that proof, and legacy `email_verified` values are deliberately
not trusted. An existing owner establishes proof by requesting a password reset,
using the one-time token delivered to that mailbox, completing the reset, and
signing in again after the old sessions are revoked. The public reset-request
response remains generic. Do not use a `VITE_*` variable, URL query, browser
storage, request-body email, or request-body verification field for this
authorization. The item is intentionally absent from the catalogue and has no
COD, coupons, wallet credit, tax, delivery charge, fashion inventory, or
fulfillment. Turning the flag off blocks new validation orders while preserving
payment history.

## Razorpay Live-readiness policy

StyleDash fulfills online orders only after Razorpay reports a captured payment:
the browser callback verifies its signature and then fetches the payment from
Razorpay, while `payment.captured` and `order.paid` webhooks use the same
exactly-once finalizer. An `authorized` payment remains pending and never changes
inventory or marks an order paid.

Use Razorpay Dashboard **Automatic Capture** for all payments authorised within
3 days. With that policy, late-authorised payments are either auto-captured and
later finalized by `payment.captured`/`order.paid`, or auto-refunded by Razorpay;
`payment.authorized` is therefore not a fulfillment dependency.

The Live webhook URL must be the public HTTPS `/api/webhooks/razorpay` endpoint
and subscribe to `payment.captured`, `payment.failed`, `order.paid`,
`refund.failed`, and `payment.dispute.created`. Refund failures and newly created
disputes create persistent, idempotent alerts visible only in the private admin
service. They never change inventory, refund automatically, or rewrite a paid
order's successful payment history.

## Verification

```bash
python3 -m unittest discover -s server/tests -v
~/bin/backup-styledash-data
~/bin/verify-option-b-release
```

Password recovery stores only a token hash, expires tokens after 30 minutes,
invalidates prior unused tokens, and revokes all customer sessions on success.
The request endpoint always returns the same response for known and unknown
accounts. Delivery failure invalidates the newly created token. A successfully
consumed emailed reset token also records the durable mailbox-possession time
used by the controlled payment-validation gate; changing a password from an
existing session does not establish mailbox verification.

Password-reset SMTP configuration belongs only in
`~/.config/styledash/secrets.env` (mode `600`):
`STYLEDASH_SMTP_HOST`, `STYLEDASH_SMTP_PORT`, `STYLEDASH_SMTP_USERNAME`,
`STYLEDASH_SMTP_PASSWORD`, `STYLEDASH_PASSWORD_RESET_FROM`, and
`STYLEDASH_PASSWORD_RESET_URL`. Do not add these to browser variables, source,
or logs.
