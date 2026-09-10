import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { CheckCircle2, Clock3, Download, MapPin, Package, RefreshCw, Store, Truck, XCircle } from 'lucide-react';
import { SEO } from '../components/SEO';
import { orderApi } from '../services/businessApi';
import { ServerOrder } from '../services/paymentApi';

const STATUS_LABELS: Record<string, string> = {
  payment_pending: 'Payment pending',
  payment_review_required: 'Payment review required',
  placed: 'Order placed',
  confirmed: 'Order confirmed',
  preparing: 'Preparing your order',
  packed: 'Packed',
  out_for_delivery: 'Out for delivery',
  delivered: 'Delivered',
  cancelled: 'Cancelled',
};

const TRACKING_STEPS = ['placed', 'confirmed', 'preparing', 'packed', 'out_for_delivery', 'delivered'];
const money = (value: number) => `₹${Number(value || 0).toFixed(0)}`;
const dateTime = (value?: string) => value ? new Date(value).toLocaleString() : '—';
const label = (status: string) => STATUS_LABELS[status] || status.split('_').join(' ');

export const OrderTracking: React.FC = () => {
  const { orderId = '' } = useParams();
  const [order, setOrder] = useState<ServerOrder | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [receiptLoading, setReceiptLoading] = useState(false);
  const [error, setError] = useState('');
  const loadOrder = useCallback(async (quiet = false) => {
    if (!quiet) setLoading(true);
    else setRefreshing(true);
    setError('');
    try {
      setOrder(await orderApi.one(orderId));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'This order could not be loaded.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [orderId]);

  useEffect(() => { void loadOrder(); }, [loadOrder]);

  const progress = useMemo(() => {
    if (!order || order.status === 'cancelled') return 0;
    const index = TRACKING_STEPS.indexOf(order.status);
    if (index < 0) return 0;
    return Math.round(((index + 1) / TRACKING_STEPS.length) * 100);
  }, [order]);

  const downloadReceipt = async () => {
    if (!order) return;
    setReceiptLoading(true);
    setError('');
    try {
      const { blob, filename } = await orderApi.receipt(order.id);
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Receipt download failed.');
    } finally {
      setReceiptLoading(false);
    }
  };

  if (loading) return <div className="max-w-5xl mx-auto px-4 py-16 text-center font-bold">Loading order tracking…</div>;
  if (!order) return <div className="max-w-3xl mx-auto px-4 py-16 space-y-5 text-center"><SEO title="Track Order - Vibe4You" noIndex /><p role="alert" className="text-red-600">{error || 'Order not found.'}</p><Link to="/orders" className="font-bold underline">Back to your orders</Link></div>;

  const cancelled = order.status === 'cancelled';
  const delivered = order.status === 'delivered';

  return (
    <div className="max-w-5xl mx-auto px-4 py-8 md:py-12 space-y-6">
      <SEO title={`Track ${order.id} - Vibe4You`} noIndex />
      <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-neutral-500">Order tracking</p>
          <h1 className="text-2xl md:text-3xl font-black mt-1">{order.id}</h1>
          <p className="text-sm text-neutral-500 mt-1">Placed {dateTime(order.createdAt)}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={() => void loadOrder(true)} disabled={refreshing} className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl border border-neutral-300 dark:border-neutral-700 font-bold">
            <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} /> {refreshing ? 'Refreshing…' : 'Refresh status'}
          </button>
          {delivered && order.fulfillmentRequired !== false && <button type="button" onClick={() => void downloadReceipt()} disabled={receiptLoading} className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-neutral-950 text-white dark:bg-lime-400 dark:text-neutral-950 font-black"><Download className="w-4 h-4" />{receiptLoading ? 'Preparing…' : 'Download receipt'}</button>}
        </div>
      </div>
      {error && <p role="alert" className="rounded-xl border border-red-300 bg-red-50 dark:bg-red-950/30 p-3 text-sm font-bold text-red-700 dark:text-red-300">{error}</p>}

      <section className={`rounded-3xl border p-5 md:p-6 ${cancelled ? 'border-red-300 bg-red-50 dark:bg-red-950/20 dark:border-red-900' : 'border-neutral-200 bg-white dark:bg-neutral-900 dark:border-neutral-800'}`}>
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            {cancelled ? <XCircle className="w-7 h-7 text-red-600 shrink-0" /> : delivered ? <CheckCircle2 className="w-7 h-7 text-green-600 shrink-0" /> : <Truck className="w-7 h-7 text-lime-600 shrink-0" />}
            <div><h2 className="text-xl font-black capitalize">{label(order.status)}</h2><p className="text-sm text-neutral-500 mt-1">Estimated delivery: {order.estimatedDelivery}</p></div>
          </div>
          <span className="rounded-full border px-3 py-1 text-xs font-black uppercase tracking-wide">{order.paymentMethod} · {order.paymentStatus}</span>
        </div>
        {!cancelled && <div className="mt-6"><div className="h-2 rounded-full bg-neutral-200 dark:bg-neutral-800 overflow-hidden"><div className="h-full bg-lime-500 transition-all" style={{ width: `${progress}%` }} /></div><div className="mt-2 flex justify-between text-[11px] font-bold text-neutral-500"><span>Placed</span><span>Delivered</span></div></div>}
        {cancelled && <div className="mt-5 rounded-2xl border border-red-300 bg-white/70 dark:bg-neutral-950/40 p-4"><p className="text-xs font-black uppercase tracking-wide text-red-700 dark:text-red-300">Cancellation reason</p><p className="mt-1 font-semibold">{order.cancellationReason || 'No cancellation reason was recorded.'}</p>{order.cancelledAt && <p className="text-xs text-neutral-500 mt-2">Cancelled {dateTime(order.cancelledAt)}</p>}</div>}
      </section>

      <section className="rounded-3xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 p-5 md:p-6 space-y-4">
        <div className="flex items-center gap-2"><Package className="w-5 h-5" /><h2 className="text-lg font-black">Order items</h2></div>
        <div className="divide-y divide-neutral-200 dark:divide-neutral-800">
          {(order.items || []).map(item => <div key={item.variantId} className="py-4 first:pt-0 last:pb-0 flex gap-4">
            <div className="w-20 h-20 rounded-2xl bg-neutral-100 dark:bg-neutral-800 overflow-hidden shrink-0">{item.imageUrl ? <img src={item.imageUrl} alt="" className="w-full h-full object-cover" /> : <div className="w-full h-full grid place-items-center"><Package className="w-7 h-7 text-neutral-400" /></div>}</div>
            <div className="min-w-0 flex-1"><div className="flex items-center gap-1.5 text-xs font-bold text-neutral-500"><Store className="w-3.5 h-3.5" /><span>{item.storeName || 'Vibe4You'}</span></div><h3 className="font-black mt-1">{item.productName}</h3><p className="text-sm text-neutral-600 dark:text-neutral-400 mt-1">Size: <strong>{item.size || '—'}</strong> · Color: <strong>{item.colourName || '—'}</strong> · Qty: <strong>{item.quantity}</strong></p></div>
            <strong className="shrink-0">{money(item.lineTotal)}</strong>
          </div>)}
        </div>
      </section>

      <div className="grid md:grid-cols-2 gap-6">
        <section className="rounded-3xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 p-5 md:p-6">
          <div className="flex items-center gap-2"><MapPin className="w-5 h-5" /><h2 className="text-lg font-black">Delivery details</h2></div>
          <div className="mt-4 text-sm leading-6"><strong>{order.address.name}</strong><p>{order.address.phone}</p><p className="text-neutral-600 dark:text-neutral-400">{order.address.street}<br />{order.address.city}, {order.address.state} {order.address.pincode}</p></div>
        </section>
        <section className="rounded-3xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 p-5 md:p-6">
          <h2 className="text-lg font-black">Payment summary</h2>
          <dl className="mt-4 space-y-2 text-sm"><div className="flex justify-between"><dt>Subtotal</dt><dd>{money(order.subtotal)}</dd></div>{order.discount > 0 && <div className="flex justify-between text-green-700 dark:text-green-400"><dt>Discount</dt><dd>-{money(order.discount)}</dd></div>}<div className="flex justify-between"><dt>Delivery</dt><dd>{money(order.deliveryFee)}</dd></div><div className="flex justify-between"><dt>Taxes</dt><dd>{money(order.taxes)}</dd></div><div className="flex justify-between border-t border-neutral-200 dark:border-neutral-800 pt-3 mt-3 text-base font-black"><dt>Total</dt><dd>{money(order.grandTotal)}</dd></div></dl>
        </section>
      </div>

      <section className="rounded-3xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 p-5 md:p-6">
        <div className="flex items-center gap-2"><Clock3 className="w-5 h-5" /><h2 className="text-lg font-black">Status history</h2></div>
        <div className="mt-5 space-y-0">{(order.statusHistory || []).map((entry, index, history) => <div key={`${entry.timestamp}-${index}`} className="flex gap-3"><div className="flex flex-col items-center"><span className="w-3 h-3 rounded-full bg-lime-500 mt-1.5" />{index < history.length - 1 && <span className="w-px flex-1 min-h-10 bg-neutral-200 dark:bg-neutral-700" />}</div><div className="pb-5"><strong className="capitalize">{label(entry.status)}</strong><p className="text-xs text-neutral-500 mt-0.5">{dateTime(entry.timestamp)}</p>{entry.note && <p className="text-sm text-neutral-600 dark:text-neutral-400 mt-1">{entry.note}</p>}</div></div>)}</div>
      </section>

      <div className="flex flex-wrap gap-3"><Link to="/orders" className="px-5 py-3 rounded-xl bg-neutral-950 text-white dark:bg-white dark:text-neutral-950 font-bold">All orders</Link><Link to="/" className="px-5 py-3 rounded-xl border border-neutral-300 dark:border-neutral-700 font-bold">Continue shopping</Link></div>
    </div>
  );
};
