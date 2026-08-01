import React, { useEffect, useState } from 'react';
import { SEO } from '../components/SEO';
import { productRepository } from '../repositories/productRepository';
import { orderRepository } from '../repositories/orderRepository';
import { Product, Order, OrderStatus } from '../types';

export const AdminDashboard: React.FC = () => {
  const [products, setProducts] = useState<Product[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [selectedStatus, setSelectedStatus] = useState<Record<string, OrderStatus>>({});

  useEffect(() => {
    productRepository.getAllProducts().then(p => setProducts(p));
    orderRepository.getAllOrders().then(o => setOrders(o));
  }, []);

  const totalRevenue = orders.reduce((acc, o) => acc + o.grandTotal, 0);

  const handleUpdateStatus = async (orderId: string) => {
    const st = selectedStatus[orderId];
    if (st) {
      await orderRepository.updateOrderStatus(orderId, st);
      const updated = await orderRepository.getAllOrders();
      setOrders(updated);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      <SEO title="Admin Dashboard - StyleDash" />

      <div>
        <h1 className="text-2xl sm:text-3xl font-black text-neutral-900 dark:text-white">StyleDash Admin & Store Portal</h1>
        <p className="text-xs text-neutral-500 mt-1">Hyperlocal inventory, orders & vendor management for Neemuch</p>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="p-5 bg-white dark:bg-neutral-900 rounded-2xl border border-neutral-200 dark:border-neutral-800">
          <span className="text-[10px] font-bold text-neutral-400 uppercase">Gross Revenue</span>
          <h3 className="text-2xl font-black text-lime-600 dark:text-lime-400">₹{totalRevenue}</h3>
        </div>
        <div className="p-5 bg-white dark:bg-neutral-900 rounded-2xl border border-neutral-200 dark:border-neutral-800">
          <span className="text-[10px] font-bold text-neutral-400 uppercase">Total Orders</span>
          <h3 className="text-2xl font-black text-neutral-900 dark:text-white">{orders.length}</h3>
        </div>
        <div className="p-5 bg-white dark:bg-neutral-900 rounded-2xl border border-neutral-200 dark:border-neutral-800">
          <span className="text-[10px] font-bold text-neutral-400 uppercase">Active Products</span>
          <h3 className="text-2xl font-black text-neutral-900 dark:text-white">{products.length}</h3>
        </div>
        <div className="p-5 bg-white dark:bg-neutral-900 rounded-2xl border border-neutral-200 dark:border-neutral-800">
          <span className="text-[10px] font-bold text-neutral-400 uppercase">Service City</span>
          <h3 className="text-2xl font-black text-neutral-900 dark:text-white">Neemuch</h3>
        </div>
      </div>

      {/* Orders Management Table */}
      <div className="bg-white dark:bg-neutral-900 rounded-3xl border border-neutral-200 dark:border-neutral-800 p-6 space-y-4">
        <h3 className="font-extrabold text-lg text-neutral-900 dark:text-white">Manage Orders</h3>
        {orders.length === 0 ? (
          <p className="text-xs text-neutral-500">No orders placed yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left text-neutral-700 dark:text-neutral-300">
              <thead className="bg-neutral-100 dark:bg-neutral-800 text-neutral-900 dark:text-white font-bold">
                <tr>
                  <th className="p-3">Order ID</th>
                  <th className="p-3">Customer</th>
                  <th className="p-3">Amount</th>
                  <th className="p-3">Current Status</th>
                  <th className="p-3">Update Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100 dark:divide-neutral-800">
                {orders.map(o => (
                  <tr key={o.id}>
                    <td className="p-3 font-bold">{o.id}</td>
                    <td className="p-3">{o.address.name} ({o.address.phone})</td>
                    <td className="p-3 font-bold">₹{o.grandTotal}</td>
                    <td className="p-3"><span className="px-2 py-0.5 rounded bg-lime-100 dark:bg-lime-900 text-lime-800 dark:text-lime-200 font-bold">{o.status}</span></td>
                    <td className="p-3 flex gap-2">
                      <select
                        onChange={(e) => setSelectedStatus({ ...selectedStatus, [o.id]: e.target.value as OrderStatus })}
                        className="p-1 rounded border border-neutral-300 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-800 text-xs"
                      >
                        <option value="placed">placed</option>
                        <option value="confirmed">confirmed</option>
                        <option value="packed">packed</option>
                        <option value="out_for_delivery">out_for_delivery</option>
                        <option value="delivered">delivered</option>
                        <option value="cancelled">cancelled</option>
                      </select>
                      <button
                        onClick={() => handleUpdateStatus(o.id)}
                        className="px-3 py-1 bg-neutral-950 dark:bg-lime-400 text-white dark:text-neutral-950 font-bold rounded"
                      >
                        Save
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
