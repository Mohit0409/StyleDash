import React, { useEffect, useState } from 'react';
import { Globe2, Package, Phone, RefreshCw } from 'lucide-react';
import { ApiError } from '../services/apiClient';
import { type MediatorOrder, mediatorOrderApi } from '../services/businessApi';

const money = (value: number) => `₹${Number(value || 0).toFixed(2).replace(/\.00$/, '')}`;

export const SellerMediatorOrders: React.FC = () => {
  const [orders, setOrders] = useState<MediatorOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = () => {
    setLoading(true);
    setError('');
    mediatorOrderApi.sellerMine()
      .then(setOrders)
      .catch(cause => setError(cause instanceof ApiError || cause instanceof Error
        ? cause.message
        : 'All India orders could not be loaded.'))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  return (
    <section className="rounded-3xl border border-neutral-200 bg-white p-6 shadow-sm dark:border-neutral-800 dark:bg-neutral-900 space-y-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2"><Globe2 className="h-5 w-5 text-lime-600" /><h2 className="text-lg font-black">All India order requests</h2></div>
          <p className="mt-1 text-xs text-neutral-500">Contact the customer directly to confirm payment, courier charge and shipping.</p>
        </div>
        <button type="button" onClick={load} disabled={loading} className="rounded-xl border p-2 disabled:opacity-50" aria-label="Refresh All India orders"><RefreshCw className="h-4 w-4" /></button>
      </div>

      {loading ? <p className="text-sm text-neutral-500">Loading order requests…</p>
        : error ? <p role="alert" className="text-sm font-semibold text-red-600">{error}</p>
          : orders.length === 0 ? <div className="rounded-2xl border border-dashed p-6 text-center text-sm text-neutral-500"><Package className="mx-auto mb-2 h-7 w-7" />No All India order requests yet.</div>
            : <div className="space-y-4">{orders.map(order => (
              <article key={order.id} className="rounded-2xl border border-neutral-200 p-4 dark:border-neutral-800 space-y-3">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div><strong>{order.id}</strong><p className="text-xs text-neutral-500">{new Date(order.createdAt).toLocaleString()}</p></div>
                  <span className="rounded-full bg-lime-100 px-3 py-1 text-[11px] font-black text-lime-800 dark:bg-lime-950/40 dark:text-lime-300">{order.status}</span>
                </div>
                <div className="space-y-2 border-y border-neutral-100 py-3 text-sm dark:border-neutral-800">
                  {order.items.map(item => <div key={item.variantId} className="flex justify-between gap-3"><span>{item.productName} · {item.size || '—'} · {item.colourName || '—'} × {item.quantity}</span><strong>{money(item.lineTotal)}</strong></div>)}
                  <div className="flex justify-between pt-1 font-black"><span>Merchandise total</span><span>{money(order.merchandiseTotal)}</span></div>
                </div>
                <div className="rounded-xl bg-neutral-50 p-3 text-xs leading-relaxed dark:bg-neutral-800/70">
                  <p className="font-black">{order.shippingPayer === 'shop' ? 'Shop pays shipping' : 'Customer pays shipping'}</p>
                  <p className="mt-1">{order.shippingPayer === 'shop' ? 'Do not ask the customer for a separate courier charge.' : 'Confirm the courier charge with the customer before shipping.'}</p>
                </div>
                <div className="text-sm">
                  <p className="font-black">{order.address.name}</p>
                  <p className="mt-1 flex items-center gap-1"><Phone className="h-3.5 w-3.5" />{order.address.phone}</p>
                  <p className="mt-1 text-neutral-600 dark:text-neutral-400">{order.address.street}, {order.address.city}, {order.address.state} - {order.address.pincode}</p>
                </div>
                <p className="text-[11px] font-semibold text-amber-700 dark:text-amber-300">Vibe4You has not collected payment or shipping charges for this request.</p>
              </article>
            ))}</div>}
    </section>
  );
};
