import React, { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { CheckCircle2 } from 'lucide-react';
import { SEO } from '../components/SEO';
import { orderApi } from '../services/businessApi';
import { ServerOrder } from '../services/paymentApi';

export const OrderSuccess: React.FC = () => {
  const { orderId = '' } = useParams();
  const [order, setOrder] = useState<ServerOrder | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');
    orderApi.one(orderId)
      .then(result => { if (active) setOrder(result); })
      .catch(cause => { if (active) setError(cause instanceof Error ? cause.message : 'This order could not be loaded.'); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [orderId]);

  return (
    <div className="max-w-2xl mx-auto px-4 py-16 text-center space-y-8">
      <SEO title="Order Confirmed - Vibe4You" noIndex />
      <CheckCircle2 className="w-20 h-20 mx-auto p-4 rounded-full bg-lime-400 text-neutral-950" />
      <div>
        <h1 className="text-3xl font-black">Order Confirmed!</h1>
        <p className="text-xs">Order Reference ID: <strong>{orderId}</strong></p>
      </div>
      {loading ? <p>Loading confirmed order…</p>
        : error ? <p role="alert" className="text-red-600">{error}</p>
          : order ? <div className="p-6 text-left bg-white dark:bg-neutral-900 rounded-3xl border dark:border-neutral-800 space-y-3">
            {order.items.map(item => <div key={item.variantId} className="flex justify-between text-sm"><span>{item.productName} ({item.size}, {item.colourName}) × {item.quantity}</span><strong>₹{item.lineTotal}</strong></div>)}
            <div className="border-t pt-3 flex justify-between font-black"><span>Order total</span><span>₹{order.grandTotal}</span></div>
          </div> : <p role="alert">This order is unavailable to the current account.</p>}
      <div className="flex justify-center gap-4">
        <Link to={`/orders/${encodeURIComponent(orderId)}/track`} className="px-6 py-3 bg-neutral-950 text-white dark:bg-lime-400 dark:text-neutral-950 rounded-xl font-bold">Track order</Link>
        <Link to="/" className="px-6 py-3 bg-white dark:bg-neutral-900 border border-neutral-300 dark:border-neutral-700 text-neutral-950 dark:text-white rounded-xl font-bold">Continue shopping</Link>
      </div>
    </div>
  );
};
