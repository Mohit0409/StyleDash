import React, { useEffect, useState } from 'react';
import { AlertTriangle, CreditCard, ShieldCheck } from 'lucide-react';
import { SEO } from '../components/SEO';
import { useAuth } from '../context/AuthContext';
import { ApiError } from '../services/apiClient';
import {
  openRazorpayCheckout,
  PaymentApiError,
  verifyPayment,
} from '../services/paymentApi';
import {
  createPaymentTestOrder,
  getPaymentTestProduct,
  PaymentTestProduct as PaymentTestProductDetails,
} from '../services/paymentTestApi';
import { NotFound } from './NotFound';

const makeIdempotencyKey = () =>
  `payment-test-${Date.now()}-${globalThis.crypto?.randomUUID?.() || Math.random().toString(36).slice(2)}`;

export const PaymentTestProduct: React.FC = () => {
  const { user, loading: authLoading } = useAuth();
  const [product, setProduct] = useState<PaymentTestProductDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [unavailable, setUnavailable] = useState(false);
  const [paymentMethod, setPaymentMethod] = useState<'upi' | 'card'>('upi');
  const [processing, setProcessing] = useState(false);
  const [message, setMessage] = useState('');
  const [completedOrderId, setCompletedOrderId] = useState('');

  useEffect(() => {
    getPaymentTestProduct()
      .then(setProduct)
      .catch(() => setUnavailable(true))
      .finally(() => setLoading(false));
  }, []);

  if (loading || authLoading) {
    return <div className="min-h-[50vh] flex items-center justify-center text-sm font-bold">Checking controlled accessâ€¦</div>;
  }
  if (unavailable || !product || !user) return <NotFound />;

  const startValidation = async () => {
    setProcessing(true);
    setMessage('');
    try {
      const created = await createPaymentTestOrder(paymentMethod, makeIdempotencyKey());
      const callback = await openRazorpayCheckout(
        created,
        { name: user.name, email: user.email, phone: user.phone || '' },
        paymentMethod,
      );
      const verified = await verifyPayment(callback, created.styleDashOrderId);
      if (verified.pending) {
        setMessage('Payment is authorized but not captured. No fulfillment will occur; wait for captured-state verification.');
        return;
      }
      setCompletedOrderId(verified.order.id);
      setMessage('Captured payment verified. This validation record requires no fulfillment.');
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 404) {
        setUnavailable(true);
        return;
      }
      const error = cause instanceof PaymentApiError || cause instanceof ApiError
        ? cause
        : new Error('Payment validation could not be completed.');
      setMessage(error.message);
    } finally {
      setProcessing(false);
    }
  };

  return (
    <div className="max-w-xl mx-auto px-4 py-10 space-y-6">
      <SEO title="Controlled payment validation - Vibe4You" description="Restricted Vibe4You payment validation." />
      <div className="rounded-3xl border-2 border-red-700 bg-red-50 dark:bg-red-950/30 p-6 space-y-3">
        <div className="flex items-center gap-2 text-red-800 dark:text-red-300">
          <AlertTriangle className="w-6 h-6" />
          <strong className="text-lg">TEST â€” NO FULFILLMENT REQUIRED</strong>
        </div>
        <p className="text-sm text-red-800 dark:text-red-200">
          This owner-controlled item validates Razorpay payment processing only. It is not clothing and will never be packed, dispatched, or delivered.
        </p>
      </div>

      <section className="rounded-3xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 p-6 space-y-5 shadow-sm">
        <div>
          <p className="text-xs font-black uppercase tracking-widest text-neutral-500">Restricted validation item</p>
          <h1 className="text-2xl font-black text-neutral-950 dark:text-white">{product.name}</h1>
          <p className="mt-2 text-4xl font-black text-lime-600">â‚¹{product.price}</p>
        </div>

        <div className="space-y-3">
          <p className="text-xs font-bold text-neutral-700 dark:text-neutral-300">Choose a Razorpay method</p>
          {(['upi', 'card'] as const).map(method => (
            <label key={method} className="flex items-center gap-3 rounded-xl border border-neutral-200 dark:border-neutral-700 p-3 text-sm font-bold">
              <input type="radio" name="payment-test-method" checked={paymentMethod === method} onChange={() => setPaymentMethod(method)} />
              {method === 'upi' ? 'UPI with Razorpay' : 'Card with Razorpay'}
            </label>
          ))}
        </div>

        <p className="flex gap-2 text-xs text-neutral-500">
          <ShieldCheck className="w-4 h-4 shrink-0" />
          The Vibe4You server fixes the total at â‚¹10 and treats the result as paid only after captured-state verification.
        </p>

        {message && <p role="status" className="rounded-xl bg-neutral-100 dark:bg-neutral-800 p-3 text-sm font-semibold">{message}</p>}
        {completedOrderId && <p className="text-xs text-neutral-500">Validation reference: <strong>{completedOrderId}</strong></p>}

        {!completedOrderId && (
          <button
            type="button"
            onClick={startValidation}
            disabled={processing}
            className="w-full flex items-center justify-center gap-2 rounded-xl bg-neutral-950 dark:bg-lime-400 px-5 py-4 text-sm font-black text-white dark:text-neutral-950 disabled:opacity-60"
          >
            <CreditCard className="w-4 h-4" />
            {processing ? 'Opening secure checkoutâ€¦' : 'Pay â‚¹10 with Razorpay'}
          </button>
        )}
      </section>
    </div>
  );
};
