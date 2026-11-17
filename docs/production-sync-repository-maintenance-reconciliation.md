# Original repository-maintenance reconciliation

The two tracked repository-maintenance changes from the original Windows checkout have been reviewed independently.

## Decision

`PASS` — retain the lint exclusion; reject the stale deployment-status prose.

`.eslintrc.cjs` now excludes `tmp`, alongside `dist` and `node_modules`. Temporary tool installations, extracted artifacts, and generated workspaces are not authored TypeScript source and should not change lint results. No lint rule was disabled or weakened.

The original `docs/DEV_COORDINATION.md` addition was not copied. It records an October Termux COD rollout using then-current “live now” hashes and paths. Production now uses the separately verified Ubuntu/systemd contract and the hash-pinned November source snapshot. Copying the old mutable status into current coordination documentation would misrepresent the active release baseline.

The underlying no-online-advance COD behavior is already preserved by the current public server source and regression suite. This decision rejects only stale release-status text, not the verified behavior.

The per-file decisions are recorded in [original-repository-maintenance-reconciliation.json](../deployment-snapshots/vibe4you-20261116-gst-r2/original-repository-maintenance-reconciliation.json).
