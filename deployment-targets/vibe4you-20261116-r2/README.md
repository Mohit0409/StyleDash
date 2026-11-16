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

This snapshot is NOT a claim about the complete Vibe4You production manifest
or a full deployable source tree. Align runtime entrypoint dependencies and
current frontend assets; run acceptance/security checks before changes.
