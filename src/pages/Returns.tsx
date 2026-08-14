import React from 'react';
import { Link } from 'react-router-dom';
import { SEO } from '../components/SEO';
import { CONFIG } from '../config';

export const Returns = () => (
  <div className="max-w-3xl mx-auto p-8 space-y-6">
    <SEO title="Returns & Exchanges - StyleDash" />
    <h1 className="text-3xl font-black">Returns and exchanges</h1>

    <p className="text-sm text-neutral-600">
      This policy applies to orders placed through StyleDash in the current
      service area. Keep the item unused, unwashed, unaltered, with original
      tags and packaging until your request is reviewed.
    </p>

    <section className="space-y-2">
      <h2 className="font-black">
        {CONFIG.LEGAL.EXCHANGE_WINDOW_DAYS}-day size exchange
      </h2>
      <p className="text-sm text-neutral-600">
        Eligible items may be requested for a size exchange within{' '}
        {CONFIG.LEGAL.EXCHANGE_WINDOW_DAYS} calendar days after delivery.
        Exchanges depend on replacement-stock availability.
      </p>
    </section>

    <section className="space-y-2">
      <h2 className="font-black">Wrong, damaged, defective, or missing item</h2>
      <p className="text-sm text-neutral-600">
        Report an item that arrived wrong, damaged, defective, or materially
        incomplete within {CONFIG.LEGAL.ISSUE_REPORT_WINDOW_DAYS} calendar days
        after delivery. Include the order reference and clear photos where
        relevant.
      </p>
    </section>

    <section className="space-y-2">
      <h2 className="font-black">Eligibility</h2>
      <p className="text-sm text-neutral-600">
        We may decline a return or exchange if the item has been worn beyond
        normal fitting, washed, altered, damaged after delivery, or returned
        without its original tags or packaging. Hygiene-sensitive items cannot
        be accepted after opening or use where a return would be unsafe or
        inappropriate.
      </p>
    </section>

    <section className="space-y-2">
      <h2 className="font-black">Pickup and exchange charges</h2>
      <p className="text-sm text-neutral-600">
        A customer-choice return pickup may carry a â‚¹
        {CONFIG.LEGAL.RETURN_PICKUP_FEE} pickup charge. A size exchange may
        carry a â‚¹{CONFIG.LEGAL.EXCHANGE_PICKUP_FEE} pickup/exchange charge.
        These charges are waived when StyleDash confirms that the item was
        wrong, damaged, defective, or not as ordered.
      </p>
      <p className="text-sm text-neutral-600">
        Return and exchange assistance is handled during{' '}
        {CONFIG.LEGAL.RETURN_SUPPORT_HOURS}. Requests may still be emailed
        outside those hours and will be reviewed during support hours.
      </p>
    </section>

    <section className="space-y-2">
      <h2 className="font-black">Refund timing</h2>
      <p className="text-sm text-neutral-600">
        Once a return or cancellation is approved, StyleDash initiates the
        refund within {CONFIG.LEGAL.REFUND_TIMELINE_DAYS} calendar days. Online
        payments are refunded to the original supported payment method. Approved
        Cash on Delivery refunds are issued by UPI after the customer supplies a
        valid UPI ID. Your bank or payment provider may take additional time to
        display the credit after StyleDash initiates it.
      </p>
    </section>

    <section className="space-y-2">
      <h2 className="font-black">Cancellation</h2>
      <p className="text-sm text-neutral-600">
        An order may be cancelled while it has not yet been packed. Once the
        order is packed or dispatched, cancellation is not available; the
        applicable return/exchange process must be used instead.
      </p>
    </section>

    <section className="rounded-xl bg-neutral-100 p-4 text-sm text-neutral-700">
      <h2 className="font-black text-neutral-900 mb-1">How to request help</h2>
      <p>
        Contact{' '}
        <a
          className="underline font-bold"
          href={`mailto:${CONFIG.LEGAL.SUPPORT_EMAIL}`}
        >
          {CONFIG.LEGAL.SUPPORT_EMAIL}
        </a>{' '}
        or {CONFIG.LEGAL.SUPPORT_PHONE} with your order reference and the
        requested action. You can also review general support information on the{' '}
        <Link className="underline font-bold" to="/help">
          Help page
        </Link>
        .
      </p>
    </section>

    <p className="text-xs text-neutral-500">
      Current policy effective date: {CONFIG.LEGAL.POLICY_EFFECTIVE_DATE}.
    </p>
  </div>
);
