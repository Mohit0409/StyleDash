# Vibe4You Ubuntu Production Operations

This directory preserves Ubuntu-specific operational scripts separately from the legacy Android/Termux scripts.

## Baseline provenance

backup-styledash-data was copied byte-for-byte from the deployed Ubuntu production host on 2026-10-01 after two fully verified 801-file backups completed successfully to both off-device destinations.

Production path: /opt/vibe4you-production/bin/backup-styledash-data

Baseline SHA-256: 41f64f6144884bc0fe7ba6a72a14d77a6e952bac07bba67eda0457f8b67a809f

Do not overwrite the deployed production copy directly from this repository. Any future deployment must use a reviewed release procedure, a rollback copy, and post-deployment backup verification.

The legacy scripts/termux/backup-styledash-data remains separate because its filesystem paths and runtime assumptions are different.

## Restore proof

On 2026-10-01 the Windows secondary backup stamp 20261001T033524Z was copied to an isolated temporary directory and verified without touching production.

Results:
- source files: 801
- restored files: 801
- source product images: 799
- restored product images: 799
- SHA-256 mismatches: 0
- SQLite PRAGMA integrity_check: ok

Use verify-restored-backup.py to repeat this source-versus-restore verification.

## Monitoring candidates

vibe4you_healthcheck.py checks:
- required systemd units are enabled and active
- local application health reports service and database ok
- public/admin external reachability
- disk usage and minimum free space
- freshness of local, primary off-device and secondary backup markers
- SQLite integrity of the latest local backup

Default thresholds:
- backup freshness: 36 hours
- maximum disk use: 85 percent
- minimum free disk space: 20 GiB

vibe4you_ops_alert.py is an optional ntfy-compatible failure notifier. It is disabled unless explicitly configured and throttles duplicate alerts for one hour by default. It does not print the notification topic or other secret configuration.

The systemd files in scripts/ubuntu/systemd are candidates only and are not installed on production by committing them.

## Outstanding production proof

A controlled Ubuntu reboot is still required before claiming full reboot-recovery proof. Perform it only in an approved maintenance window, then re-check public/admin/tunnel services, the backup timer, external endpoints, and sensitive-path blocking.