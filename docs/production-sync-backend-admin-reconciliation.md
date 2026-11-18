# Backend, admin, and coupled-test reconciliation

The remaining dirty backend reference, private admin UI, and coupled backend-test bundles were reviewed together because their routes and state transitions are inseparable. No dirty implementation or test was ported.

Every one of the nine dirty source/admin files differs from its pinned live target. The synchronized branch already matches the pinned live receipt generator and all three admin assets byte-for-byte, so replacing those files would discard verified production lineage.

The dirty public server is internally unsafe to promote as a unit: it rejects new COD checkout payments because COD now needs no online advance, while retaining legacy ₹50 booking-advance creation and administration paths. The same bundle also raises the retained 20-combination product limit to 100, reintroduces a static category taxonomy, and couples supplier-bill storage, GST classification, invoice issuance, per-product commission, private WhatsApp links, and COD collection controls to new Termux-era routes.

Those capabilities may be useful, but they require independently designed Ubuntu-native changes with explicit payment, ownership/IDOR, CSRF, storage, invoice, tax, privacy, and rollback review. Their dirty tests must travel only with that reviewed implementation.

The current six-module regression run completed 225 tests: 223 passed and two review-eligibility tests failed again in isolation. The current and pinned-live review workflow reports a customer eligible before a qualifying delivered order exists. That baseline defect is recorded as a separate release blocker and was not silently repaired inside this reconciliation.

Result: the three bundles are evidence-complete but remain `MANUAL ACTION REQUIRED`. No production or runtime state was changed.
