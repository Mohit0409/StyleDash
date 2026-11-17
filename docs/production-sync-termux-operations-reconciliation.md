# Original Termux operations reconciliation

The three tracked Termux operation-script changes from the original Windows checkout have been reviewed against the pinned Ubuntu/systemd release contract.

## Decision

`PASS` - do not port any Termux script into the Ubuntu release path.

The dirty payment deployment script adds validation and installation for the billing-audit and invoice modules. Those seven modules are already represented by thirteen explicit Admin/Public targets in the hash-pinned Ubuntu source map. Copying the Termux deploy script would add a second, incompatible activation path without adding candidate coverage.

The dirty backup scripts also contain useful operational principles: refuse overlapping runs, verify off-device copies with bounded retries, and include supplier-bill artifacts in backup and recovery coverage. These are recorded as requirements for a future Ubuntu-specific backup and recovery design. They are not copied because the scripts depend on Termux paths, phone services, and mutable runtime configuration.

Supplier bills, databases, order state, product images, and private configuration are runtime backup inputs. They remain forbidden from the source-only release candidate. The candidate still has no activation mechanism, and the old Termux installer remains explicitly disallowed.

The exact file decisions, pinned module targets, and future Ubuntu requirements are recorded in [original-termux-operations-reconciliation.json](../deployment-snapshots/vibe4you-20261116-gst-r2/original-termux-operations-reconciliation.json).

No production, service, backup, restore, database, payment, or deployment action was performed.
