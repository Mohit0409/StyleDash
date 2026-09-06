import React from 'react';
import { SEO } from '../components/SEO';
import { CONFIG } from '../config';

export const Shipping = () => (
  <div className="max-w-3xl mx-auto p-8 space-y-6">
    <SEO title="Shipping & Delivery - Vibe4You" />
    <h1 className="text-3xl font-black">Shipping and delivery</h1>

    <p className="text-sm text-neutral-600">
      Vibe4You provides hyperlocal delivery within its supported Neemuch service
      area. Your address, delivery option, fee, stock, and order total are
      validated by the server during checkout.
    </p>

    <section className="space-y-2">
      <h2 className="font-black">Service area</h2>
      <p className="text-sm text-neutral-600">
        Delivery is available only to supported pincodes shown as serviceable at
        checkout. A catalogue page or saved address does not override the
        checkout serviceability check.
      </p>
    </section>

    <section className="space-y-2">
      <h2 className="font-black">Local Delivery</h2>
      <p className="text-sm text-neutral-600">
        Standard Local Delivery targets delivery within a day. The current fee
        is INR {CONFIG.STANDARD_DELIVERY_FEE} for orders below INR{' '}
        {CONFIG.FREE_DELIVERY_THRESHOLD}; eligible orders at or above that
        threshold receive free delivery.
      </p>
    </section>

    <section className="space-y-2">
      <h2 className="font-black">Weekend Express Delivery</h2>
      <p className="text-sm text-neutral-600">
        When Express Delivery is offered for your cart on Saturday or Sunday,
        the target is about {CONFIG.EXPRESS_DELIVERY_MINUTES} minutes. The
        current Express fee is INR {CONFIG.EXPRESS_DELIVERY_FEE} for orders
        below the free-delivery threshold. Checkout is the final authority on
        whether Express is available for a particular order.
      </p>
    </section>

    <section className="space-y-2">
      <h2 className="font-black">Delays and order status</h2>
      <p className="text-sm text-neutral-600">
        Delivery times are estimates rather than guarantees and may change due
        to store acceptance, stock, traffic, weather, address accuracy, rider
        availability, or other events outside reasonable control.
      </p>
    </section>

    <section className="space-y-2">
      <h2 className="font-black">Delivery support</h2>
      <p className="text-sm text-neutral-600">
        For delivery questions, contact {CONFIG.LEGAL.SUPPORT_EMAIL} or{' '}
        {CONFIG.LEGAL.SUPPORT_PHONE} and include your order reference.
      </p>
    </section>

    <p className="text-xs text-neutral-500">
      Current policy effective date: {CONFIG.LEGAL.POLICY_EFFECTIVE_DATE}.
    </p>
  </div>
);
