# Vibe4You Ubuntu Artifact Manifest Reseal

The Ubuntu public and admin launchers verify
`.migration/artifact-files-remediated.sha256` before Python starts.

A reviewed frontend deployment that changes `server/index.html` or adds a
fingerprinted file under `server/assets/` must keep that startup manifest current.
Otherwise the currently running process can remain healthy while the next restart or
reboot fails closed.

Use:

```bash
scripts/ubuntu/reseal-vibe4you-artifact-manifest \
  server/index.html \
  server/assets/<new-reviewed-asset>.js
```

The helper is intentionally narrow. It permits only `server/index.html` and
`server/assets/...` targets. It does not permit Python runtime modules, configuration,
secrets, database files, admin security files, or arbitrary paths.

Before writing, the helper verifies every manifest entry not explicitly named for the
reviewed frontend release. Any unrelated mismatch blocks the reseal.
For an accepted reseal it:

1. hashes only the explicitly approved frontend paths;
2. preserves the previous manifest beside the live manifest;
3. writes the candidate manifest atomically;
4. verifies the complete resulting manifest;
5. restores the old manifest automatically if final verification fails.

A release is not complete merely because HTTP health is green. Before a reboot window,
also verify the complete artifact manifest and restart the public/admin services from
systemd so the same startup gate exercised at boot has already been proven.

Test the helper without production access using:

```bash
python server/tests/test_ubuntu_artifact_manifest.py
```

Do not weaken or remove the launcher integrity check to work around a stale manifest.
