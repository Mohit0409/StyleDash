# V4Y Deployment v2 — Phase 1

Status: implementation candidate; not deployed.

Scope: immutable exact-SHA artifact, CI gate, detached Termux transaction,
preflight-before-backup, manifest baseline, focused runtime/security smoke,
automatic managed-runtime rollback, and deployment records.

Excluded: product behavior, payment behavior, auth, pricing, inventory,
database schema/data, admin authorization, and backup-format optimization.

Acceptance evidence is supplied by `server/tests/test_vibe_deployment_v2.py`,
the complete existing regression suite, independent Tester/Security reviews,
and the GitHub required CI run for the PR. Production deployment needs separate
owner authorization after those gates pass.
