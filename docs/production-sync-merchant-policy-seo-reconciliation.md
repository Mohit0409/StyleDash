# Original merchant-policy/SEO reconciliation

The five tracked merchant-policy and SEO-shell paths from the original Windows checkout have been reviewed independently.

## Decision

`PASS` - selectively port the conditional merchant-policy structured data and its browser assertion.

Product pages now emit an organization-level `MerchantReturnPolicy` record linking to the published `/returns` page. It does not claim a universal return window or fee, which would be inaccurate for conditional, hygiene-sensitive, or merchant-specific products. The browser test also confirms that product offers do not publish unsupported `shippingDetails`.

The generic keyword-oriented HTML/SEO shell rewrite was not copied; the synchronized branded shell and route-specific/generated discovery metadata remain authoritative. The Returns and Terms edits were also rejected because they mix the current no-advance COD model with historical INR 50 booking-advance refund and forfeiture rules. Publishing either model through legal copy is unsafe until the payment bundle is reconciled.

The per-file decisions are recorded in [original-merchant-policy-seo-reconciliation.json](../deployment-snapshots/vibe4you-20261116-gst-r2/original-merchant-policy-seo-reconciliation.json).

No legal policy, payment behavior, deployment, service, or production state was changed.
