# Vibe4You staging network/credential release preflight

**Review-only.** This QA helper is an OFFLINE policy check. It neither reads secret values nor makes any network requests or account changes. Do not mistake a green synthetic fixture for proof that an active server is isolated.

The owner has already separated staging's Linux user/group and staging filesystem ACLs. The staging service currently has PrivateNetwork=no, no configured IPAddressDeny/Allow, and shares the host loopback with the 8080/8081 production listeners. Staging itself listens on loopback 18080. These findings require a further security project, not an unapproved service restart.

For a snapshot of **sanitized configuration and real audit evidence**, run:

    python qa/staging_external_boundary_gate.py --snapshot safe_metadata.json

The gate refuses a release if the inspected environment has:
- a shared production Unix identity, a production EnvironmentFile reference, or an unsafe public origin;
- live Razorpay mode, live/payment/mail credential variable names, or enabled ordering/notifications;
- a shared host network without service-level network policy;
- missing independent runtime evidence that production localhost APIs are denied to staging, nonlocal egress is restricted, authentication credentials are distinct, and staging remains healthy after the network policy.

Runtime evidence is supplied as booleans by a separate authorized reviewer. The validator **does not certify their provenance**. A future hardening task must choose network namespace/proxy and/or firewall restrictions carefully so that the staging health endpoint remains reachable. IPAddressDeny=any + IPAddressAllow=localhost alone would NOT block production on localhost and is insufficient.

Do not test by sending real payments, creating orders, sending notifications, logging into production, or accessing sensitive production data. Do not copy production secrets into staging.

No production/staging service file, data, payment integration or secret is altered by this change.

## Shared Firebase frontend project is a separate release blocker

An independent static dependency-graph check of the actual staging and production
entrypoint bundles found that their reachable Firebase client code uses matching
projectId, authDomain, appId, and apiKey values. These are public client identifiers,
but none of their raw values are recorded in reports. Simply creating a separate
Firebase *app* in the same project would not isolate default Firebase Auth users.

The gate now requires a trusted comparison of the currently referenced frontend
bundles and explicit evidence that the staging Firebase project ID and auth
domain differ from production. Omission or a known shared configuration fails.
The separate frontend project check does not replace backend/provider credential
separation checks, tenancy validation, or authorization rules review.
