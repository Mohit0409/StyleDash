# Original Windows checkout: 68-path tracked audit

Observed read-only on 2026-11-17. No file in `C:/movieXsuggestion/MyProject/StyleDash` was edited, staged, reset, cleaned, or copied into this branch.

## Result

`MANUAL ACTION REQUIRED`

The 68 tracked status paths are not one releasable change set. They contain 65 real content diffs and three status-only paths. Four working files already equal this synchronization branch. The remainder mixes sensitive/runtime configuration, a rejected policy-file deletion, obsolete Termux operations, production-divergent backend/admin code, tests coupled to that code, and several frontend feature bundles with untracked dependencies.

The machine-readable inventory is [original-tracked-audit.json](../deployment-snapshots/vibe4you-20261116-gst-r2/original-tracked-audit.json).

## Fixed observations

- Original branch: `agent/dev-admin-session-reset-main`
- Original HEAD: `2c3e6e7bc400502516467869c370264e27d069aa`
- Relationship to observed `origin/main`: ahead 1, behind 140
- Tracked status paths: 68
- Content diffs: 65
- Status-only: `src/context/AuthContext.tsx`, `src/services/authApi.ts`, and `vite.config.ts`
- Staged paths: 0
- Visible untracked paths: at least 4,239; the scan was incomplete because some cache/tool directories were unreadable

The status-only paths and `src/context/ToastContext.tsx` are already byte-equivalent to the synchronization branch, so they require no port.

## Production comparison

Nine dirty backend/admin candidates were SHA-256 compared with every live target in the pinned source-mapping audit. There were zero exact matches. They are therefore development evidence, not recovered production source:

- `scripts/catalog_normalization.py`
- `scripts/receipt_pdf.py`
- `scripts/styledash_security.py`
- `scripts/styledash_shops.py`
- `scripts/termux-admin-server.py`
- `scripts/termux-spa-server.py`
- `server/admin/admin.css`
- `server/admin/admin.js`
- `server/admin/index.html`

The existing target-specific Ubuntu sources and pinned live hashes remain authoritative for release-candidate assembly.

## Blocking inconsistencies

The checkout contains two incompatible COD directions: the checkout UI and browser test say COD requires no online advance, while the payment API tests still create and authorize a COD booking advance. The dirty Termux server also contains both retired-advance commentary and advance-handling paths. This payment bundle must not be copied or partially cherry-picked.

Several tracked frontend changes import files that are untracked in the original checkout, including catalog taxonomy, ecommerce analytics, product presentation/assurances, Neemuch route data, and the Neemuch page. Those dependencies must be provenance-reviewed with their consumers. A tracked-only patch would be incomplete.

## Disposition

1. Keep the four already-synchronized paths as-is in this branch.
2. Never copy `.env.e2e` or runtime settings values. Review `.env.example` only as a redacted template.
3. Reject deletion of `AGENTS.md`.
4. Do not port the three Termux backup/deploy scripts into the Ubuntu/systemd release flow.
5. Treat backend/admin diffs as feature evidence only; re-implement selectively against the pinned public/admin source contracts.
6. Reconcile the COD model before any payment-related port, then require independent security review.
7. Review each remaining frontend bundle with its dependencies and tests; do not bulk-add the untracked surface.

No merge, deployment, production write, database mutation, service restart, payment, or refund was performed.
