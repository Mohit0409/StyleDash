import React, { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { ShieldCheck, Truck, X } from 'lucide-react';
import type { Product, ProductVariant } from '../types';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { deliveryRequestApi } from '../services/deliveryRequestApi';
import { ApiError } from '../services/apiClient';

interface Props {
  product: Product;
  variant: ProductVariant;
  quantity: number;
  onClose: () => void;
}

export const OutsideDeliveryRequestDialog: React.FC<Props> = ({
  product,
  variant,
  quantity,
  onClose,
}) => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const { showToast } = useToast();
  const [name, setName] = useState(user?.name || '');
  const [phone, setPhone] = useState(user?.phone || '');
  const [street, setStreet] = useState('');
  const [city, setCity] = useState('');
  const [state, setState] = useState('');
  const [pincode, setPincode] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!user) {
      navigate('/login', { state: { from: location.pathname }, replace: true });
    }
  }, [location.pathname, navigate, user]);

  if (!user) return null;

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true); setError('');
    try {
      const result = await deliveryRequestApi.create({
        productId: product.id,
        variantId: variant.id,
        quantity,
        address: {
          name: name.trim(),
          phone: phone.trim(),
          street: street.trim(),
          city: city.trim(),
          state: state.trim(),
          pincode: pincode.trim(),
        },
      });
      showToast(
        result.idempotent
          ? 'This delivery request is already active. Opening your requests.'
          : 'Delivery request sent. Vibe4You will confirm the delivery charge before payment.',
        'success',
      );
      navigate('/delivery-requests');
    } catch (cause) {
      const message = cause instanceof ApiError ? cause.message : 'Delivery request could not be submitted.';
      setError(message);
      showToast(message, 'error');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[80] flex items-end justify-center bg-black/60 p-0 sm:items-center sm:p-4" role="presentation">
      <div role="dialog" aria-modal="true" aria-labelledby="outside-delivery-title" className="max-h-[95vh] w-full max-w-xl overflow-y-auto rounded-t-3xl bg-white p-5 shadow-2xl sm:rounded-3xl sm:p-6 dark:bg-neutral-900">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-[11px] font-black uppercase tracking-widest text-violet-600">Outside Neemuch (458441)</p>
            <h2 id="outside-delivery-title" className="text-xl font-black">Request product delivery</h2>
          </div>
          <button type="button" onClick={onClose} aria-label="Close delivery request" className="rounded-xl border p-2"><X className="h-4 w-4" /></button>
        </div>
        <div className="mt-4 rounded-2xl border border-violet-200 bg-violet-50 p-4 text-xs dark:border-violet-900 dark:bg-violet-950/20">
          <div className="flex items-center gap-2 font-black"><ShieldCheck className="h-4 w-4" /> You do not pay now.</div>
          <p className="mt-1 text-neutral-600 dark:text-neutral-300">Vibe4You will check courier/delivery cost for your address. After we confirm the charge, a secure payment request for product + delivery will appear in your account.</p>
        </div>

        <div className="mt-4 rounded-2xl bg-neutral-50 p-4 text-xs dark:bg-neutral-800/70">
          <strong className="block">{product.name}</strong>
          <span className="text-neutral-500">{variant.size}{variant.colourName ? ` · ${variant.colourName}` : ''} · Qty {quantity}</span>
          <span className="mt-1 block font-black">Product subtotal: ₹{(variant.price ?? product.price) * quantity}</span>
        </div>

        <form onSubmit={submit} className="mt-5 grid gap-4 sm:grid-cols-2">
          <label className="text-xs font-bold">Full name<input required minLength={2} maxLength={80} autoComplete="name" value={name} onChange={event => setName(event.target.value)} className="mt-1 w-full rounded-xl border p-3 dark:bg-neutral-800" /></label>
          <label className="text-xs font-bold">Phone number<input required minLength={10} maxLength={16} autoComplete="tel" inputMode="tel" value={phone} onChange={event => setPhone(event.target.value)} className="mt-1 w-full rounded-xl border p-3 dark:bg-neutral-800" /></label>
          <label className="text-xs font-bold sm:col-span-2">Street address & landmark<input required minLength={5} maxLength={200} autoComplete="street-address" value={street} onChange={event => setStreet(event.target.value)} className="mt-1 w-full rounded-xl border p-3 dark:bg-neutral-800" /></label>
          <label className="text-xs font-bold">City<input required minLength={2} maxLength={80} autoComplete="address-level2" value={city} onChange={event => setCity(event.target.value)} className="mt-1 w-full rounded-xl border p-3 dark:bg-neutral-800" /></label>
          <label className="text-xs font-bold">State<input required minLength={2} maxLength={80} autoComplete="address-level1" value={state} onChange={event => setState(event.target.value)} className="mt-1 w-full rounded-xl border p-3 dark:bg-neutral-800" /></label>
          <label className="text-xs font-bold sm:col-span-2">Pincode<input required pattern="[0-9]{6}" inputMode="numeric" maxLength={6} autoComplete="postal-code" value={pincode} onChange={event => setPincode(event.target.value.replace(/\D/g, '').slice(0, 6))} className="mt-1 w-full rounded-xl border p-3 dark:bg-neutral-800" /><span className="mt-1 block font-normal text-neutral-500">For 458441, use normal Vibe4You checkout instead.</span></label>
          {error && <p role="alert" className="sm:col-span-2 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}
          <div className="sm:col-span-2 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <button type="button" onClick={onClose} disabled={busy} className="rounded-xl border px-4 py-3 text-xs font-bold">Cancel</button>
            <button disabled={busy} className="inline-flex items-center justify-center gap-2 rounded-xl bg-violet-600 px-5 py-3 text-xs font-black text-white disabled:opacity-60"><Truck className="h-4 w-4" />{busy ? 'Sending request…' : 'Request Delivery Quote'}</button>
          </div>
        </form>
      </div>
    </div>
  );
};
