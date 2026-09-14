import React from 'react';
import { Link } from 'react-router-dom';
import { SEO } from '../components/SEO';
import { CONFIG } from '../config';

export const Returns = () => (
  <div className="max-w-3xl mx-auto p-8 space-y-6">
    <SEO title="Returns & Exchanges - Vibe4You" />
    <h1 className="text-3xl font-black">Returns and exchanges</h1>

    <p className="text-sm text-neutral-600">
      This policy applies to orders placed through Vibe4You in the current
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
        Exchanges depend on replacement-stock availability and are offered only
        when the product listing states that size exchange is available. An
        eligible size exchange costs INR {CONFIG.LEGAL.EXCHANGE_PICKUP_FEE}.
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
        A customer-choice return pickup may carry an INR{' '}
        {CONFIG.LEGAL.RETURN_PICKUP_FEE} pickup charge. A size exchange may
        carry an INR {CONFIG.LEGAL.EXCHANGE_PICKUP_FEE} pickup/exchange charge.
        These charges are waived when Vibe4You confirms that the item was
        wrong, damaged, defective, or not as ordered.
      </p>
      <p className="text-sm text-neutral-600">
        The dedicated return and size-exchange desk is handled during{' '}
        {CONFIG.LEGAL.RETURN_SUPPORT_HOURS}. General customer support remains
        available during {CONFIG.LEGAL.SUPPORT_HOURS}. Requests may still be emailed
        outside those hours and will be reviewed during support hours.
      </p>
    </section>

    <section className="space-y-2">
      <h2 className="font-black">Refund timing</h2>
      <p className="text-sm text-neutral-600">
        Once a return or cancellation is approved, Vibe4You initiates the
        refund within {CONFIG.LEGAL.REFUND_TIMELINE_DAYS} calendar days. Online
        payments are refunded to the original supported payment method. Approved
        Cash on Delivery refunds are issued by UPI after the customer supplies a
        valid UPI ID. Your bank or payment provider may take additional time to
        display the credit after Vibe4You initiates it.
      </p>
    </section>

    <section className="space-y-2">
      <h2 className="font-black">Cancellation</h2>
      <p className="text-sm text-neutral-600">
        A customer may submit a cancellation request before delivery. If the
        order is already out for delivery, the cancellation costs INR 50. Any
        required fee collection and online refund must be reconciled before the
        order is finally marked cancelled.
      </p>
    </section>

    <section className="space-y-2">
      <h2 className="font-black">Try at Home</h2>
      <p className="text-sm text-neutral-600">
        Products marked Try at Home allow two selected sizes for an INR 50
        service fee. The customer must choose one size within 15 minutes after
        delivery and return the other in its original condition. An additional
        INR 50 late fee applies after the 15-minute window.
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
