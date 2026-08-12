import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Package, Clock, Zap, CheckCircle2, ChevronRight } from 'lucide-react';
import { SEO } from '../components/SEO';
import { orderRepository } from '../repositories/orderRepository';
import { Order } from '../types';
import { useAuth } from '../context/AuthContext';

export const Orders: React.FC = () => {
  const { user } = useAuth();
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const uid = user ? user.uid : 'guest-user-id';
    orderRepository.getOrdersByUser(uid).then(o => {
      setOrders(o);
      setLoading(false);
    });
  }, [user]);

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      <SEO title="Order History - StyleDash" />

      <div>
        <h1 className="text-2xl sm:text-3xl font-black text-neutral-900 dark:text-white">Your Orders & Doorstep Tracking</h1>
        <p className="text-xs text-neutral-500 mt-1">Track live 60-minute fashion dispatches in Neemuch</p>
      </div>

      {loading ? (
        <div className="text-center py-12 text-xs text-neutral-500">Loading orders...</div>
      ) : orders.length === 0 ? (
        <div className="p-12 text-center bg-white dark:bg-neutral-900 rounded-3xl border border-neutral-200 dark:border-neutral-800 space-y-4">
          <Package className="w-12 h-10 text-neutral-400 mx-auto" />
          <h3 className="font-bold text-base">No orders placed yet</h3>
          <p className="text-xs text-neutral-500">Discover trending outfits and get delivery within 60 minutes.</p>
          <Link to="/products" className="inline-block px-6 py-2.5 bg-neutral-950 dark:bg-lime-400 text-white dark:text-neutral-950 text-xs font-bold rounded-xl">
            Start Shopping
          </Link>
        </div>
      ) : (
        <div className="space-y-4">
          {orders.map(order => (
            <div key={order.id} className="p-6 bg-white dark:bg-neutral-900 rounded-3xl border border-neutral-200 dark:border-neutral-800 space-y-4 shadow-sm">
              <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-neutral-100 dark:border-neutral-800 text-xs">
                <div>
                  <span className="font-bold text-neutral-900 dark:text-white">Order {order.id}</span>
                  <span className="text-neutral-400 block text-[10px]">{new Date(order.createdAt).toLocaleDateString()}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="px-3 py-1 rounded-full bg-lime-100 dark:bg-lime-950 text-lime-800 dark:text-lime-300 font-extrabold uppercase text-[10px]">
                    {order.status}
                  </span>
                  <span className="font-black text-neutral-900 dark:text-white">₹{order.grandTotal}</span>
                </div>
              </div>

              {/* Items */}
              <div className="space-y-2 text-xs">
                {order.items.map(item => (
                  <div key={item.lineId} className="flex justify-between items-center text-neutral-700 dark:text-neutral-300">
                    <span>{item.product.name} ({item.selectedSize}, {item.selectedColour}) x {item.quantity}</span>
                    <span className="font-bold text-neutral-900 dark:text-white">₹{item.unitPrice * item.quantity}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
