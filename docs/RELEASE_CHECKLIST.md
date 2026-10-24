# Vibe4You release checklist

## Before the owner command

- [ ] PR is approved and merged to `main`.
- [ ] Exact merged SHA has **StyleDash Required CI: PASS**.
- [ ] Tester review PASS and Security review PASS are recorded for changes that
  affect production tooling, runtime, security, data, payment, or deployment.
- [ ] No secrets, runtime database, backup, or customer data are in the diff.
- [ ] The owner has not authorized a real payment or production configuration
  change beyond this approved release.

## Owner command

```powershell
.\ops\deploy-vibe4you.ps1
```

- [ ] Confirm `DEPLOYMENT PASS`.
- [ ] If it fails before mutation, resolve the reported preflight/backup issue;
  do not retry by bypassing the check.
- [ ] If it reports rollback failure, stop release work and follow
  `docs/ROLLBACK.md`.

## After a successful deployment

- [ ] Verify the generated non-sensitive record under `docs/deployments/`.
- [ ] Record the final SHA, CI URL, and deployment record in the deployment
  track/Jira item.
- [ ] Do not run a live Razorpay payment as a routine smoke test.

## Phase 2 gate

Archive-based backup optimization requires a separate PR with benchmark data,
isolated restore proof, primary/secondary verification, Tester PASS, and
Security PASS. It is not part of deployment v2 Phase 1.
