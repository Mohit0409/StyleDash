import React from 'react';
import { SEO } from '../components/SEO';

export const Terms = () => <div className="max-w-3xl mx-auto p-8 space-y-6">
  <SEO title="Terms - StyleDash" />
  <h1 className="text-3xl font-black">Terms of service</h1>
  <section><h2 className="font-black">Orders and availability</h2><p className="text-sm text-neutral-600">Catalogue availability, serviceability, pricing, discounts, delivery charges, and stock are confirmed by the StyleDash server when an order is submitted. An item shown in the catalogue may become unavailable before confirmation.</p></section>
  <section><h2 className="font-black">Delivery</h2><p className="text-sm text-neutral-600">Delivery estimates are targets rather than guarantees and may change because of merchant acceptance, stock, traffic, weather, address accuracy, or rider availability.</p></section>
  <section><h2 className="font-black">Payments</h2><p className="text-sm text-neutral-600">Supported orders may use Cash on Delivery or Razorpay checkout. An online order is treated as paid only after server-side verification. Do not share a CVV or UPI PIN with StyleDash staff.</p></section>
  <section><h2 className="font-black">Customer responsibilities</h2><p className="text-sm text-neutral-600">Provide accurate account and delivery information, protect your password, and report unauthorized account activity promptly. Misuse, fraud, or attempts to interfere with the service may lead to account restriction.</p></section>
  <p className="rounded-xl bg-amber-50 text-amber-900 p-4 text-sm"><strong>Legal review required:</strong> the business identity, governing law, cancellation/refund rules, liability terms, and verified contact details must be approved before Live Mode.</p>
</div>;
