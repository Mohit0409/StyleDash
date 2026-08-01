import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { CheckCircle2, Zap, Package, MapPin, ArrowRight } from 'lucide-react';
import { SEO } from '../components/SEO';
import { orderRepository } from '../repositories/orderRepository';
import { Order } from '../types';

export const OrderSuccess: React.FC = () => {
  const { orderId } = useParams<{ orderId: string }>();
  const [order, setOrder] = useState<Order | null>(null);

  useEffect(() => {
    if (orderId) {
      orderRepository.getOrderById(orderId).then(o => setOrder(o));
    }
  }, [orderId]);

  return (
    <div className="max-w-2xl mx-auto px-4 py-16 text-center space-y-8">
      <SEO title="Order Confirmed - StyleDash" />

      <div className="w-20 h-20 bg-lime-400 text-neutral-950 rounded-full flex items-center justify-center mx-auto shadow-xl">
        <CheckCircle2 className="w-10 h-10" />
      </div>

      <div className="space-y-2">
        <span className="text-xs font-black uppercase tracking-widest text-lime-600 dark:text-lime-400">60-Min Express Dispatch</span>
        <h1 className="text-3xl font-black text-neutral-900 dark:text-white">Order Confirmed!</h1>
        <p className="text-xs text-neutral-500">Order Reference ID: <strong className="text-neutral-900 dark:text-white">{orderId}</strong></p>
      </div>

      {order && (
        <div className="p-6 bg-white dark:bg-neutral-900 rounded-3xl border border-neutral-200 dark:border-neutral-800 text-left space-y-4 shadow-sm text-xs">
          <div className="flex items-center justify-between pb-3 border-b border-neutral-100 dark:border-neutral-800">
            <span className="font-bold text-neutral-500">Estimated Delivery Time</span>
            <span className="font-extrabold text-lime-600 dark:text-lime-400 flex items-center gap-1">
              <Zap className="w-4 h-4 fill-lime-400" /> {order.estimatedDelivery}
            </span>
          </div>

          <div className="space-y-2">
            <span className="font-bold text-neutral-900 dark:text-white">Items Ordered ({order.items.length})</span>
            {order.items.map(item => (
              <div key={item.lineId} className="flex justify-between text-neutral-600 dark:text-neutral-400">
                <span>{item.product.name} ({item.selectedSize}, {item.selectedColour}) x {item.quantity}</span>
                <span className="font-bold text-neutral-900 dark:text-white">₹{item.unitPrice * item.quantity}</span>
              </div>
            ))}
          </div>

          <div className="pt-3 border-t border-neutral-100 dark:border-neutral-800 flex justify-between font-black text-sm">
            <span>Amount Paid</span>
            <span className="text-lime-600 dark:text-lime-400">₹{order.grandTotal}</span>
          </div>
        </div>
      )}

      <div className="flex justify-center gap-4">
        <Link to="/orders" className="px-6 py-3 bg-neutral-950 dark:bg-lime-400 text-white dark:text-neutral-950 font-bold text-xs rounded-xl">
          Track Order Status
        </Link>
        <Link to="/" className="px-6 py-3 bg-neutral-100 dark:bg-neutral-800 font-bold text-xs rounded-xl">
          Continue Shopping
        </Link>
      </div>
    </div>
  );
};
