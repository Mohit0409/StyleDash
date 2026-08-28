import React from 'react';
import { Link } from 'react-router-dom';
import { SEO } from '../components/SEO';
import { CONFIG } from '../config';

export const Terms = () => (
  <div className="max-w-3xl mx-auto p-8 space-y-6">
    <SEO title="Terms - Vibe4You" />
    <h1 className="text-3xl font-black">Terms of service</h1>

    <p className="text-sm text-neutral-600">
      Vibe4You is currently operated by {CONFIG.LEGAL.PROPRIETOR_NAME} from{' '}
      {CONFIG.LEGAL.ADDRESS}. By placing an order, you agree to these terms and
      the policies linked from them.
    </p>

    <section className="space-y-2">
      <h2 className="font-black">Orders and availability</h2>
      <p className="text-sm text-neutral-600">
        Catalogue availability, serviceability, pricing, discounts, delivery
        charges, and stock are checked by the Vibe4You service when an order is
        submitted. An item shown in the catalogue may become unavailable before
        confirmation. We may reject or cancel an order that cannot be fulfilled
        or that appears fraudulent or abusive.
      </p>
    </section>

    <section className="space-y-2">
      <h2 className="font-black">Pricing and order totals</h2>
      <p className="text-sm text-neutral-600">
        The server-calculated checkout total is the amount used to create an
        order. If an obvious pricing or catalogue error is discovered before
        fulfillment, Vibe4You may cancel the affected order and refund any
        verified payment rather than fulfill at an erroneous amount.
      </p>
    </section>

    <section className="space-y-2">
      <h2 className="font-black">Delivery</h2>
      <p className="text-sm text-neutral-600">
        Delivery estimates are targets rather than guarantees and may change
        because of store acceptance, stock, traffic, weather, address accuracy,
        rider availability, or events outside reasonable control.
      </p>
    </section>

    <section className="space-y-2">
      <h2 className="font-black">Payments</h2>
      <p className="text-sm text-neutral-600">
        Supported orders may use Cash on Delivery or Razorpay checkout. An
        online order is treated as paid only after server-side verification.
        Do not share a CVV or UPI PIN with Vibe4You support staff.
      </p>
    </section>

    <section className="space-y-2">
      <h2 className="font-black">Cancellation, returns, exchanges, and refunds</h2>
      <p className="text-sm text-neutral-600">
        The current cancellation cutoff, exchange window, return conditions,
        pickup charges, issue-reporting period, and refund timing are stated in
        the{' '}
        <Link className="underline font-bold" to="/returns">
          Returns &amp; Exchanges policy
        </Link>
        , which forms part of these terms.
      </p>
    </section>

    <section className="space-y-2">
      <h2 className="font-black">Customer responsibilities</h2>
      <p className="text-sm text-neutral-600">
        Provide accurate account and delivery information, protect your
        password, use only payment methods you are authorized to use, and report
        unauthorized account activity promptly. Fraud, abuse, or attempts to
        interfere with the service may result in order cancellation or account
        restriction.
      </p>
    </section>

    <section className="space-y-2">
      <h2 className="font-black">Consumer rights and applicable law</h2>
      <p className="text-sm text-neutral-600">
        These terms are governed by applicable laws of India. Nothing in these
        terms is intended to waive or restrict rights or remedies that a
        consumer cannot lawfully waive. Disputes may be raised before competent
        consumer authorities, courts, or other forums as provided by applicable
        law.
      </p>
    </section>

    <section className="rounded-xl bg-neutral-100 p-4 text-sm text-neutral-700 space-y-1">
      <h2 className="font-black text-neutral-900">Business and grievance contact</h2>
      <p>Operator: {CONFIG.LEGAL.PROPRIETOR_NAME}</p>
      <p>Grievance officer: {CONFIG.LEGAL.GRIEVANCE_OFFICER}</p>
      <p>
        Email: {CONFIG.LEGAL.SUPPORT_EMAIL} | Phone: {CONFIG.LEGAL.SUPPORT_PHONE}
      </p>
      <p>Support hours: {CONFIG.LEGAL.SUPPORT_HOURS}</p>
    </section>

    <p className="text-xs text-neutral-500">
      Current policy effective date: {CONFIG.LEGAL.POLICY_EFFECTIVE_DATE}.
    </p>
  </div>
);
