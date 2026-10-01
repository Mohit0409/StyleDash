# Vibe4You Ubuntu Production Operations Handover — Draft

Status date: 2026-10-01

This document is a draft until the controlled reboot-recovery test is completed. It contains no passwords, API keys, payment secrets, Firebase credentials, TOTP secrets, SSH private keys, or Cloudflare tunnel tokens.

## Production host

Host: vibe4you-server
Ubuntu LAN address: 192.168.1.14
Application root: /opt/vibe4you-production
Persistent data: /var/lib/vibe4you-production
Local backup root: /var/backups/vibe4you-production

The old Android/Termux Vibe4You production stack is intentionally stopped and must not be started unless performing an explicit rollback. Never operate both hosts as writable production at the same time.

## Production services

Required system units:
- vibe4you-production-public.service
- vibe4you-production-admin.service
- vibe4you-cloudflared.service
- vibe4you-backup.timer

Verified on 2026-10-01:
- all four units enabled
- all four units active
- zero failed systemd units at inspection time
- public service bound to loopback port 8080
- admin service bound to loopback port 8081
- services are system units and do not depend on interactive login

Cloudflare is configured to restart automatically. Public and admin restart on failure.

## External verification

Verified:
- https://vibe4you.in/ returned HTTP 200
- https://vibe4you.in/api/health returned HTTP 200 with service and database ok
- https://admin.vibe4you.in/ returned HTTP 302 through the admin access layer

Sensitive public paths verified as HTTP 404:
- /admin
- /api/admin/orders
- /backups
- /logs
- /styledash.db
- /.env

## Backup status

Daily timer:
- OnCalendar: 03:00 UTC
- RandomizedDelaySec: 10 minutes
- Persistent: true

Latest verified backup during this review:
- stamp: 20261001T033524Z
- primary encrypted off-device: 801 matching files, 0 differences
- Windows secondary disaster recovery: 801 matching files, 0 differences
- backup service exit: success
- elapsed time: about 14 minutes 23 seconds

Next timer at the time of inspection:
- 2026-10-02 03:08:10 UTC
- 2026-10-02 08:38:10 IST

The deployed Ubuntu backup script was preserved byte-for-byte in Git on the isolated operations branch before any refactoring. Its baseline SHA-256 is 41f64f6144884bc0fe7ba6a72a14d77a6e952bac07bba67eda0457f8b67a809f.

The Ubuntu script remains separate from the legacy Termux backup script because their filesystem paths and runtime assumptions differ.

## Restore proof

A restore test was performed from the Windows off-device disaster-recovery snapshot 20261001T033524Z into an isolated temporary directory.

Results:
- backup source files: 801
- restored files: 801
- source product images: 799
- restored product images: 799
- SHA-256 mismatches: 0
- unexpected restored files: 0
- SQLite PRAGMA integrity_check: ok

This proves the secondary backup can be restored into an isolated location with byte-identical contents and a valid SQLite database.

The repository contains scripts/ubuntu/verify-restored-backup.py so the verification can be repeated.

## Storage and retention

Ubuntu root filesystem at inspection:
- capacity: 216 GB
- used: about 10 GB
- free: about 197 GB
- utilization: 5 percent

Persistent system journal usage: about 40 MB.

Windows secondary disaster-recovery storage:
- snapshots: 266
- oldest observed stamp: 20260821T161908Z
- newest observed stamp: 20261001T033524Z
- total files: 43,578
- total bytes: about 5.16 GB

The current backup script keeps 14 local snapshots but does not delete off-device snapshots. Do not delete historical backups yet. Define an explicit off-device retention policy after the migration safety period.

Recommended future retention approach after approval:
- preserve recent daily recovery points
- preserve less-frequent weekly/monthly recovery points for longer
- never prune the only known-good restore point
- perform pruning only after a fresh verified backup
- exclude migration rollback archives from automated pruning until their separate safety period expires

## Monitoring candidate

The isolated operations branch contains a candidate health checker that verifies:
- required systemd units enabled and active
- application health JSON and database status
- public/admin external reachability
- disk percentage and minimum free bytes
- local, primary and secondary backup freshness
- SQLite integrity of the latest local backup

Default candidate thresholds:
- backup age: 36 hours
- disk usage: alert at 85 percent
- disk free: alert below 20 GiB

A candidate ntfy-compatible alert helper and systemd health timer are also present in the branch. They are not installed on production.

The alert helper:
- is disabled unless explicitly configured
- does not print notification secrets
- throttles duplicate alerts to once per hour by default

## Logging

Vibe4You system services currently log through systemd journal. The journal is persistent and occupied about 40 MB during inspection. The standard logrotate timer is enabled and active for traditional logs.

No global journald change is currently justified by disk pressure. Monitor growth before introducing a server-wide journald retention override.

## Reboot readiness

Configuration-level checks pass:
- production services are system-level units
- required units are enabled
- Cloudflare waits for network-online and requires the public service
- backup timer is persistent and enabled
- no interactive user login is required

A real controlled reboot has not yet been performed after migration. Therefore full reboot recovery is not yet considered proven.

Do not perform the reboot casually during customer traffic. Use an approved maintenance window and verify all services and external endpoints immediately after boot.

## Rollback assets

Keep untouched for now:
- old Android/Termux final production snapshot
- Ubuntu pre-final-cutover archive
- earlier pre-candidate archive
- Firebase-related rollback material
- rollback script

Recommended minimum old-host safety period: 30 days after cutover, no earlier than approximately 2026-10-31 and only after stable daily backups, restore proof, monitoring, and reboot proof.

Recommended migration rollback archive safety period: approximately 90 days, through late December 2026, unless a reviewed retention policy requires longer.

## Git preservation

Isolated branch:
agent/ubuntu-production-ops-20261001

Worktree:
.worktrees/ubuntu-production-ops-20261001

Commits created during post-migration hardening:
- 206201f ops: preserve Ubuntu production backup baseline
- 2753fb9 ops: add Ubuntu restore verification and health monitoring candidates

The historically dirty root StyleDash worktree was not reset, cleaned, merged, or used as a release workspace.

The operations branch has not been deployed to production.

## Remaining gates

Before calling the migration fully operationally hardened:
1. Review the monitoring candidate and secure alert configuration.
2. Take a fresh rollback copy before installing monitoring components.
3. Install and validate the healthcheck one-shot without changing application services.
4. Enable the healthcheck timer and verify alert delivery using a non-destructive test condition.
5. Observe at least one normal scheduled backup under monitoring.
6. Perform a controlled Ubuntu reboot in an approved maintenance window.
7. Reverify public, admin, Cloudflare, backup timer, health JSON, sensitive paths, and no interactive-login dependency.
8. Finalize this handover document and only then begin the old-host decommissioning decision.

## Safety rules

- Do not expose production secrets in Git, logs, or troubleshooting output.
- Do not perform a real payment transaction as a health test.
- Do not restart the old Android/Termux stack except for an explicit rollback.
- Do not overwrite the proven production backup script from an unreviewed repository copy.
- Do not use the dirty root worktree for production release work.
- Do not modify Gravity Fitness, Need For Strength, Universal Gym, or unrelated projects as part of Vibe4You operations.
## Monitoring installation result — 2026-10-01

Monitoring has now been installed on the Ubuntu production host.

Installation sequence:
- the first one-shot healthcheck failed safely before the timer was enabled
- failure reason: latest_backup_db_unreadable
- root cause: SQLite read-only integrity verification needed immutable mode under the hardened service sandbox
- fix: open the backup database using mode=ro&immutable=1
- repair commit: 863ab6c
- repaired healthcheck passed
- healthcheck timer is enabled and active
- two consecutive healthcheck executions returned VIBE4YOU_HEALTH=PASS
- the initial failure triggered the operations notification path and logged VIBE4YOU_OPS_ALERT=SENT
- public, admin, Cloudflare, and the existing backup timer remained active throughout

Current healthcheck cadence:
- OnBootSec: 3 minutes
- OnUnitActiveSec: 5 minutes
- RandomizedDelaySec: 30 seconds
- Persistent: true

The initial test failure consumed the alert helper's one-hour duplicate-alert throttle for the same event. Health checks continue to run and log during that window; notification throttling expires automatically.

The monitoring repair created/preserved rollback material under:
- /var/backups/vibe4you-production/pre-monitoring-20261001T050230Z

Do not remove that rollback material during the migration safety period.

## Updated remaining gates

Completed:
- Ubuntu backup implementation preserved in Git
- isolated restore from Windows secondary proven
- SQLite restore integrity proven
- product-image count proven
- service/disk/backup/database monitoring installed
- operations notification delivery proven
- healthcheck timer enabled and passing

Still outstanding:
1. Observe at least one normal scheduled production backup while monitoring is active.
2. Perform a controlled Ubuntu reboot in an approved maintenance window.
3. After reboot, verify public, admin, Cloudflare, backup timer, monitoring timer, external routes, and sensitive-path blocking.
4. Finalize this handover after reboot recovery is proven.
5. Only then begin the old Android host decommissioning decision.