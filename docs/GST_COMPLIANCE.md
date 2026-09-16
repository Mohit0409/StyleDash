# Vibe4You GST / marketplace compliance

Registration source: Form GST REG-06 issued 16 September 2026.

- Legal name: Manorama
- Trade name: Vibe4You
- GSTIN: 23JVZPM8734E1ZT
- Registration: Regular, effective 2026-09-16
- Principal place: H-5, Alkaloid Colony, Industrial Area Jhanjharwada, Neemuch, Madhya Pradesh 458441

## Current rollout state
The owner has explicitly instructed that GST must **not be applied to any product yet**.

The current GST rollout is therefore limited to displaying the Vibe4You GSTIN in customer billing/checkout information and marketplace receipt identity. Product GST calculation, product GST rates, HSN billing data and GST amounts are disabled for customer billing until separately authorized.

The payment settings use `taxRate: 0`. Checkout does not add GST to the payable amount, and the receipt does not show a product-GST amount.

## Marketplace receipt
The customer PDF is explicitly a **Marketplace Receipt** and identifies Vibe4You/Manorama and GSTIN 23JVZPM8734E1ZT. Goods remain identified by their store/supplier. Product GST is not calculated or charged on the current marketplace receipt.

## Deferred work
HSN/rate classification and product-level GST implementation are intentionally deferred. Do not enable them merely because metadata or historical code exists; owner authorization is required first.

The monthly TCS reconciliation utility is deferred while product GST/HSN billing is disabled; it emits no filing rows and does not alter customer totals or product pricing.

## Operational actions outside code
- Display the REG-06 certificate prominently at the registered place of business.
- Verify GST portal and marketplace/ECO filing obligations with the tax professional/portal.
- Maintain seller, order, return/refund and settlement records for later reconciliation.
- Do not infer that displaying the GSTIN means product GST collection has been enabled.
