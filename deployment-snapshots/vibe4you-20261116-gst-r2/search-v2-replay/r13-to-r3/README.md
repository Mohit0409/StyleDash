# V4Y-056 R13 -> V4Y-055 R3 reproducible compiled release

This public-code archive captures the ORIGINAL V4Y-055 R3 release builder
and the SHA-256-pinned previously deployed V4Y-056 R13 compiled storefront
on 2026-11-12.

## Offline verification

Run from the isolated StyleDash worktree:

    py -3.12 scripts/replay_r13_to_r3_offline.py

The tool checks 53 R13 JavaScript chunks plus index.html (54 inputs),
a pinned original Python builder, a pinned R13 release SHA manifest and
a public Android Digital Asset Links file.

It runs the historical builder with Python isolated flags in a NEW
temporary folder, then validates every one of the 56 generated R3
files (53 JS, homepage HTML, public assetlinks.json, SHA256SUMS).
The 54 generated website code files also match the canonical R3
baseline used for the later Search V2 -> R2 release-chain replay.

Both checkout payment retry and homepage section icon improvements
are in the original builder. No edits to payment APIs, catalog, fees
or customer order state were made to produce this replay.

## Verified chain to production

1. 54-file public, *already-compiled* V4Y-056 R13 input
2. 56-file V4Y-055 R3 output: 54 storefront code files plus public
   assetlinks.json and SHA256SUMS
3. 54-file Search V2 compiled output
4. 54-file Search V2 Relevance R2 output. These final 54 hashes
   also match the pinned, read-only current Ubuntu public snapshot.

All stages have fail-closed SHA-256 checks. Steps 3 and 4 additionally
rebuild their TypeScript search bridges with pinned esbuild 0.21.5.

IMPORTANT: This chain starts from **compiled R13 assets**, not
React/TypeScript source. It does NOT yet prove a complete reproducible
frontend build starting solely from editable JSX/TSX. Separately
deployed overlays, PWA files, CSS and marketing/review additions
must also be integrated and browser-tested before production release.

This tool writes exclusively to disposable OS-temp paths. It is NOT
a deployment utility, does not access production, and does not touch
private data, live orders, tax invoices, or payments.
