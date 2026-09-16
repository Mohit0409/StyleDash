# Vibe4You GST / marketplace compliance

Registration source: Form GST REG-06 issued 16 September 2026.

- Legal name: Manorama
- Trade name: Vibe4You
- GSTIN: 23JVZPM8734E1ZT
- Registration: Regular, effective 2026-09-16
- Principal place: H-5, Alkaloid Colony, Industrial Area Jhanjharwada, Neemuch, Madhya Pradesh 458441

## Product tax data
Private Admin product create/edit supports `HSN code` and `GST rate %`. These are product-specific compliance fields. Do not guess either value. Confirm the HSN and current rate for the exact product before production use.

Checkout remains tax-inclusive. The server snapshots HSN, GST rate, taxable value and included GST on each order line. Existing products without product-specific tax metadata retain the pre-existing 5% fallback until their tax classification is reviewed; this fallback is compatibility behavior, not a legal classification.

## Marketplace receipt
The customer PDF is explicitly a **Marketplace Receipt**, identifies Vibe4You/Manorama and the GSTIN, and states that goods are supplied by the named stores. It does not misrepresent Vibe4You as the supplier tax invoice issuer for third-party goods.

## TCS reconciliation
Section 52 TCS is tracked separately from customer GST. Effective 10 July 2024 the total TCS rate is 0.5% (0.25% CGST + 0.25% SGST for intra-state supplies; 0.5% IGST for inter-state supplies). Vibe4You currently serves Neemuch and the report exposes the intra-state split.

Generate a read-only monthly reconciliation:

`python scripts/gst_tcs_report.py --state /path/to/orders.json --month 2026-09 --output /safe/private/path/gst-tcs-2026-09.csv`

The report intentionally flags supplier GSTIN as required rather than inventing it. Supplier registration/tax status must be verified before filing GSTR-8. Returns/refunds and seller settlements must be reconciled against actual books before filing.

## Filing / operational actions outside code
- Display the REG-06 certificate prominently at the registered place of business.
- Complete/verify GST portal bank details and the registration needed for ECO/TCS obligations with the tax professional/portal.
- File GSTR-8 and deposit applicable TCS by the statutory deadline.
- Keep seller GST registration/status, HSN/rates, supplier invoices, returns/refunds and settlement records reconciled.
- Do not deploy this branch until existing published products have been reviewed for HSN/GST rate and regression/security review is complete.
