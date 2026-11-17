# Reproducible selected code-target assembly: Vibe4You GST R2

OFFLINE ONLY - not a release tool, deployer or complete website build.

source-map.json pins 60 backend/static production target files to exact
Windows source paths and SHA-256 values. 58 are directly represented by
the non-sensitive production-code snapshot, with a two-target authentic
GST Phase 1 registry recovered by matching the protected file hashes in
the verified live manifest.

Sixteen target-specific source files are kept separately under targets/.
Admin and Public modules are never silently merged or overwritten.
The single generated server/index.html is EXCLUDED because current
Vite source does not yet reproduce the Search V2 R2+overlays storefront.

The historical Termux deployer is NOT updated, and this map cannot
be used to deploy to the live Ubuntu server. The assembly script only
validates source byte hashes and optionally writes a local temporary
staging directory. It cannot stage private state, customer data, secrets,
or assets outside this explicit 60-file allowlist.

`frontend-overlay-source-map.json` independently pins 25 public frontend
files: 14 standalone overlays, two compiled CSS references and nine static
PWA outputs. `scripts/assemble_pinned_frontend_overlays.py` applies the same
offline/new-temp-directory boundary. It deliberately excludes the generated
homepage and Search V2 R2 main bundle and is not connected to a deployer.

`ubuntu-release-contract.json` records the read-only observed Ubuntu service
boundary around the 60 backend/static targets. The offline
`scripts/build_pinned_ubuntu_release_candidate.py` builder emits a deterministic
temporary candidate with separate 33-file Admin and 27-file Public payloads,
exact source-map/contract copies, a manifest and SHA256SUMS. It cannot activate
the candidate, contact production, restart systemd or include runtime state.
See `deployment-snapshots/vibe4you-20261116-gst-r2/UBUNTU_BACKEND_RELEASE_ARCHITECTURE.md`.

This snapshot is NOT a claim about the complete Vibe4You production manifest
or a full deployable source tree. Align runtime entrypoint dependencies and
current frontend assets; run acceptance/security checks before changes.
