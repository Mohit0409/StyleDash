# Original mobile filter bundle reconciliation

The two tracked mobile-filter changes from the original Windows checkout have been reconciled selectively.

## Decision

`PASS` — one source hunk and its browser assertion are retained.

The synchronized drawer previously made the complete panel scrollable. On shorter mobile viewports, that allowed the primary `Apply Filters` action to move below the visible area. The reconciled layout now has:

- a width bounded by the viewport;
- a scrollable filter-content region;
- a non-scrolling footer containing the primary action;
- bottom padding that respects the device safe-area inset.

The original dirty diff also removed comments and compressed most JSX onto single lines. Those formatting-only hunks were excluded.

The Playwright regression verifies the action remains fully inside 390x844 and 768x1024 viewports, remains visible after a filter interaction, and preserves the existing outside-click dismissal and body-scroll restoration behavior.

The exact comparison and selective decisions are recorded in [original-filter-dismiss-reconciliation.json](../deployment-snapshots/vibe4you-20261116-gst-r2/original-filter-dismiss-reconciliation.json).

This is editable-source reconciliation only. It does not deploy or claim parity with the pinned live compiled frontend.
