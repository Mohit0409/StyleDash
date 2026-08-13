import React from 'react';
import { Link } from 'react-router-dom';
import { SEO } from '../components/SEO';

export const Help = () => <div className="max-w-3xl mx-auto p-8 space-y-6">
  <SEO title="Help & Support - StyleDash" />
  <h1 className="text-3xl font-black">Help and customer support</h1>
  <section><h2 className="font-black">Order help</h2><p className="text-sm text-neutral-600">Sign in and open <Link className="underline font-bold" to="/orders">Your Orders</Link> to find the order reference, payment state, items, and delivery status. Keep the order reference when contacting StyleDash support.</p></section>
  <section><h2 className="font-black">Delivery area and timing</h2><p className="text-sm text-neutral-600">StyleDash currently validates delivery addresses in supported Neemuch pincodes during checkout. Express timing is an estimate and can vary with store acceptance, stock, traffic, weather, and rider availability.</p></section>
  <section><h2 className="font-black">Payments</h2><p className="text-sm text-neutral-600">Online payments open Razorpay’s checkout. StyleDash does not collect card numbers, CVV, or UPI PIN. If checkout is cancelled or fails, your cart remains available; check Your Orders before trying again.</p></section>
  <p className="rounded-xl bg-amber-50 text-amber-900 p-4 text-sm"><strong>Support contact pending:</strong> the business must publish its verified phone/email or in-app contact channel before accepting live customer orders.</p>
</div>;
