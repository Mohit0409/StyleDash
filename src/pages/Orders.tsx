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

export const Orders: React.FC = () => {
  const [orders, setOrders] = useState<ServerOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    orderApi.mine().then(setOrders).catch((cause) => setError(cause instanceof Error ? cause.message : 'Orders could not be loaded.')).finally(() => setLoading(false));
  }, []);

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
              <div className="divide-y divide-neutral-200 dark:divide-neutral-800">{order.items.map(item => <div key={item.variantId} className="py-3 first:pt-0 last:pb-0 flex items-center gap-3">
                <div className="w-14 h-14 rounded-xl bg-neutral-100 dark:bg-neutral-800 overflow-hidden shrink-0">{item.imageUrl ? <img src={item.imageUrl} alt="" className="w-full h-full object-cover" /> : <div className="w-full h-full grid place-items-center"><Package className="w-5 h-5 text-neutral-400" /></div>}</div>
                <div className="min-w-0 flex-1"><div className="flex items-center gap-1 text-xs font-bold text-neutral-500"><Store className="w-3.5 h-3.5" />{item.storeName || 'Vibe4You'}</div><p className="font-bold truncate">{item.productName}</p><p className="text-sm text-neutral-500">Size {item.size || '—'} · Color {item.colourName || '—'} · Qty {item.quantity}</p></div>
                <strong className="shrink-0">₹{item.lineTotal}</strong>
              </div>)}</div>
              {order.status === 'cancelled' && order.cancellationReason && <div className="rounded-xl border border-red-200 bg-red-50 dark:border-red-900 dark:bg-red-950/20 p-3 text-sm"><strong>Cancellation reason:</strong> {order.cancellationReason}</div>}
              <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
                <p className="text-sm text-neutral-500">Deliver to <strong className="text-neutral-800 dark:text-neutral-200">{order.address.name}</strong> · {order.address.phone}</p>
                <Link to={`/orders/${encodeURIComponent(order.id)}/track`} className="px-4 py-2.5 rounded-xl bg-neutral-950 text-white dark:bg-lime-400 dark:text-neutral-950 font-black">Track order</Link>
              </div>
            </article>)}</div>}
    </div>
  );
};
