# Surgical Combined Release Procedure

This procedure exists because the normal `deploy-payment-release` command
copies the complete staged runtime. Production currently contains newer
category-rule files that are intentionally outside the combined lag, review,
storefront, and backup-tool release. A full-tree deployment would overwrite
those live files.

## Supported command

After the release archive has been extracted and independently verified on the
Termux host, run:

```sh
bash STAGING_DIRECTORY/scripts/termux/deploy-surgical-combined-release \
  STAGING_DIRECTORY
```

Do not run `deploy-payment-release` for this release.

## Exact write set

The surgical command can replace only:

- `~/server/serve.py`
- `~/server/styledash_reviews.py`
- the customer frontend files from `dist/`
- `~/admin/serve.py`
- `~/admin/styledash_reviews.py`
- `~/bin/backup-styledash-data`
- `~/bin/start-styledash-cloudflare`

It does not copy the stage's category, security, shop-rule, catalogue,
settings, delivery-zone, secret, payment, order, or database files.

Before mutation it records SHA-256 values for both public and private copies
of `styledash_security.py`, `catalog_normalization.py`, and
`styledash_shops.py`, the live private Admin `index.html` and `admin.js`, plus
authoritative catalogue/settings/delivery-zone configuration and `secrets.env`.
The same hashes must match after the copy and after any automatic rollback.

The private Admin frontend is deliberately preserved in this release because
production contains live-only Admin hotfixes that are not yet reconciled into Git.

## Backup and rollback

The command first requires the supported `~/bin/backup-styledash-data` process
to finish successfully. That command owns SQLite online-backup, integrity,
foreign-key, and configured off-device replication verification.

The code/static rollback snapshot is created under:

```text
~/backups/styledash-surgical-combined.XXXXXX/
  public/runtime/
  public/static/
  admin/runtime/
  ops/
```

Public and Admin files never share a rollback namespace. In particular, their
two `serve.py` files cannot overwrite each other.

After the snapshot is complete, the command stops the watchdog, explicitly
stops the verified public and Admin processes, waits for ports 8080 and 8081
to be released, and only then installs files. The new PID for each service
must differ from its pre-release PID.

Any error after mutation starts invokes automatic code/static rollback. The
rollback never restores an older database, payment state, order state, or
customer data.

## Required acceptance checks

The command refuses success unless all of these pass:

- local public health returns HTTP 200;
- public `/admin` returns HTTP 404;
- public `/api/admin/me` returns HTTP 404;
- `/api/shop-products/homepage` returns HTTP 200;
- `/api/shop-products/published` still returns HTTP 200;
- private loopback Admin returns HTTP 200;
- SQLite `PRAGMA integrity_check` is `ok`;
- SQLite `PRAGMA foreign_key_check` returns zero rows;
- protected live hashes remain identical;
- public and Admin are each served by exactly one verified new process;
- the existing Cloudflare tunnel remains a single verified HTTP/2 process;
- the health watchdog is restored only after the runtime checks pass.

Public-origin smoke tests, browser regression, latency measurement, and the
release documentation closeout still follow the command. Never automate a
real Razorpay Live payment.

## Current status

This procedure being present in source does not mean it has been run in
production. Production deployment remains a separate human-approved action.
