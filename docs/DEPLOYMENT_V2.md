# Vibe4You Deployment v2

Deployment v2 replaces the release-specific, interactive surgical procedure
with one owner-run Windows command and a detached Termux transaction. It does
not deploy automatically after a merge and it never performs a real payment.

## Normal owner flow

1. Merge the approved PR into `main`.
2. Wait for the exact commit's **StyleDash Required CI** check to pass.
3. From a Windows checkout that has the private public frontend build values in
   its ignored `.env`, run:

   ```powershell
   .\ops\deploy-vibe4you.ps1
   ```

4. Confirm `DEPLOYMENT PASS`.

To deploy an already merged, exact approved main SHA instead, run:

```powershell
.\ops\deploy-vibe4you.ps1 -Commit <40-character-main-sha>
```

The wrapper refuses a SHA not merged into `origin/main`, a missing/failed exact
SHA CI gate, incomplete production Firebase public values, or a missing local
SSH identity. It uses `git archive`, so a dirty root worktree is not cleaned,
stashed, reset, or used as deployment input.

The wrapper builds a fresh immutable artifact from that SHA, checks its
allowlisted contents and SHA-256, uploads it, and asks the Termux runner to
perform preflight. The full frontend/backend/Playwright regression suite is
not rerun on the phone: GitHub CI is the exact-SHA test authority. Only the
focused runtime and security smoke suite runs on production.

## Other owner commands

```powershell
.\ops\deploy-vibe4you.ps1 -PreflightOnly
.\ops\deploy-vibe4you.ps1 -Status
.\ops\deploy-vibe4you.ps1 -Resume
```

`-PreflightOnly` validates the artifact and live runtime without starting a
backup or changing production. Its successful terminal output includes:

```text
PRELIGHT PASS
BACKUP_NOT_STARTED       YES
PRODUCTION_MUTATED       NO
```

`-Status` reads the private transaction state. `-Resume` reuses the same
release/artifact transaction. If its fresh pre-mutation backup already passed,
it is not started again. A changed SHA, artifact checksum, live baseline, or
failed preflight invalidates the transaction and stops safely.

## What the Termux transaction does

The Termux entry point is `~/bin/vibe-deploy` after the first successful v2
deployment. The first v2 command safely runs the staged runner directly. It
uses a private lock and `nohup`/`setsid`; an SSH disconnect from Windows does
not terminate the backup or deployment. A later command finds the existing
transaction and reports its state rather than starting an overlapping backup.

Private state and logs are under:

```text
~/.local/share/styledash/deployments/
  current.json
  history/<timestamp>-<sha>.json
  transactions/<sha>-<artifact>/state.json
  records/<date>-<sha>.md
~/logs/vibe-deploy-<transaction>.log
```

The live production identity is always `https://vibe4you.in`. The runner never
uses `~/run/styledash-public-url`, which belongs to the diagnostic ngrok tool.
It does not follow redirects for sensitive-route checks.

Preflight happens before backup and validates artifact provenance/checksum,
safe contents, syntax, Firebase/analytics configuration, SQLite integrity and
foreign keys, process identity, loopback listeners, disk, canonical-origin
health, sensitive public paths, managed-file baseline, protected files, and
rollback/staging ownership/path safety.

The first v2 transaction accepts the existing live baseline only by matching
the audited `780cde2…` runtime hashes and the retained approved analytics
frontend tree in `ops/deployment-v2-bootstrap.json`. Later transactions match
the last successful private deployment manifest. Unexplained managed-file drift
fails before backup.

After preflight, exactly one fresh existing-format backup runs. Its stages are
reported as `BACKUP_LOCAL`, `BACKUP_PRIMARY_COPY`, `BACKUP_PRIMARY_VERIFY`,
`BACKUP_SECONDARY_COPY`, and `BACKUP_SECONDARY_VERIFY` when those remotes are
configured. Backup format optimization is deliberately a separate Phase 2.

After mutation, v2 checks public/admin process identity, local and canonical
health, homepage and product APIs, a published product page, login route,
private admin loopback, sensitive route denials, SQLite integrity/FK state,
protected hashes, installed artifact hashes, Firebase, analytics, and payment
configuration presence. It does not place an order or contact Razorpay.

## Failure and rollback

If preflight fails, backup has not started and production is not mutated. If
backup fails, runtime mutation does not start. If an error occurs after
mutation, the runner stops only the managed services, restores the exact
pre-deployment managed files and frontend snapshot, restarts the prior managed
services, rechecks health/integrity/baseline, and reports
`AUTOMATIC_ROLLBACK=PASS` or `AUTOMATIC_ROLLBACK=FAIL` with
`MANUAL_RECOVERY_REQUIRED`.

The transaction never restores `styledash.db`, orders, payments, inventory, or
customer data from an old backup. A captured-payment inconsistency remains a
manual reconciliation incident, not a rollback shortcut.

## Records and intervention

Each successful deployment writes immutable JSON history and a non-sensitive
Markdown record on Termux. The Windows wrapper copies that record to
`docs/deployments/` when the checkout permits it.

Developer/Codex intervention is needed only for a failed CI gate, unexplained
baseline drift, failed backup, failed automatic rollback, an intentional
runtime-write-set expansion, or a new/changed required public build value.
Normal successful releases need only the four-step owner flow above.
