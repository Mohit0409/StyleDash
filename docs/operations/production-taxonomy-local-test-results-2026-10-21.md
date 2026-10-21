# Local validation of production taxonomy reconciliation — 2026-10-21

This evidence concerns the editable StyleDash source branch and its 19-category production taxonomy synchronization. It is **not** a claim of complete parity with the live Ubuntu server.

## Completed checks on Windows 11

- Backend full unittest discovery (server/tests/test_*.py): 339 tests, all passing, 4 skipped; exit 0.
- Frontend full Vitest suite: 193 tests in 35 files, all passing; exit 0.
- ESLint: exit 0.
- Production frontend build: exit 0.
- Bulk CSV / multi-image Node UI tests: exit 0.
- TypeScript project build/typecheck: exit 0.
- Admin JavaScript syntax: exit 0.
- Relevant separate catalogue/security suites: 12 catalogue and 19 security tests passed.
- Both frontend and backend originally reported stale assertions referring to the old seven-category vocabulary. The tests were updated to match the existing 19-category production specification; they pass.

## GitHub Actions blocker

A GitHub-hosted check run for this PR failed on attempts 1 and 2 before any steps executed, with no job logs. The workflow is enabled, and preceding days had successful runs. The root cause was not established from the available Actions metadata.

The PR remains draft and must not be merged or deployed automatically until hosted checks are executing and approved.

## Safeguards

- Tests were run on an isolated clean worktree. Existing changes in the owner's primary StyleDash checkout are untouched.
- The live server and production database were not modified.
- Source-only changes cover the 19-category vocabulary, boots normalization and generated category tags.
- The exact production runtime code is preserved separately in the private Vibe4You-Production-Mirror, with SHA-256 verification.
- The build reported an existing nonfatal duplicate package.json overrides-key warning; this source-sync PR does not modify package manager overrides.