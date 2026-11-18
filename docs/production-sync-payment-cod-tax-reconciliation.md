# Payment, COD, and tax-invoice reconciliation

The current direct COD contract is retained: new COD orders use `/api/place-cod-order`, require no online advance, and collect the full amount on delivery. UPI and card orders continue through Razorpay with server-side verification.

The dirty bundle was not coherent. Its checkout and browser test say no COD advance, while its payment unit test requires `/api/create-order` and a ₹50 Razorpay booking amount. It also removes the browser test that proves successful placement, tracking, receipt state, and cross-account `404` isolation.

The tax-invoice tracking UI was held with its backend contract. It cannot be promoted before the invoice ledger, issuance gates, authentication, ownership/IDOR behavior, and Ubuntu deployment path are independently reviewed.

Only one narrow test assertion was admitted: customer checkout source must not reintroduce `Pay ₹50 to Place COD Order`. The retained payment tests passed 18/18, and the real COD placement plus cross-account isolation browser flow passed.

No payment, order, inventory, invoice, database, service, deployment, or production state was changed. Release status remains `MANUAL ACTION REQUIRED`.
