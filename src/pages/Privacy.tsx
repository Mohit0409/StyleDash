import React from 'react';
import { SEO } from '../components/SEO';
import { CONFIG } from '../config';

export const Privacy = () => (
  <div className="max-w-3xl mx-auto p-8 space-y-6">
    <SEO title="Privacy - StyleDash" />
    <h1 className="text-3xl font-black">Privacy notice</h1>

    <p className="text-sm text-neutral-600">
      StyleDash is currently operated by {CONFIG.LEGAL.PROPRIETOR_NAME}. This
      notice explains the information used to operate customer accounts, orders,
      payments, support, and local fulfillment.
    </p>

    <section className="space-y-2">
      <h2 className="font-black">Information we handle</h2>
      <p className="text-sm text-neutral-600">
        Depending on how you use StyleDash, we may handle account identifiers,
        name, email, phone number, delivery address, order and cart information,
        support messages, vendor-application information, device/session
        security data, and payment/order references.
      </p>
    </section>

    <section className="space-y-2">
      <h2 className="font-black">How information is used</h2>
      <p className="text-sm text-neutral-600">
        Information is used to provide account access, validate serviceability
        and stock, process and fulfill orders, provide customer support, prevent
        fraud and abuse, secure the service, reconcile payments, maintain
        business records, and handle disputes or legal obligations.
      </p>
    </section>

    <section className="space-y-2">
      <h2 className="font-black">Payments</h2>
      <p className="text-sm text-neutral-600">
        Online payment entry is handled through Razorpay. StyleDash stores
        payment and order identifiers and verification state needed for order
        reconciliation, but support staff must never ask you to provide a card
        CVV or UPI PIN.
      </p>
    </section>

    <section className="space-y-2">
      <h2 className="font-black">Service providers and access</h2>
      <p className="text-sm text-neutral-600">
        Information may be shared only as reasonably needed with payment,
        hosting, communications, support, store, and delivery providers involved
        in operating your order or the service. Customer-facing access is scoped
        to the signed-in account, while authorized administration may access
        information required for fulfillment, support, security, and
        reconciliation.
      </p>
    </section>

    <section className="space-y-2">
      <h2 className="font-black">Retention</h2>
      <p className="text-sm text-neutral-600">
        We retain information only for as long as reasonably needed for active
        accounts and orders, payment reconciliation, fraud/security controls,
        support and disputes, backups, and applicable accounting, tax, or legal
        obligations. Information that is no longer required is deleted or
        anonymized where reasonably practicable.
      </p>
    </section>

    <section className="space-y-2">
      <h2 className="font-black">Access, correction, and deletion requests</h2>
      <p className="text-sm text-neutral-600">
        To request access to, correction of, or deletion of account information,
        email{' '}
        <a
          className="underline font-bold"
          href={`mailto:${CONFIG.LEGAL.SUPPORT_EMAIL}`}
        >
          {CONFIG.LEGAL.SUPPORT_EMAIL}
        </a>{' '}
        from the email associated with your account. We may need to verify the
        request. Deleting an account does not require us to erase transaction,
        payment, fraud-prevention, or other records that must still be retained
        for legitimate business or legal reasons.
      </p>
    </section>

    <section className="space-y-2">
      <h2 className="font-black">Security</h2>
      <p className="text-sm text-neutral-600">
        StyleDash uses account authentication, protected sessions, access
        controls, private administration, backups, and other technical and
        operational safeguards. No internet-connected system can guarantee
        absolute security.
      </p>
    </section>

    <section className="rounded-xl bg-neutral-100 p-4 text-sm text-neutral-700 space-y-1">
      <h2 className="font-black text-neutral-900">Privacy and grievance contact</h2>
      <p>Operator: {CONFIG.LEGAL.PROPRIETOR_NAME}</p>
      <p>Grievance officer: {CONFIG.LEGAL.GRIEVANCE_OFFICER}</p>
      <p>
        Email: {CONFIG.LEGAL.SUPPORT_EMAIL} | Phone: {CONFIG.LEGAL.SUPPORT_PHONE}
      </p>
      <p>Address: {CONFIG.LEGAL.ADDRESS}</p>
    </section>

    <p className="text-xs text-neutral-500">
      Current policy effective date: {CONFIG.LEGAL.POLICY_EFFECTIVE_DATE}.
    </p>
  </div>
);
