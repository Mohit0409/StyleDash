import React, { useEffect, useState } from 'react';
import { CheckCircle2 } from 'lucide-react';
import { Link, useParams } from 'react-router-dom';
import { SEO } from '../components/SEO';
import { type MediatorOrder, mediatorOrderApi } from '../services/businessApi';

const money = (value: number) => `₹${Number(value || 0).toFixed(2).replace(/\.00$/, '')}`;

export const MediatorOrderSuccess: React.FC = () => {
  const { orderId = '' } = useParams();
  const [order, setOrder] = useState<MediatorOrder | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    mediatorOrderApi.one(orderId)
      .then(result => { if (active) setOrder(result); })
      .catch(cause => { if (active) setError(cause instanceof Error ? cause.message : 'Order request could not be loaded.'); });
    return () => { active = false; };
  }, [orderId]);

  return (
    <div className="mx-auto max-w-2xl space-y-7 px-4 py-14 text-center">
      <SEO title="All India Order Sent - Vibe4You" noIndex />
      <CheckCircle2 className="mx-auto h-20 w-20 rounded-full bg-lime-400 p-4 text-neutral-950" />
      <div>
        <h1 className="text-3xl font-black">Order request sent to the shop</h1>
        <p className="mt-2 text-sm text-neutral-500">Reference: <strong>{orderId}</strong></p>
      </div>
      {error ? <p role="alert" className="text-red-600">{error}</p>
        : order ? <div className="space-y-4 rounded-3xl border bg-white p-6 text-left dark:border-neutral-800 dark:bg-neutral-900">
          <div><p className="text-xs font-bold uppercase text-neutral-500">Shop</p><p className="font-black">{order.shopName}</p></div>
          <div className="space-y-2 border-y py-4 dark:border-neutral-800">{order.items.map(item => <div key={item.variantId} className="flex justify-between gap-3 text-sm"><span>{item.productName} · {item.size || '—'} × {item.quantity}</span><strong>{money(item.lineTotal)}</strong></div>)}</div>
          <div className="flex justify-between font-black"><span>Merchandise total</span><span>{money(order.merchandiseTotal)}</span></div>
          <div className="rounded-2xl bg-amber-50 p-4 text-sm leading-relaxed text-amber-900 dark:bg-amber-950/20 dark:text-amber-200">
            <strong>{order.shippingPayer === 'shop' ? 'Shop pays the shipping charge.' : 'You pay the shipping charge.'}</strong>
            <p className="mt-1">Vibe4You is only the mediator for this All India order. No product payment or shipping charge was collected by Vibe4You. The shop will contact you to confirm availability, payment and courier arrangements.</p>
          </div>
        </div>
          : <p className="text-sm text-neutral-500">Loading order request…</p>}
      <Link to="/" className="inline-flex rounded-xl bg-neutral-950 px-6 py-3 font-black text-white dark:bg-lime-400 dark:text-neutral-950">Continue shopping</Link>
    </div>
  );
};
