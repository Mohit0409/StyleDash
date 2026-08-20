# StyleDash production reliability

This repository keeps production data authoritative on the Termux host. The
reliability layer adds off-device backup support, health/restart notifications,
and code/config rollback while preserving live customer and payment history.

## Off-device SQLite backups

`~/bin/styledash-health` runs the existing integrity-checked online SQLite
backup once per UTC day. Configure a private rclone remote on the Termux host
and add these values to `~/.config/styledash/secrets.env`:

```sh
STYLEDASH_BACKUP_REMOTE=styledash-crypt:StyleDash/production
STYLEDASH_REQUIRE_OFFDEVICE_BACKUP=true
```

Use an encrypted/private rclone remote suitable for production customer data.
Do not upload production database backups to the source repository.

Each scheduled backup:

1. uses SQLite's online backup API;
2. runs `PRAGMA integrity_check` on the local backup;
3. copies the timestamped backup to the configured rclone destination with
   immutable semantics; and
4. downloads/checks the remote copy before recording the off-device marker.

Local retention remains 14 timestamped backups. The script does not
automatically delete remote backups.

## Owner notifications

The watchdog reuses the existing ntfy integration. Configure privately:

```sh
STYLEDASH_NTFY_ENABLED=true
STYLEDASH_NTFY_BASE_URL=https://ntfy.sh
STYLEDASH_NTFY_TOPIC=replace-with-private-topic
```

Notifications contain only operational state. They do not include customer,
payment, TOTP, Firebase credential, or other secret values.

The watchdog checks public port `8080` and private admin port `8081`, restarts
each independently, and notifies on unhealthy/restart-failed/recovered state.
Backup and ngrok failures are also reported.

## Deployment rollback

Every release records its pre-release code/config snapshot in:

```text
~/run/styledash-last-release-backup
```

To restore the latest pre-release executable/config snapshot:

```sh
~/bin/rollback-payment-release
```

The rollback command creates a fresh local online data backup first, restores
only code plus catalog/settings configuration, and then verifies both local
services. It never restores an older production database or historical order
state over current live financial/customer data.

A specific managed pre-release snapshot may be supplied as the sole argument.
