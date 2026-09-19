import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Package, Store } from 'lucide-react';
import { SEO } from '../components/SEO';
import { orderApi } from '../services/businessApi';
import { ServerOrder } from '../services/paymentApi';

const statusLabel = (value: string) => value.split('_').join(' ');
const statusClass = (value: string) => value === 'cancelled'
  ? 'bg-red-100 text-red-700 dark:bg-red-950/40 dark:text-red-300'
  : value === 'delivered'
    ? 'bg-green-100 text-green-700 dark:bg-green-950/40 dark:text-green-300'
    : 'bg-lime-100 text-lime-800 dark:bg-lime-950/40 dark:text-lime-300';

const EARLY_CANCEL_STATUSES = new Set(['payment_review_required', 'placed', 'confirmed']);
const CANCELLATION_STATUSES = new Set(['payment_pending', 'payment_review_required', 'placed', 'confirmed', 'preparing', 'packed', 'out_for_delivery']);
const isOnlinePayment = (order: ServerOrder) => order.paymentMethod === 'upi' || order.paymentMethod === 'card';
const cancellationButtonLabel = (order: ServerOrder) => {
  if (EARLY_CANCEL_STATUSES.has(order.status)) return isOnlinePayment(order) ? 'Cancel & get refund' : 'Cancel order';
  return order.status === 'out_for_delivery' ? 'Request cancellation (₹50)' : 'Request cancellation';
};
const cancellationStatusText = (order: ServerOrder) => {
  const request = order.cancellationRequest;
  if (!request) return '';
  if (request.refundStatus === 'processed') return 'Order cancelled. Your full refund has been confirmed to the original payment method.';
  if (request.refundStatus === 'failed') return 'Order cancelled, but the refund needs attention. Please contact Vibe4You support.';
  if (request.refundStatus === 'initiated') return 'Order cancelled. Your full refund has been initiated to the original payment method and is awaiting payment-provider confirmation.';
  if (request.status === 'completed') return 'Order cancelled. No payment refund was required.';
  return request.feeDue > 0
    ? `Cancellation requested. ₹${request.feeDue} fee ${request.feePaid ? 'paid' : 'due'}.`
    : 'Cancellation requested. No cancellation fee applies.';
};

export const Orders: React.FC = () => {
  const [orders, setOrders] = useState<ServerOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [busyOrderId, setBusyOrderId] = useState('');
  const [exchangeChoice, setExchangeChoice] = useState<Record<string, string>>({});

  useEffect(() => {
    orderApi.mine().then(setOrders).catch((cause) => setError(cause instanceof Error ? cause.message : 'Orders could not be loaded.')).finally(() => setLoading(false));
  }, []);

  const replaceOrder = (updated: ServerOrder) => setOrders(current => current.map(order => order.id === updated.id ? updated : order));
  const requestCancellation = async (order: ServerOrder) => {
    const early = EARLY_CANCEL_STATUSES.has(order.status);
    const confirmation = early
      ? isOnlinePayment(order)
        ? 'Cancel this order now and initiate a full refund to your original payment method?'
        : 'Cancel this Cash on Delivery order now?'
      : order.status === 'out_for_delivery'
        ? 'Submit this cancellation request? A ₹50 fee applies because the order is already out for delivery.'
        : 'Submit this cancellation request?';
    if (!window.confirm(confirmation)) return;
    setBusyOrderId(order.id); setError('');
    try { replaceOrder(await orderApi.requestCancellation(order.id)); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Cancellation could not be requested.'); }
    finally { setBusyOrderId(''); }
  };
  const requestExchange = async (orderId: string, itemIndex: number) => {
    const key = `${orderId}:${itemIndex}`;
    const targetVariantId = exchangeChoice[key];
    if (!targetVariantId) { setError('Choose the replacement size first.'); return; }
    setBusyOrderId(orderId); setError('');
    try { replaceOrder(await orderApi.requestExchange(orderId, itemIndex, targetVariantId)); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Exchange could not be requested.'); }
    finally { setBusyOrderId(''); }
  };

  return (
    <div className="max-w-5xl mx-auto px-4 py-8 space-y-8">
      <SEO title="Order History - Vibe4You" noIndex />
      <div><h1 className="text-3xl font-black">Your Orders</h1><p className="text-sm text-neutral-500 mt-1">Track each order, see its store and product details, and download the receipt after delivery.</p></div>
      {loading ? <div className="text-center py-12">Loading orders…</div>
        : error ? <p role="alert" className="text-red-600">{error}</p>
          : orders.length === 0 ? <div className="p-12 text-center bg-white dark:bg-neutral-900 rounded-3xl border dark:border-neutral-800 space-y-4"><Package className="w-12 h-10 mx-auto"/><h3 className="font-bold">No orders placed yet</h3><Link to="/products" className="font-bold text-lime-600">Start shopping</Link></div>
            : <div className="space-y-5">{orders.map(order => <article key={order.id} className="p-5 md:p-6 bg-white dark:bg-neutral-900 rounded-3xl border dark:border-neutral-800 space-y-5">
              {order.isPaymentTestOrder && <div className="rounded-xl border-2 border-red-700 bg-red-50 dark:bg-red-950/30 p-3 text-sm font-black text-red-800 dark:text-red-300">TEST — NO FULFILLMENT REQUIRED</div>}
              {order.status === 'payment_review_required' && <div role="status" className="rounded-xl border border-amber-500 bg-amber-50 dark:bg-amber-950/30 p-3 text-sm font-bold text-amber-900 dark:text-amber-200">Payment received. Stock confirmation is required. Do not pay again.</div>}
              <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
                <div><strong className="text-lg">Order {order.id}</strong><small className="block text-neutral-500 mt-1">{new Date(order.createdAt).toLocaleString()}</small></div>
                <div className="sm:text-right"><span className={`inline-flex rounded-full px-3 py-1 text-xs font-black uppercase ${statusClass(order.status)}`}>{statusLabel(order.status)}</span><strong className="block mt-2">₹{order.grandTotal}</strong></div>
              </div>
              <div className="divide-y divide-neutral-200 dark:divide-neutral-800">{order.items.map((item, itemIndex) => <div key={`${item.variantId}:${itemIndex}`} className="py-3 first:pt-0 last:pb-0 flex flex-wrap items-center gap-3">
                <div className="w-14 h-14 rounded-xl bg-neutral-100 dark:bg-neutral-800 overflow-hidden shrink-0">{item.imageUrl ? <img src={item.imageUrl} alt="" className="w-full h-full object-contain object-center p-1" /> : <div className="w-full h-full grid place-items-center"><Package className="w-5 h-5 text-neutral-400" /></div>}</div>
                <div className="min-w-0 flex-1"><div className="flex items-center gap-1 text-xs font-bold text-neutral-500"><Store className="w-3.5 h-3.5" />{item.storeName || 'Vibe4You'}</div><p className="font-bold truncate">{item.productName}</p><p className="text-sm text-neutral-500">Size {item.size || '—'} · Color {item.colourName || '—'} · Qty {item.quantity}</p></div>
                <strong className="shrink-0">₹{item.lineTotal}</strong>
                {item.exchangeEligible && order.status === 'delivered' && !order.exchangeRequests?.some(request => request.itemIndex === itemIndex && ['requested', 'approved', 'completed'].includes(request.status)) && <div className="basis-full rounded-xl bg-sky-50 p-3 dark:bg-sky-950/20"><p className="mb-2 text-xs font-bold text-sky-800 dark:text-sky-200">Exchange this item for another available size (₹50)</p><div className="flex flex-wrap gap-2"><select aria-label={`Replacement size for ${item.productName}`} value={exchangeChoice[`${order.id}:${itemIndex}`] || ''} onChange={event => setExchangeChoice(current => ({ ...current, [`${order.id}:${itemIndex}`]: event.target.value }))} className="rounded-lg border bg-white px-3 py-2 text-sm dark:bg-neutral-900"><option value="">Choose size</option>{(item.exchangeOptions || []).map(option => <option key={option.variantId} value={option.variantId}>{option.size}</option>)}</select><button type="button" disabled={busyOrderId === order.id || !(item.exchangeOptions || []).length} onClick={() => void requestExchange(order.id, itemIndex)} className="rounded-lg bg-sky-700 px-3 py-2 text-xs font-black text-white disabled:opacity-50">Request exchange</button></div></div>}
              </div>)}</div>
              {order.cancellationRequest && <div role="status" className="rounded-xl border border-amber-300 bg-amber-50 p-3 text-sm font-bold text-amber-900 dark:border-amber-800 dark:bg-amber-950/20 dark:text-amber-200">{cancellationStatusText(order)}</div>}
              {(order.exchangeRequests || []).map(request => <div key={request.id} role="status" className="rounded-xl border border-sky-200 bg-sky-50 p-3 text-sm dark:border-sky-900 dark:bg-sky-950/20"><strong>Exchange {statusLabel(request.status)}:</strong> {request.sourceSize} to {request.targetSize} · ₹{request.feeDue} fee {request.feePaid ? 'paid' : 'due'}</div>)}
              {order.status === 'cancelled' && order.cancellationReason && <div className="rounded-xl border border-red-200 bg-red-50 dark:border-red-900 dark:bg-red-950/20 p-3 text-sm"><strong>Cancellation reason:</strong> {order.cancellationReason}</div>}
              <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
                <p className="text-sm text-neutral-500">Deliver to <strong className="text-neutral-800 dark:text-neutral-200">{order.address.name}</strong> · {order.address.phone}</p>
                <div className="flex flex-wrap gap-2">{!order.cancellationRequest && CANCELLATION_STATUSES.has(order.status) && <button type="button" disabled={busyOrderId === order.id} onClick={() => void requestCancellation(order)} className="rounded-xl border border-red-300 px-4 py-2.5 text-sm font-black text-red-700 disabled:opacity-50">{cancellationButtonLabel(order)}</button>}<Link to={`/orders/${encodeURIComponent(order.id)}/track`} className="px-4 py-2.5 rounded-xl bg-neutral-950 text-white dark:bg-lime-400 dark:text-neutral-950 font-black">Track order</Link></div>
              </div>
            </article>)}</div>}
    </div>
  );
};
