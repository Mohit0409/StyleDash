import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Package } from 'lucide-react';
import { SEO } from '../components/SEO';
import { orderApi } from '../services/businessApi';
import { ServerOrder } from '../services/paymentApi';

export const Orders: React.FC = () => {
  const [orders, setOrders] = useState<ServerOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  useEffect(() => { orderApi.mine().then(setOrders).catch(e => setError(e.message)).finally(() => setLoading(false)); }, []);
  return <div className="max-w-4xl mx-auto px-4 py-8 space-y-8"><SEO title="Order History - StyleDash" />
    <div><h1 className="text-3xl font-black">Your Orders &amp; Doorstep Tracking</h1><p className="text-xs text-neutral-500">Only orders owned by your authenticated account are shown.</p></div>
    {loading ? <div className="text-center py-12">Loading orders…</div> : error ? <p role="alert" className="text-red-600">{error}</p> : orders.length === 0 ? <div className="p-12 text-center bg-white dark:bg-neutral-900 rounded-3xl border space-y-4"><Package className="w-12 h-10 mx-auto"/><h3 className="font-bold">No orders placed yet</h3><Link to="/products" className="font-bold text-lime-600">Start shopping</Link></div> : <div className="space-y-4">{orders.map(order => <div key={order.id} className="p-6 bg-white dark:bg-neutral-900 rounded-3xl border dark:border-neutral-800 space-y-4"><div className="flex justify-between"><div><strong>Order {order.id}</strong><small className="block text-neutral-500">{new Date(order.createdAt).toLocaleDateString()}</small></div><div><span className="font-bold uppercase text-lime-600">{order.status}</span> · <strong>₹{order.grandTotal}</strong></div></div>{order.items.map(item => <div key={item.variantId} className="flex justify-between text-sm"><span>{item.productName} ({item.size}, {item.colourName}) × {item.quantity}</span><strong>₹{item.lineTotal}</strong></div>)}</div>)}</div>}
  </div>;
};
