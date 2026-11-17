# Vibe4You active frontend runtime reference — 2026-11-16

This is a byte-exact copy of already **publicly served, deployed
frontend artifacts**, captured read-only from Ubuntu. It is NOT
the editable React/Vite source, a deployer, or a fully reproducible
frontend *build*.

The production integrity manifest SHA-256 is:
ec13b4f28f99b26f3cf468412d77a651b8596decc1cb5afb1012170bac11a126

Captured 134 public paths, including the active homepage HTML, its
21 direct first-party script/link resources, potential literal-asset
dependencies derived from the current Search V2 R2 bundle, and public
PWA icons/service worker/offline fallback. The potential dependency graph is an
OVER-APPROXIMATION of literal references, NOT a browser network trace.

- 123 files are pinned by the production integrity manifest.
- 11 are served and readable but not recorded in that manifest.
  Their captured bytes were independently checked against live
  disk SHA-256 and origin HTTP response SHA-256.
- 134 / 134 bytes and lengths verified before staging to this branch.
- No private orders, credentials, customers, or payment data are copied.
- A basic secret-pattern screen found no flagged files.

Untracked items include the main deployed stylesheet,
a lazy-loaded Home stylesheet, PWA service worker/offline fallback,
app manifest/installer and icon files. Their absence from the
existing live integrity manifest is a future release-coverage gap.
DO NOT modify the production manifest independently of the guarded
release and backup process.

windows-artifact-provenance.json records exact Windows release-artifact
matches for direct homepage assets when a matching copy was found.
Those may be BUILT outputs, NOT editable original source.

The old Windows Vite build still produces a different main bundle.
Before claiming complete source alignment, identify and integrate
the editable Search V2 R2 and overlay sources, verify Vite outputs
and browser E2E/checkout, and perform an owner-approved release.
This reference should never be deployed straight to production.

The independent overlay/PWA tranche is now pinned separately by
`deployment-targets/vibe4you-20261116-r2/frontend-overlay-source-map.json`
and can be validated or staged offline with
`scripts/assemble_pinned_frontend_overlays.py`. See
`../FRONTEND_OVERLAY_INTEGRATION.md`. That boundary is not a claim of typed
React integration or complete Vite source parity.
