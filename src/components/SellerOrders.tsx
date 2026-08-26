import React from 'react';
import { MapPin, PackageCheck, Truck } from 'lucide-react';
import type { SellerOrder } from '../services/businessApi';

export const SellerOrders: React.FC<{ orders: SellerOrder[]; loading?: boolean }> = ({ orders, loading }) => (
  <section className="space-y-4 rounded-3xl border border-neutral-200 bg-white p-6 dark:border-neutral-800 dark:bg-neutral-900" aria-labelledby="seller-orders-heading">
    <div>
      <h3 id="seller-orders-heading" className="text-xl font-black">Seller Orders</h3>
      <p className="mt-1 text-xs text-neutral-500">Only items sold by your shop are shown. Payment identifiers, refunds, and other shops&apos; items stay private.</p>
    </div>
    {loading ? <p className="text-sm text-neutral-500">Loading seller orders...</p>
      : orders.length === 0 ? <p className="rounded-2xl bg-neutral-50 p-4 text-sm text-neutral-500 dark:bg-neutral-800">No orders for your shop yet.</p>
        : <div className="space-y-4">{orders.map(order => <OrderCard key={order.id} order={order} />)}</div>}
  </section>
);

const OrderCard: React.FC<{ order: SellerOrder }> = ({ order }) => {
  const created = order.createdAt ? new Date(order.createdAt).toLocaleString() : 'Time unavailable';
  return <article className="rounded-2xl border p-4 dark:border-neutral-700">
    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
      <div><p className="text-xs font-black uppercase tracking-wider text-neutral-500">{order.id}</p><p className="mt-1 text-sm text-neutral-500">{created}</p></div>
      <div className="flex flex-wrap gap-2 text-xs font-bold"><span className="rounded-lg bg-neutral-100 px-3 py-1.5 dark:bg-neutral-800">{order.status || 'order received'}</span><span className="rounded-lg bg-lime-100 px-3 py-1.5 text-lime-900">{order.paymentStatus || order.paymentMethod || 'payment pending'}</span></div>
    </div>
    <div className="mt-4 space-y-2">{order.items.map((item, index) => <div key={`${item.productId}-${item.variantId || index}`} className="flex items-start justify-between gap-4 rounded-xl bg-neutral-50 p-3 text-sm dark:bg-neutral-800">
      <div><p className="font-bold">{item.productName || item.productId}</p><p className="text-xs text-neutral-500">{[item.size, item.colourName].filter(Boolean).join(' / ') || 'Standard option'} / Qty {item.quantity}</p></div>
      <p className="font-black">INR {item.lineTotal}</p>
    </div>)}</div>
    <div className="mt-4 flex items-center justify-between border-t pt-4 text-sm dark:border-neutral-700"><span className="font-bold">Your shop subtotal</span><span className="text-lg font-black">INR {order.sellerSubtotal}</span></div>
    <div className="mt-4 grid gap-3 sm:grid-cols-2">
      <div className="rounded-xl border p-3 dark:border-neutral-700"><div className="flex items-center gap-2 text-xs font-black uppercase tracking-wider text-neutral-500"><MapPin className="w-4" />Delivery</div><p className="mt-2 text-sm font-semibold">{order.address.name || 'Customer'}</p><p className="text-xs text-neutral-500">{order.address.phone || 'Phone unavailable'}</p><p className="mt-1 text-xs text-neutral-500">{[order.address.street, order.address.city, order.address.state, order.address.pincode].filter(Boolean).join(', ')}</p></div>
      <div className="rounded-xl border p-3 dark:border-neutral-700"><div className="flex items-center gap-2 text-xs font-black uppercase tracking-wider text-neutral-500"><Truck className="w-4" />Fulfillment</div><p className="mt-2 text-sm font-semibold">{order.deliveryMethod || 'Delivery method pending'}</p><p className="mt-1 flex items-center gap-2 text-xs text-neutral-500"><PackageCheck className="w-4" />Read-only in v1. Seller-specific fulfillment actions will be added without changing the global order state.</p></div>
    </div>
  </article>;
};
