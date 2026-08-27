import React, { useMemo, useState } from 'react';
import { RotateCcw, XCircle } from 'lucide-react';
import {
  returnApi,
  type ReturnRequest,
  type ReturnRequestType,
} from '../services/businessApi';
import type { ServerOrder, TrustedOrderItem } from '../services/paymentApi';

type CancellationRequest = NonNullable<ServerOrder['cancellationRequest']>;
type Draft = {
  item: TrustedOrderItem;
  requestType: ReturnRequestType;
  reason: string;
  details: string;
  quantity: number;
};

const closedStatuses = new Set(['REJECTED', 'REFUNDED', 'EXCHANGED', 'CANCELLED']);
const label = (value: string) => value.replace(/_/g, ' ').toLowerCase();
export const CustomerOrderSupport: React.FC<{
  order: ServerOrder;
  requests: ReturnRequest[];
  onRequestCreated: (request: ReturnRequest) => void;
  onCancellationCreated: (request: CancellationRequest) => void;
}> = ({ order, requests, onRequestCreated, onCancellationCreated }) => {
  const [draft, setDraft] = useState<Draft | null>(null);
  const [cancelOpen, setCancelOpen] = useState(false);
  const [cancelReason, setCancelReason] = useState<'CUSTOMER_REQUEST' | 'ORDERED_BY_MISTAKE'>('CUSTOMER_REQUEST');
  const [cancelDetails, setCancelDetails] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const orderRequests = useMemo(
    () => requests.filter(request => request.orderId === order.id),
    [requests, order.id],
  );

  const activeFor = (item: TrustedOrderItem) => orderRequests.find(request =>
    request.productId === item.productId
    && request.variantId === item.variantId
    && !closedStatuses.has(request.status),
  );
  const cancellationAvailable = !order.cancellationRequest
    && order.isPaymentTestOrder !== true
    && order.fulfillmentRequired !== false
    && order.paymentStatus !== 'refunded'
    && !['packed', 'out_for_delivery', 'delivered', 'cancelled'].includes(order.status)
    && !(order.fulfillments || []).some(item => ['SHIPPED', 'DELIVERED'].includes(item.status));

  const openRequest = (item: TrustedOrderItem, requestType: ReturnRequestType) => {
    setError('');
    setDraft({
      item,
      requestType,
      reason: requestType === 'SIZE_EXCHANGE' ? 'SIZE_ISSUE' : 'WRONG_ITEM',
      details: '',
      quantity: 1,
    });
  };

  const submitReturn = async () => {
    if (!draft) return;
    setBusy(true);
    setError('');
    try {
      const created = await returnApi.create(order.id, {
        productId: draft.item.productId,
        variantId: draft.item.variantId,
        requestType: draft.requestType,
        reason: draft.reason,
        details: draft.details.trim() || undefined,
        quantity: draft.quantity,
      });
      onRequestCreated(created);
      setDraft(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Return request could not be submitted.');
    } finally {
      setBusy(false);
    }
  };
  const submitCancellation = async () => {
    setBusy(true);
    setError('');
    try {
      const created = await returnApi.requestCancellation(order.id, {
        reason: cancelReason,
        details: cancelDetails.trim() || undefined,
      });
      onCancellationCreated(created);
      setCancelOpen(false);
      setCancelDetails('');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Cancellation request could not be submitted.');
    } finally {
      setBusy(false);
    }
  };

  return <section className="space-y-3 rounded-2xl border border-neutral-200 p-4 dark:border-neutral-700" aria-label={`Order support ${order.id}`}>
    <div className="flex flex-wrap items-center justify-between gap-2">
      <div><p className="text-xs font-black uppercase tracking-wider text-neutral-500">Returns & cancellation</p><p className="text-xs text-neutral-500">Requests are reviewed before any exchange, cancellation, or refund is completed.</p></div>
      {cancellationAvailable && <button type="button" onClick={() => setCancelOpen(value => !value)} className="rounded-xl border px-3 py-2 text-xs font-black dark:border-neutral-700"><XCircle className="mr-1 inline w-4" />Request cancellation</button>}
    </div>
    {error && <p role="alert" className="rounded-xl bg-red-50 p-3 text-xs font-bold text-red-700 dark:bg-red-950/30 dark:text-red-300">{error}</p>}
    {order.cancellationRequest && <div className="rounded-xl bg-amber-50 p-3 text-xs text-amber-900 dark:bg-amber-950/30 dark:text-amber-200">
      <p className="font-black">Cancellation request: {label(order.cancellationRequest.status)}</p>
      <p className="mt-1">Reason: {label(order.cancellationRequest.reason)}</p>
      {order.cancellationRequest.adminNote && <p className="mt-1">Admin note: {order.cancellationRequest.adminNote}</p>}
      {order.cancellationRequest.status === 'APPROVED' && <p className="mt-1 font-bold">Approved request only. Refund/cancellation processing may still be pending.</p>}
    </div>}

    {cancelOpen && !order.cancellationRequest && <div className="space-y-3 rounded-xl bg-neutral-50 p-3 dark:bg-neutral-800">
      <label className="block text-xs font-bold">Reason<select value={cancelReason} onChange={event => setCancelReason(event.target.value as typeof cancelReason)} className="mt-1 w-full rounded-lg border bg-white px-3 py-2 dark:border-neutral-700 dark:bg-neutral-900"><option value="CUSTOMER_REQUEST">I no longer need this order</option><option value="ORDERED_BY_MISTAKE">Ordered by mistake</option></select></label>
      <label className="block text-xs font-bold">Details (optional)<textarea value={cancelDetails} onChange={event => setCancelDetails(event.target.value)} maxLength={1000} className="mt-1 min-h-20 w-full rounded-lg border bg-white px-3 py-2 font-normal dark:border-neutral-700 dark:bg-neutral-900" /></label>
      <div className="flex gap-2"><button type="button" disabled={busy} onClick={submitCancellation} className="rounded-lg bg-neutral-950 px-3 py-2 text-xs font-black text-white disabled:opacity-50 dark:bg-lime-400 dark:text-neutral-950">{busy ? 'Submitting…' : 'Submit cancellation request'}</button><button type="button" disabled={busy} onClick={() => setCancelOpen(false)} className="rounded-lg border px-3 py-2 text-xs font-bold dark:border-neutral-700">Close</button></div>
    </div>}
    <div className="space-y-2">{order.items.map(item => {
      const active = activeFor(item);
      const eligibility = item.returnEligibility;
      const canIssue = eligibility?.issueReturn.available === true;
      const canExchange = eligibility?.sizeExchange.available === true;
      if (!active && !canIssue && !canExchange) return null;
      return <div key={`${item.productId}-${item.variantId}`} className="rounded-xl bg-neutral-50 p-3 text-xs dark:bg-neutral-800">
        <div className="flex flex-wrap items-center justify-between gap-2"><span className="font-bold">{item.productName}</span>{active && <span className="font-black text-lime-700">{label(active.status)}</span>}</div>
        {active ? <div className="mt-2 text-neutral-600 dark:text-neutral-300"><p>{label(active.requestType)} · {label(active.reason)}</p>{active.sellerNote && <p>Seller note: {active.sellerNote}</p>}{active.adminNote && <p>Admin note: {active.adminNote}</p>}</div>
          : <div className="mt-2 flex flex-wrap gap-2">{canIssue && <button type="button" onClick={() => openRequest(item, 'ISSUE_RETURN')} className="rounded-lg border px-3 py-2 font-black dark:border-neutral-700"><RotateCcw className="mr-1 inline w-4" />Report item issue</button>}{canExchange && <button type="button" onClick={() => openRequest(item, 'SIZE_EXCHANGE')} className="rounded-lg border px-3 py-2 font-black dark:border-neutral-700">Request size exchange</button>}</div>}
      </div>;
    })}</div>
    {draft && <div className="space-y-3 rounded-xl border p-3 dark:border-neutral-700">
      <div><p className="text-xs font-black uppercase tracking-wider text-neutral-500">{draft.requestType === 'SIZE_EXCHANGE' ? 'Size exchange request' : 'Item issue report'}</p><p className="font-bold">{draft.item.productName}</p></div>
      {draft.requestType === 'ISSUE_RETURN' && <label className="block text-xs font-bold">Issue<select value={draft.reason} onChange={event => setDraft(current => current ? { ...current, reason: event.target.value } : current)} className="mt-1 w-full rounded-lg border bg-transparent px-3 py-2 dark:border-neutral-700"><option value="WRONG_ITEM">Wrong item</option><option value="DAMAGED">Damaged</option><option value="DEFECTIVE">Defective</option><option value="MISSING_ITEM">Missing item</option></select></label>}
      <label className="block text-xs font-bold">Quantity<input type="number" min={1} max={draft.item.quantity} value={draft.quantity} onChange={event => setDraft(current => current ? { ...current, quantity: Math.max(1, Math.min(current.item.quantity, Number(event.target.value) || 1)) } : current)} className="mt-1 w-full rounded-lg border bg-transparent px-3 py-2 dark:border-neutral-700" /></label>
      <label className="block text-xs font-bold">Details (optional)<textarea value={draft.details} onChange={event => setDraft(current => current ? { ...current, details: event.target.value } : current)} maxLength={1000} className="mt-1 min-h-20 w-full rounded-lg border bg-transparent px-3 py-2 font-normal dark:border-neutral-700" /></label>
      <p className="text-[11px] text-neutral-500">The server will verify delivery time, request window, purchased quantity, and item eligibility again when you submit.</p>
      <div className="flex gap-2"><button type="button" disabled={busy} onClick={submitReturn} className="rounded-lg bg-neutral-950 px-3 py-2 text-xs font-black text-white disabled:opacity-50 dark:bg-lime-400 dark:text-neutral-950">{busy ? 'Submitting…' : 'Submit request'}</button><button type="button" disabled={busy} onClick={() => setDraft(null)} className="rounded-lg border px-3 py-2 text-xs font-bold dark:border-neutral-700">Close</button></div>
    </div>}
  </section>;
};
