# V4Y-046 editable-source provenance — 2026-11-17

## Result

The historical editable source candidate has been identified and built, but
V4Y-046 was not produced by one ordinary React/Vite build.

Source commit `748ac8a60e1665bd7dbd4261ef1816423a5ad342` on
`origin/feature/store-compact-statistics-20261015` is the closest recorded
editable predecessor. A fresh export installed 370 packages offline and built
successfully with Vite 5.4.21. It emitted 54 JavaScript chunks after
transforming 1,676 modules.

That build does **not** reproduce V4Y-046 exactly:

- exact raw module equality: **0/53**;
- equality after replacing only graph-local JavaScript basenames and
  normalizing CRLF/LF: **43/53**;
- source-build-only chunk: `storeRating`;
- different modules: `Categories`, `Checkout`, `ProductDetail`, `Profile`,
  `StoreDetail`, `Stores`, `VendorOnboarding`, `categories`, `index`, and
  `paymentApi`.

The narrow normalization exists only to distinguish filename/newline release
rewrites from code differences. It is not exact build parity.

## Release composition established

The evidence supports this composition:

1. PR150 compiled graph associated with source commit `748ac8a`.
2. Five PR150 modules already differ from the fresh source build, while the
   editable build contains an additional `storeRating` chunk.
3. Six recorded compiled files were replaced in place: `index`, `Profile`,
   `ProductDetail`, `Checkout`, `categories`, and `VendorOnboarding`.
4. V4Y-045 applied five anchored changes directly to the compiled Checkout
   module and rewrote the graph suffix.
5. V4Y-046 rewrote the suffix again, inserted the deferred social script into
   the HTML, and replaced `Categories` with a captured post-minification patch.

The fresh source build matches 48/53 PR150 modules under the same narrow
filename/newline normalization. The five differences are `Checkout`,
`StoreDetail`, `Stores`, `index`, and `paymentApi`.

## Categories source search

The deployed Categories chunk contains the deliberately preserved identifiers
`V4Y_PH`, `V4Y_Pick`, and `V4Y_Thumb`. Its 5,080 bytes are the 3,726-byte
suffix-renamed predecessor plus 1,354 inserted characters and no deletions.

No Git commit containing those identifiers was found. No checked-out
`src/pages/Categories.tsx` contained the deployed thumbnail-selection logic.
The historical staging folder contains the compiled assets, index, manifests,
plan, and deploy script, but no React source or original Categories builder.

This is consistent with a direct post-minification insertion, not a missing
ordinary TypeScript build.

## Reproduction

The pinned source commit remains in the same GitHub repository on
`origin/feature/store-compact-statistics-20261015`. Export it into a disposable
worktree, then run:

```text
py -3.12 scripts/build_v4y046_source_candidate_offline.py --source-tree <disposable-worktree>
py -3.12 scripts/verify_v4y046_editable_source_provenance.py --candidate-assets <disposable-worktree>/dist/assets
```

The builder uses `npm ci --offline --ignore-scripts`, strips inherited Vite and
secret-like environment variables, derives only the four browser-visible
Firebase fields in memory from the pinned public bundle, and performs no
production or provider request.

## Acceptance status

Priority 2 provenance is now classified, but complete editable-source parity
remains **not achieved**. The correct next source task is to reconstruct and
test typed equivalents of the ten differing modules and the independent
overlays. A source build must not be deployed merely because it compiles or
because 43 normalized modules match.

No production, database, customer, payment, or GitHub-main change occurred.
