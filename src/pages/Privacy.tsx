import React from 'react';
import { SEO } from '../components/SEO';

export const Privacy = () => <div className="max-w-3xl mx-auto p-8 space-y-6">
  <SEO title="Privacy - StyleDash" />
  <h1 className="text-3xl font-black">Privacy notice</h1>
  <p className="text-sm text-neutral-600">StyleDash stores account, contact, delivery-address, cart-related order, payment-reference, and vendor-application information needed to operate the service.</p>
  <section><h2 className="font-black">Payments</h2><p className="text-sm text-neutral-600">Online payment entry is handled by Razorpay. StyleDash stores payment and order identifiers and verification state, but must never receive or store card numbers, CVV, or UPI PIN.</p></section>
  <section><h2 className="font-black">Use and access</h2><p className="text-sm text-neutral-600">Customer data is used for account access, fulfillment, support, fraud prevention, and payment reconciliation. Customers can access only their own profile and orders. Authorized local administration may access fulfillment information.</p></section>
  <section><h2 className="font-black">Storage and retention</h2><p className="text-sm text-neutral-600">Application data is stored on the privately operated StyleDash server and in protected backups. Reasonable security controls reduce risk but no system can guarantee absolute security.</p></section>
  <p className="rounded-xl bg-amber-50 text-amber-900 p-4 text-sm"><strong>Business details required:</strong> the data-controller identity, privacy contact, retention periods, and deletion/request procedure must be confirmed before Live Mode.</p>
</div>;
