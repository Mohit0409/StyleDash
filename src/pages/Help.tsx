import React from 'react';
import { Link } from 'react-router-dom';
import { SEO } from '../components/SEO';
import { CONFIG } from '../config';

const supportPhoneHref = CONFIG.LEGAL.SUPPORT_PHONE.replace(/\s+/g, '');

export const Help = () => (
  <div className="max-w-3xl mx-auto p-8 space-y-6">
    <SEO title="Help & Support - StyleDash" />
    <h1 className="text-3xl font-black">Help and customer support</h1>

    <section className="space-y-2">
      <h2 className="font-black">Contact StyleDash</h2>
      <p className="text-sm text-neutral-600">
        Email:{' '}
        <a
          className="underline font-bold"
          href={`mailto:${CONFIG.LEGAL.SUPPORT_EMAIL}`}
        >
          {CONFIG.LEGAL.SUPPORT_EMAIL}
        </a>
      </p>
      <p className="text-sm text-neutral-600">
        Phone:{' '}
        <a
          className="underline font-bold"
          href={`tel:${supportPhoneHref}`}
        >
          {CONFIG.LEGAL.SUPPORT_PHONE}
        </a>
      </p>
      <p className="text-sm text-neutral-600">
        Support hours: {CONFIG.LEGAL.SUPPORT_HOURS}
      </p>
      <p className="text-sm text-neutral-600">
        Business address: {CONFIG.LEGAL.ADDRESS}
      </p>
    </section>

    <section className="space-y-2">
      <h2 className="font-black">Order help</h2>
      <p className="text-sm text-neutral-600">
        Sign in and open{' '}
        <Link className="underline font-bold" to="/orders">
          Your Orders
        </Link>{' '}
        to find the order reference, payment state, items, and delivery status.
        Keep the order reference when contacting support.
      </p>
    </section>

    <section className="space-y-2">
      <h2 className="font-black">Returns, exchanges, and cancellations</h2>
      <p className="text-sm text-neutral-600">
        See the{' '}
        <Link className="underline font-bold" to="/returns">
          Returns &amp; Exchanges policy
        </Link>{' '}
        for the current exchange window, issue-reporting period, pickup charges,
        cancellation cutoff, and refund timing.
      </p>
    </section>

    <section className="space-y-2">
      <h2 className="font-black">Delivery area and timing</h2>
      <p className="text-sm text-neutral-600">
        StyleDash validates delivery addresses against the server-configured
        service area during checkout. Delivery estimates are targets and may
        vary with store acceptance, stock, traffic, weather, address accuracy,
        and rider availability.
      </p>
    </section>

    <section className="space-y-2">
      <h2 className="font-black">Payments</h2>
      <p className="text-sm text-neutral-600">
        Online payments open Razorpay checkout. StyleDash does not ask you to
        share a card CVV or UPI PIN with support staff. If checkout is cancelled
        or fails, check Your Orders before trying again.
      </p>
    </section>

    <section className="rounded-xl bg-neutral-100 p-4 text-sm text-neutral-700 space-y-1">
      <h2 className="font-black text-neutral-900">Grievance contact</h2>
      <p>Grievance officer: {CONFIG.LEGAL.GRIEVANCE_OFFICER}</p>
      <p>
        Contact: {CONFIG.LEGAL.SUPPORT_EMAIL} / {CONFIG.LEGAL.SUPPORT_PHONE}
      </p>
      <p>
        When raising a grievance, include your order reference and a concise
        description of the issue so it can be investigated.
      </p>
    </section>

    <p className="text-xs text-neutral-500">
      Current policy effective date: {CONFIG.LEGAL.POLICY_EFFECTIVE_DATE}.
    </p>
  </div>
);
