import React, { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Clock3, PackageCheck, RefreshCw, ShieldCheck, Truck, XCircle } from 'lucide-react';
import { SEO } from '../components/SEO';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import {
  deliveryRequestApi,
  type OutsideDeliveryRequest,
} from '../services/deliveryRequestApi';
import {
  openRazorpayCheckout,
  PaymentApiError,
  verifyPayment,
} from '../services/paymentApi';
import { ApiError } from '../services/apiClient';

const makeIdempotencyKey = (requestId: string) =>
  `outside-${requestId}-${Date.now()}-${globalThis.crypto?.randomUUID?.() || Math.random().toString(36).slice(2)}`;

const statusCopy: Record<string, string> = {
  requested: 'Request received. Vibe4You is checking the courier/delivery charge.',
  quoted: 'Delivery charge confirmed. Your secure payment request is ready.',
  payment_pending: 'Payment request created. You can safely retry payment if you closed Razorpay.',
  paid: 'Payment received. This request is now a normal tracked Vibe4You order.',
  cancelled: 'You cancelled this delivery request.',
  rejected: 'Vibe4You could not arrange this outside-Neemuch delivery.',
};
export const OutsideDeliveryRequests: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { showToast } = useToast();
  const [requests, setRequests] = useState<OutsideDeliveryRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState('');
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setError('');
    try {
      setRequests(await deliveryRequestApi.list());
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'Delivery requests could not be loaded.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const cancel = async (request: OutsideDeliveryRequest) => {
    setBusyId(request.id); setError('');
    try {
      const updated = await deliveryRequestApi.cancel(request.id);
      setRequests(current => current.map(item => item.id === updated.id ? updated : item));
      showToast('Delivery request cancelled.', 'success');
    } catch (cause) {
      const message = cause instanceof ApiError ? cause.message : 'Delivery request could not be cancelled.';
      setError(message); showToast(message, 'error');
    } finally { setBusyId(''); }
  };
  const pay = async (request: OutsideDeliveryRequest, method: 'upi' | 'card') => {
    if (!request.quote) return;
    setBusyId(request.id); setError('');
    try {
      const created = await deliveryRequestApi.createPaymentOrder(
        request.id,
        method,
        makeIdempotencyKey(request.id),
      );
      const payment = await openRazorpayCheckout(
        created,
        {
          name: request.address.name || user?.name || '',
          email: user?.email,
          phone: request.address.phone || user?.phone || '',
        },
        method,
      );
      const result = await verifyPayment(payment, created.styleDashOrderId);
      await load();
      if (result.pending) {
        showToast('Payment authorized and awaiting capture. Do not pay again.', 'info');
        return;
      }
      if (result.order.status === 'payment_review_required') {
        showToast('Payment received. Stock confirmation is required; do not pay again.', 'info');
        navigate('/orders');
        return;
      }
      showToast('Payment verified. Your outside-Neemuch order is placed!', 'success');
      navigate(`/order-success/${result.order.id}`);
    } catch (cause) {
      const message = cause instanceof PaymentApiError || cause instanceof ApiError
        ? cause.message
        : 'Payment could not be completed.';
      setError(message);
      showToast(message, cause instanceof PaymentApiError && cause.code === 'payment_cancelled' ? 'info' : 'error');
    } finally { setBusyId(''); }
  };

  const activeCount = requests.filter(item => ['requested', 'quoted', 'payment_pending'].includes(item.status)).length;
  return (
    <div className="mx-auto max-w-4xl space-y-6 px-4 py-8 sm:px-6">
      <SEO title="Delivery Requests - Vibe4You" noIndex />
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-black uppercase tracking-widest text-violet-600">Outside Neemuch</p>
          <h1 className="text-3xl font-black">Delivery Requests</h1>
          <p className="mt-1 text-sm text-neutral-500">
            For eligible products outside 458441, Vibe4You confirms the delivery charge before you pay.
          </p>
        </div>
        <button type="button" onClick={() => void load()} disabled={loading} className="inline-flex items-center gap-2 rounded-xl border px-4 py-2 text-xs font-bold disabled:opacity-60">
          <RefreshCw className="h-4 w-4" /> Refresh
        </button>
      </div>

      <div className="rounded-2xl border border-violet-200 bg-violet-50 p-4 text-xs text-violet-950 dark:border-violet-900 dark:bg-violet-950/20 dark:text-violet-100">
        <div className="flex items-center gap-2 font-black"><ShieldCheck className="h-4 w-4" /> No delivery amount is taken before your quote.</div>
        <p className="mt-1">The product price and delivery charge are calculated and stored on the server. Payment is accepted only after Vibe4You approves the delivery quote.</p>
      </div>

      {error && <p role="alert" className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}
      {loading ? <p className="text-sm text-neutral-500">Loading delivery requests…</p> : requests.length === 0 ? (
        <div className="rounded-3xl border p-8 text-center dark:border-neutral-800">
          <Truck className="mx-auto h-9 w-9 text-neutral-400" />
          <h2 className="mt-3 text-lg font-black">No outside delivery requests yet</h2>
          <p className="mt-1 text-sm text-neutral-500">Open an eligible product and choose “Request Delivery Outside Neemuch”.</p>
          <Link to="/products" className="mt-4 inline-block rounded-xl bg-neutral-950 px-5 py-2.5 text-xs font-bold text-white dark:bg-lime-400 dark:text-neutral-950">Browse products</Link>
        </div>
      ) : (
        <>
          <p className="text-xs font-bold text-neutral-500">{activeCount} active request{activeCount === 1 ? '' : 's'}</p>
          <div className="space-y-4">
            {requests.map(request => {
              const quote = request.quote;
              const canPay = (request.status === 'quoted' || request.status === 'payment_pending') && quote;
              const canCancel = request.status === 'requested' || request.status === 'quoted';
              return (
                <article key={request.id} className="rounded-3xl border bg-white p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <p className="text-[11px] font-black uppercase tracking-wider text-neutral-400">{request.id}</p>
                      <h2 className="text-lg font-black">{request.productName}</h2>
                      <p className="text-xs text-neutral-500">{request.storeName || 'Vibe4You store'} · {request.size}{request.colourName ? ` · ${request.colourName}` : ''} · Qty {request.quantity}</p>
                    </div>
                    <span className="w-fit rounded-full bg-neutral-100 px-3 py-1 text-[11px] font-black uppercase dark:bg-neutral-800">{request.status.replace(/_/g, ' ')}</span>
                  </div>

                  <p className="mt-3 flex items-start gap-2 text-xs text-neutral-600 dark:text-neutral-300">
                    <Clock3 className="mt-0.5 h-4 w-4 shrink-0" /> {statusCopy[request.status] || request.status}
                  </p>
                  <div className="mt-4 grid gap-3 rounded-2xl bg-neutral-50 p-4 text-xs sm:grid-cols-2 dark:bg-neutral-800/60">
                    <div><span className="text-neutral-500">Delivery to</span><strong className="mt-1 block">{request.address.street}, {request.address.city}, {request.address.state} {request.address.pincode}</strong></div>
                    <div><span className="text-neutral-500">Product subtotal</span><strong className="mt-1 block">₹{quote?.productSubtotal ?? request.productSubtotal}</strong></div>
                    {quote && <><div><span className="text-neutral-500">Delivery charge</span><strong className="mt-1 block">₹{quote.deliveryFee}</strong></div><div><span className="text-neutral-500">Total payment request</span><strong className="mt-1 block text-base">₹{quote.grandTotal}</strong></div></>}
                  </div>
                  {quote?.estimatedDelivery && <p className="mt-3 text-xs"><strong>Estimated delivery:</strong> {quote.estimatedDelivery}</p>}
                  {quote?.note && <p className="mt-2 rounded-xl border border-violet-200 bg-violet-50 p-3 text-xs dark:border-violet-900 dark:bg-violet-950/20"><strong>Vibe4You:</strong> {quote.note}</p>}
                  {request.rejectionReason && <p className="mt-3 flex gap-2 rounded-xl border border-red-200 bg-red-50 p-3 text-xs text-red-700"><XCircle className="h-4 w-4 shrink-0" /> {request.rejectionReason}</p>}
                  {request.status === 'paid' && request.orderId && <Link to={`/orders/${encodeURIComponent(request.orderId)}/track`} className="mt-4 inline-flex items-center gap-2 rounded-xl border px-4 py-2.5 text-xs font-bold"><PackageCheck className="h-4 w-4" /> Track order {request.orderId}</Link>}

                  {(canPay || canCancel) && <div className="mt-4 flex flex-wrap gap-2">
                    {canPay && <>
                      <button type="button" disabled={busyId === request.id} onClick={() => void pay(request, 'upi')} className="rounded-xl bg-neutral-950 px-4 py-2.5 text-xs font-black text-white disabled:opacity-60 dark:bg-lime-400 dark:text-neutral-950">Pay ₹{quote.grandTotal} with UPI</button>
                      <button type="button" disabled={busyId === request.id} onClick={() => void pay(request, 'card')} className="rounded-xl border px-4 py-2.5 text-xs font-black disabled:opacity-60">Pay by Card</button>
                    </>}
                    {canCancel && <button type="button" disabled={busyId === request.id} onClick={() => void cancel(request)} className="rounded-xl border border-red-200 px-4 py-2.5 text-xs font-bold text-red-600 disabled:opacity-60">Cancel request</button>}
                  </div>}
                </article>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
};
