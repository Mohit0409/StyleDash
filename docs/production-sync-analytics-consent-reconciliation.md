# Original analytics/consent reconciliation

The seven tracked analytics, consent, and attribution paths from the original Windows checkout have been reviewed against the current isolated synchronization branch.

## Decision

`PASS` - retain the current consent implementation; no dirty source file needs to be ported.

The current branch already mounts the consent dialog and route tracker, exposes Analytics Preferences in the footer, delays Google Analytics and Meta Pixel until explicit acceptance, revokes consent and expires known cookies on withdrawal, suppresses sensitive routes, records the add-to-cart event, and publishes the matching privacy disclosure.

It also includes two important improvements beyond the dirty version: the public GA identifier is validated with a synchronized fallback, and the `gtag` shim queues the real JavaScript `arguments` object required by Google Consent Mode.

The dirty attribution helpers were not copied. They append selected query parameters and a sanitized referrer, while the active privacy notice promises that query strings and fragments are excluded from page-view tracking. The current implementation keeps page locations query-free and sends an empty referrer.

The dirty ecommerce wrapper and Neemuch route/homepage work depend on untracked files. They are not admitted through this privacy-sensitive bundle and would also regress current inventory or merchandising behavior if copied wholesale.

The per-file decisions and preserved privacy invariants are recorded in [original-analytics-consent-reconciliation.json](../deployment-snapshots/vibe4you-20261116-gst-r2/original-analytics-consent-reconciliation.json).

No tracker, consent value, environment, deployment, service, or production state was changed.
