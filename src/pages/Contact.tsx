import React from 'react';
import { SEO } from '../components/SEO';
import { CONFIG } from '../config';

const supportPhoneHref = CONFIG.LEGAL.SUPPORT_PHONE.replace(/\s+/g, '');

export const Contact = () => (
  <div className="max-w-3xl mx-auto p-8 space-y-6">
    <SEO title="Contact Us - Vibe4You" />
    <h1 className="text-3xl font-black">Contact us</h1>

    <p className="text-sm text-neutral-600">
      For order, payment, return, delivery, account, or grievance support,
      contact Vibe4You using the details below.
    </p>

    <section className="rounded-xl bg-neutral-100 p-4 text-sm text-neutral-700 space-y-2">
      <p><strong>Operator:</strong> {CONFIG.LEGAL.PROPRIETOR_NAME}</p>
      <p><strong>Grievance officer:</strong> {CONFIG.LEGAL.GRIEVANCE_OFFICER}</p>
      <p>
        <strong>Email:</strong>{' '}
        <a className="underline font-bold" href={`mailto:${CONFIG.LEGAL.SUPPORT_EMAIL}`}>
          {CONFIG.LEGAL.SUPPORT_EMAIL}
        </a>
      </p>
      <p>
        <strong>Phone:</strong>{' '}
        <a className="underline font-bold" href={`tel:${supportPhoneHref}`}>
          {CONFIG.LEGAL.SUPPORT_PHONE}
        </a>
      </p>
      <p><strong>Address:</strong> {CONFIG.LEGAL.ADDRESS}</p>
      <p><strong>Support hours:</strong> {CONFIG.LEGAL.SUPPORT_HOURS}</p>
    </section>

    <section className="space-y-2">
      <h2 className="font-black">When contacting us</h2>
      <p className="text-sm text-neutral-600">
        Include your Vibe4You order reference when your question is about an
        order, payment, refund, return, or delivery. Never send a card CVV, UPI
        PIN, password, OTP, or other authentication secret to support.
      </p>
    </section>

    <p className="text-xs text-neutral-500">
      Current policy effective date: {CONFIG.LEGAL.POLICY_EFFECTIVE_DATE}.
    </p>
  </div>
);
