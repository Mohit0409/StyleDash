import React, { useState } from 'react';
import { RotateCcw } from 'lucide-react';
import { sellerReturnApi, type ReturnRequest } from '../services/businessApi';

export const SellerReturns: React.FC<{
  requests: ReturnRequest[];
  loading?: boolean;
  onRequestChange?: (request: ReturnRequest) => void;
}> = ({ requests, loading, onRequestChange }) => {
  const [editingId, setEditingId] = useState('');
  const [note, setNote] = useState('');
  const [error, setError] = useState('');

  const saveNote = async (request: ReturnRequest) => {
    const value = note.trim();
    if (value.length < 2) return;
    setEditingId(request.id);
    setError('');
    try {
      const updated = await sellerReturnApi.addNote(request.id, value);
      onRequestChange?.(updated);
      setNote('');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Seller note could not be saved.');
    } finally {
      setEditingId('');
    }
  };

  return <section className="space-y-4 rounded-3xl border border-neutral-200 bg-white p-6 dark:border-neutral-800 dark:bg-neutral-900" aria-labelledby="seller-returns-heading">
    <div>
      <div className="flex items-center gap-2"><RotateCcw className="w-5 text-lime-600" /><h3 id="seller-returns-heading" className="text-xl font-black">Returns & Exchanges</h3></div>
      <p className="mt-1 text-xs text-neutral-500">Only requests tied to your shop are shown. Sellers can add review notes, but approval and refunds remain administrator-controlled.</p>
    </div>
    {error && <p role="alert" className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}
    {loading ? <p className="text-sm text-neutral-500">Loading requests...</p> : requests.length === 0 ? <p className="rounded-2xl bg-neutral-50 p-4 text-sm text-neutral-500 dark:bg-neutral-800">No return or exchange requests for your shop.</p> : <div className="space-y-4">
      {requests.map(request => <article key={request.id} className="rounded-2xl border p-4 dark:border-neutral-700">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div><p className="text-xs font-black uppercase tracking-wider text-neutral-500">Order {request.orderId}</p><h4 className="mt-1 font-black">{request.productName}</h4><p className="text-xs text-neutral-500">Qty {request.quantity} · {request.requestType.replace(/_/g, ' ')}</p></div>
          <span className="rounded-lg bg-lime-100 px-3 py-1.5 text-xs font-black text-lime-900">{request.status.replace(/_/g, ' ')}</span>
        </div>
        <div className="mt-3 rounded-xl bg-neutral-50 p-3 text-sm dark:bg-neutral-800"><p><strong>Reason:</strong> {request.reason.replace(/_/g, ' ')}</p>{request.details && <p className="mt-1 text-neutral-500">{request.details}</p>}</div>
        {request.sellerNote && <p className="mt-3 text-xs text-neutral-500"><strong>Your note:</strong> {request.sellerNote}</p>}
        {request.adminNote && <p className="mt-2 text-xs text-neutral-500"><strong>Admin note:</strong> {request.adminNote}</p>}
        {!['REJECTED','REFUNDED','EXCHANGED','CANCELLED'].includes(request.status) && <div className="mt-3 space-y-2">
          <textarea value={editingId === request.id ? note : ''} onChange={event => { setEditingId(request.id); setNote(event.target.value); }} maxLength={1000} placeholder="Add seller review note" className="min-h-20 w-full rounded-xl border bg-transparent px-3 py-2 text-sm dark:border-neutral-700" />
          <button type="button" disabled={editingId === request.id && note.trim().length < 2} onClick={() => saveNote(request)} className="rounded-xl border px-4 py-2 text-xs font-black disabled:opacity-50 dark:border-neutral-700">Save note</button>
        </div>}
      </article>)}
    </div>}
  </section>;
};
