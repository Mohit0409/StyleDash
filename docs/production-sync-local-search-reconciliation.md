# Original local-search bundle reconciliation

The five tracked NMH/Neemuch local-search changes from the original Windows checkout have been reconciled without copying its mixed dirty patch.

## Decision

`PASS` — no source port is required.

The original checkout's untracked `src/utils/localSearch.ts` is byte-identical to the file already present in this synchronization branch. The synchronized search implementation is also newer and more complete than the original patch:

- `parseSearchQuery` centrally calls `normalizeLocalShoppingQuery`.
- Product catalogue matching flows through `parseSearchQuery` and `scoreProductSearch`.
- Store results in `Products.tsx` flow through `scoreStoreSearch`.
- Search suggestions already normalize the query before ranked matching.

The original `Products.tsx` change combined local-search behavior with unrelated SEO title, description, and heading edits. Those hunks were intentionally excluded and remain part of the separate merchant-policy/SEO review bundle.

Two explicit regression cases were retained in the current test suite:

- catalogue queries treat NMH and Neemuch as equivalent and a place-only query does not empty the catalogue;
- suggestion results are identical for equivalent NMH and Neemuch-qualified searches.

A focused Playwright case also verifies that the real products route returns the expected local store for `royals in NMH`.

The exact comparison and per-file decisions are recorded in [original-local-search-reconciliation.json](../deployment-snapshots/vibe4you-20261116-gst-r2/original-local-search-reconciliation.json).

This reconciliation makes no editable-source-to-live-bundle parity claim. The pinned production frontend capsule remains the deployment-integrity authority.
