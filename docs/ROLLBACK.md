# Vibe4You deployment rollback

Deployment v2 automatically rolls back managed code/static files when runtime
acceptance fails after mutation. It does not restore the authoritative SQLite
database, orders, payments, inventory, or customer data.

## Normal automatic path

The deployment status should end with one of:

```text
AUTOMATIC_ROLLBACK=PASS
```

or:

```text
AUTOMATIC_ROLLBACK=FAIL
MANUAL_RECOVERY_REQUIRED
```

For a PASS, use `.\ops\deploy-vibe4you.ps1 -Status` to confirm the prior
runtime identity and record the incident. Do not start a new deployment until
the failure cause has been fixed and reviewed.

## Manual recovery gate

For rollback failure, stop release work. Preserve the private transaction
directory, log, artifact checksum, rollback snapshot reference, current
database, and Razorpay/webhook evidence. Do not overwrite or restore the live
database from a backup.

An authorized maintainer must inspect the exact private transaction state and
restore only the managed runtime snapshot if necessary, then verify public
`/api/health`, private-admin loopback, sensitive-route denials, SQLite
integrity/FK state, and the prior deployment manifest. If any captured payment
is inconsistent, reconcile it through verified Razorpay payment/order/webhook
data before accepting new affected traffic.
