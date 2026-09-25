# Surgical Combined Release Procedure

This procedure exists for reviewed releases that must update only the
approved storefront/runtime write set while preserving production-only Admin,
configuration, security, payment, order, and database state. The release pins
both the current live runtime hashes and the exact staged replacement hashes so
an unexpected live change blocks deployment before mutation.

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
- `~/server/catalog_normalization.py`
- `~/server/styledash_shops.py`
- the customer frontend files from `dist/`
- `~/admin/serve.py`
- `~/admin/styledash_reviews.py`
- `~/admin/catalog_normalization.py`
- `~/admin/styledash_shops.py`
- `~/bin/backup-styledash-data`
- `~/bin/start-styledash-cloudflare`

It does not copy the stage's security, catalogue, settings, delivery-zone,
secret, payment, order, or database files. `catalog_normalization.py` and
`styledash_shops.py` are the only category/shop runtime modules in the write
set, and both their current-live and staged SHA-256 values must match the
release-specific pins before mutation.

Before mutation it records SHA-256 values for protected public/private
`styledash_security.py`, the live private Admin `index.html` and `admin.js`,
authoritative catalogue/settings/delivery-zone configuration, and `secrets.env`.
Those protected hashes must remain unchanged after the copy and after rollback.

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

For the commission/MRP release, the verified current live runtime is:

- `catalog_normalization.py`: `a656e8a56c9f9d1e91a70508b34e99f48f247e72e3838b9a0af8b4fc68654417`
- `styledash_shops.py`: `23d6f7c2a53bbca3fec06e1f25ff1a7bdb6632ced0751daea51eaa4df532fda0`

The staged `styledash_shops.py` replacement must be
`a78f30d94376dca74c9f8dbb048990906f448768c541ab1b5cc5124466d8587e`.
This procedure being present in source does not mean it has been run in
production. Production deployment remains a separate human-approved action.
