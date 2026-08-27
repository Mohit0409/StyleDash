import React, { useState } from 'react';
import { MapPin, PackageCheck, Truck } from 'lucide-react';
import { sellerOrderApi, type SellerFulfillmentStatus, type SellerOrder } from '../services/businessApi';

const actionLabel: Record<SellerFulfillmentStatus, string> = {
  NEW: 'New', PROCESSING: 'Start processing', READY: 'Mark ready',
  SHIPPED: 'Mark shipped', DELIVERED: 'Mark delivered',
};

type ShippingDetails = { carrier: string; trackingNumber: string };

export const SellerOrders: React.FC<{
  orders: SellerOrder[];
  loading?: boolean;
  onOrderChange?: (order: SellerOrder) => void;
}> = ({ orders, loading, onOrderChange }) => {
  const [updatingId, setUpdatingId] = useState('');
  const [error, setError] = useState('');

  const advance = async (
    order: SellerOrder,
    status: SellerFulfillmentStatus,
    shipping?: ShippingDetails,
  ) => {
    setUpdatingId(order.id);
    setError('');
    try {
      const fulfillment = await sellerOrderApi.updateFulfillment(order.id, status, shipping);
      onOrderChange?.({ ...order, fulfillment });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Fulfillment status could not be updated.');
    } finally {
      setUpdatingId('');
    }
  };

  return <section className="space-y-4 rounded-3xl border border-neutral-200 bg-white p-6 dark:border-neutral-800 dark:bg-neutral-900" aria-labelledby="seller-orders-heading">
    <div>
      <h3 id="seller-orders-heading" className="text-xl font-black">Seller Orders</h3>
      <p className="mt-1 text-xs text-neutral-500">Only items sold by your shop are shown. Payment identifiers, refunds, and other shops&apos; items stay private.</p>
    </div>
    {error && <p role="alert" className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}
    {loading ? <p className="text-sm text-neutral-500">Loading seller orders...</p>
      : orders.length === 0 ? <p className="rounded-2xl bg-neutral-50 p-4 text-sm text-neutral-500 dark:bg-neutral-800">No orders for your shop yet.</p>
        : <div className="space-y-4">{orders.map(order => <OrderCard key={order.id} order={order} busy={updatingId === order.id} onAdvance={advance} />)}</div>}
  </section>;
};

const OrderCard: React.FC<{
  order: SellerOrder;
  busy: boolean;
  onAdvance: (order: SellerOrder, status: SellerFulfillmentStatus, shipping?: ShippingDetails) => void;
}> = ({ order, busy, onAdvance }) => {
  const created = order.createdAt ? new Date(order.createdAt).toLocaleString() : 'Time unavailable';
  const fulfillment = order.fulfillment || {
    status: 'NEW' as const, updatedAt: null, allowedNextStatuses: ['PROCESSING' as const], shipping: null,
  };
  const next = fulfillment.allowedNextStatuses[0];
  const [carrier, setCarrier] = useState(fulfillment.shipping?.carrier || '');
  const [trackingNumber, setTrackingNumber] = useState(fulfillment.shipping?.trackingNumber || '');
  const carrierValue = carrier.trim();
  const trackingValue = trackingNumber.trim();
  const shippingIncomplete = Boolean(carrierValue) !== Boolean(trackingValue);
  const shippingPayload = carrierValue && trackingValue
    ? { carrier: carrierValue, trackingNumber: trackingValue }
    : undefined;
  const showShippingEditor = next === 'SHIPPED' || fulfillment.status === 'SHIPPED';
  const shippingChanged = fulfillment.status === 'SHIPPED' && Boolean(shippingPayload) && (
    shippingPayload?.carrier !== fulfillment.shipping?.carrier
    || shippingPayload?.trackingNumber !== fulfillment.shipping?.trackingNumber
  );

  return <article className="rounded-2xl border p-4 dark:border-neutral-700">
    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
      <div><p className="text-xs font-black uppercase tracking-wider text-neutral-500">{order.id}</p><p className="mt-1 text-sm text-neutral-500">{created}</p></div>
      <div className="flex flex-wrap gap-2 text-xs font-bold"><span className="rounded-lg bg-neutral-100 px-3 py-1.5 dark:bg-neutral-800">Global: {order.status || 'order received'}</span><span className="rounded-lg bg-lime-100 px-3 py-1.5 text-lime-900">{order.paymentStatus || order.paymentMethod || 'payment pending'}</span></div>
    </div>
    <div className="mt-4 space-y-2">{order.items.map((item, index) => <div key={`${item.productId}-${item.variantId || index}`} className="flex items-start justify-between gap-4 rounded-xl bg-neutral-50 p-3 text-sm dark:bg-neutral-800">
      <div><p className="font-bold">{item.productName || item.productId}</p><p className="text-xs text-neutral-500">{[item.size, item.colourName].filter(Boolean).join(' / ') || 'Standard option'} / Qty {item.quantity}</p></div>
      <p className="font-black">INR {item.lineTotal}</p>
    </div>)}</div>
    <div className="mt-4 flex items-center justify-between border-t pt-4 text-sm dark:border-neutral-700"><span className="font-bold">Your shop subtotal</span><span className="text-lg font-black">INR {order.sellerSubtotal}</span></div>
    <div className="mt-4 grid gap-3 sm:grid-cols-2">
      <div className="rounded-xl border p-3 dark:border-neutral-700"><div className="flex items-center gap-2 text-xs font-black uppercase tracking-wider text-neutral-500"><MapPin className="w-4" />Delivery</div><p className="mt-2 text-sm font-semibold">{order.address.name || 'Customer'}</p><p className="text-xs text-neutral-500">{order.address.phone || 'Phone unavailable'}</p><p className="mt-1 text-xs text-neutral-500">{[order.address.street, order.address.city, order.address.state, order.address.pincode].filter(Boolean).join(', ')}</p></div>
      <div className="rounded-xl border p-3 dark:border-neutral-700">
        <div className="flex items-center gap-2 text-xs font-black uppercase tracking-wider text-neutral-500"><Truck className="w-4" />Your fulfillment</div>
        <p className="mt-2 text-sm font-black">{fulfillment.status.replace('_', ' ')}</p>
        <p className="mt-1 text-xs text-neutral-500">{order.deliveryMethod || 'Delivery method pending'} · This status applies only to your shop items.</p>
        {fulfillment.shipping && <div className="mt-2 rounded-lg bg-neutral-50 p-2 text-xs dark:bg-neutral-800"><p><strong>Carrier:</strong> {fulfillment.shipping.carrier}</p><p>Tracking: {fulfillment.shipping.trackingNumber}</p></div>}
        {showShippingEditor && <div className="mt-3 space-y-2">
          <label className="block text-xs font-bold">Carrier (optional)<input value={carrier} onChange={event => setCarrier(event.target.value)} maxLength={80} className="mt-1 w-full rounded-lg border bg-transparent px-3 py-2 font-normal dark:border-neutral-700" /></label>
          <label className="block text-xs font-bold">Tracking number (optional)<input value={trackingNumber} onChange={event => setTrackingNumber(event.target.value)} maxLength={120} className="mt-1 w-full rounded-lg border bg-transparent px-3 py-2 font-normal dark:border-neutral-700" /></label>
          {shippingIncomplete && <p className="text-xs font-bold text-red-600">Enter both carrier and tracking number, or leave both blank.</p>}
          {shippingChanged && <button type="button" disabled={busy || shippingIncomplete} onClick={() => shippingPayload && onAdvance(order, 'SHIPPED', shippingPayload)} className="rounded-lg border px-3 py-2 text-xs font-black disabled:opacity-50 dark:border-neutral-700">{busy ? 'Saving…' : 'Save tracking'}</button>}
        </div>}
        {next ? <button type="button" disabled={busy || (next === 'SHIPPED' && shippingIncomplete)} onClick={() => onAdvance(order, next, next === 'SHIPPED' ? shippingPayload : undefined)} className="mt-3 rounded-xl bg-neutral-950 px-4 py-2 text-xs font-black text-white disabled:cursor-not-allowed disabled:opacity-50 dark:bg-lime-400 dark:text-neutral-950">{busy ? 'Updating…' : actionLabel[next]}</button>
          : <p className="mt-3 flex items-center gap-2 text-xs font-bold text-lime-700"><PackageCheck className="w-4" />Fulfillment completed for your shop.</p>}
      </div>
    </div>
  </article>;
};
