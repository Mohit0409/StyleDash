# Ubuntu backend release-candidate architecture — 2026-11-17

## Result

The existing 60-target production source map is now integrated into a
deterministic, Ubuntu-layout release candidate. This is an offline candidate
builder and verification contract, not a production activation tool.

Read-only inspection of the current Ubuntu host confirmed:

- production root: `/opt/vibe4you-production`;
- public systemd unit: `vibe4you-production-public.service`, executing
  `/opt/vibe4you-production/run-public.sh` as `vibe4you:vibe4you`, with working
  directory `/opt/vibe4you-production`, `NoNewPrivileges=yes`,
  `ProtectSystem=strict`, and public application bound to `127.0.0.1:8080`;
- Admin systemd unit: `vibe4you-production-admin.service`, executing
  `/opt/vibe4you-production/run-admin.sh` with the same service identity and
  hardening, while Admin remains private on `127.0.0.1:8081`;
- tunnel unit: `vibe4you-cloudflared.service`; its credential file remains in
  `/etc/vibe4you-production` and no credential contents are represented here.

These observations are pinned in
`deployment-targets/vibe4you-20261116-r2/ubuntu-release-contract.json`
(SHA-256 `d7b78dd49e6f06250bb3401f8702723fd8bd50581099b81f6c52d88e885b3909`).

## Candidate layout

`scripts/build_pinned_ubuntu_release_candidate.py` produces only a new
directory under the operating-system temporary directory:

```text
candidate/
  payload/admin/                 33 exact production targets
  payload/server/                27 exact production targets
  candidate-manifest.json        deterministic target hashes and sizes
  SHA256SUMS                     deterministic payload hash list
  source-map.json                exact pinned source map
  ubuntu-release-contract.json   exact observed safety contract
```

The payload paths match the current flat Ubuntu production root, but the
builder cannot copy them there. It has no SSH, systemd, sudo, service restart,
database, backup, or activation implementation.

## Preserved runtime boundary

The contract excludes and preserves the existing run scripts, `bin/`, `venv/`,
`private/`, frontend `server/assets/`, generated `server/index.html`, and all
`/etc/vibe4you-production` configuration. Database/WAL/SHM files, backups,
logs, secrets, tokens, credentials, caches and bytecode are forbidden from the
candidate. The separate Admin and Public `serve.py` files remain different and
are never flattened.

The older Termux installer is explicitly disallowed. It does not model the
current Ubuntu systemd/service ownership boundary and must not be pointed at
this production host.

## Verification

```text
python scripts/build_pinned_ubuntu_release_candidate.py --check
python -m unittest server.tests.test_pinned_source_assembly server.tests.test_pinned_ubuntu_release_candidate
```

The combined focused suite has 20 passing tests. It covers the original source
assembly plus exact candidate construction, deterministic metadata, service
isolation, generated-homepage exclusion, forbidden private/runtime paths,
contract and payload tampering, unexpected files, destination restrictions,
and absence of an activation CLI.

## Future human-gated activation work

No production activation is implemented or authorized. A future Ubuntu
activation tranche needs independent Tester and Security review, full backend
and storefront regression, read-only live target comparison, SQLite integrity
and validated online backup gates, explicit owner approval, an Ubuntu-specific
staging/atomic code-switch mechanism, post-activation public/Admin/tunnel
boundary checks, and a code-only rollback that never replaces current
database/payment/GST history.

No production file, service, database, order, payment, customer record,
invoice, backup, or original Windows checkout was changed during this work.
