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
- `GET /api/profile`, `PATCH /api/profile`
- `GET /api/orders`, `GET /api/orders/:id`
- `POST /api/vendor-applications`
- `POST /api/create-order`, `POST /api/verify-payment`, `POST /api/place-cod-order`
- `POST /api/webhooks/razorpay`

Razorpay Test and Live credentials are isolated. Keep `RAZORPAY_MODE=test` until
all manual customer/admin/reboot gates pass; deployment never enables Live Mode.

## Verification

```bash
python3 -m unittest discover -s server/tests -v
~/bin/backup-styledash-data
~/bin/verify-option-b-release
```

Customer self-service password recovery is deferred until an approved SMTP or
transactional-email configuration exists. Reset tokens already have a private,
hashed, expiring, single-use schema and must never be returned to public clients.
