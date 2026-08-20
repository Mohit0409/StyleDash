import React, { useEffect, useState } from 'react';
import { AlertTriangle, Edit3, PackagePlus, Send } from 'lucide-react';
import { ApiError } from '../services/apiClient';
import {
  type SellerProduct,
  type SellerProductDraft,
  shopProductApi,
} from '../services/businessApi';

const CATEGORIES = ['Clothing & Fashion', 'Footwear', 'Electronics', 'Home & Living', 'General Store'];
const DEPARTMENTS = ['men', 'women', 'kids', 'unisex', 'footwear', 'accessories'] as const;

interface ProductFormState {
  name: string;
  description: string;
  brand: string;
  department: SellerProductDraft['department'];
  category: string;
  price: string;
  originalPrice: string;
  inventory: string;
  size: string;
  colourName: string;
  colourHex: string;
  imageUrls: string;
  material: string;
}

const EMPTY_FORM: ProductFormState = {
  name: '', description: '', brand: '', department: 'unisex', category: CATEGORIES[0],
  price: '', originalPrice: '', inventory: '0', size: '', colourName: '', colourHex: '',
  imageUrls: '', material: '',
};

const toForm = (product: SellerProduct): ProductFormState => ({
  name: product.name,
  description: product.description,
  brand: product.brand || '',
  department: product.department,
  category: product.category,
  price: (product.pricePaise / 100).toFixed(2),
  originalPrice: (product.originalPricePaise / 100).toFixed(2),
  inventory: String(product.inventory),
  size: product.size,
  colourName: product.colourName,
  colourHex: product.colourHex || '',
  imageUrls: product.imageUrls.join('\n'),
  material: product.attributes.material || '',
});

const toPayload = (form: ProductFormState): SellerProductDraft => {
  const pricePaise = Math.round(Number(form.price) * 100);
  const originalPricePaise = form.originalPrice
    ? Math.round(Number(form.originalPrice) * 100)
    : pricePaise;
  const inventory = Number(form.inventory);
  if (
    !Number.isSafeInteger(pricePaise) || pricePaise < 100
    || !Number.isSafeInteger(originalPricePaise) || originalPricePaise < pricePaise
    || !Number.isSafeInteger(inventory) || inventory < 0 || inventory > 100_000
  ) {
    throw new Error('Enter valid price and inventory values.');
  }
  const imageUrls = form.imageUrls.split(/\r?\n/).map(value => value.trim()).filter(Boolean);
  if (imageUrls.length < 1 || imageUrls.length > 8 || imageUrls.some(value => {
    try { return new URL(value).protocol !== 'https:'; } catch { return true; }
  })) {
    throw new Error('Enter between 1 and 8 valid HTTPS image URLs.');
  }
  return {
    name: form.name.trim(),
    description: form.description.trim(),
    brand: form.brand.trim() || undefined,
    department: form.department,
    category: form.category,
    pricePaise,
    originalPricePaise,
    inventory,
    size: form.size.trim(),
    colourName: form.colourName.trim(),
    colourHex: form.colourHex.trim() || undefined,
    imageUrls,
    attributes: form.material.trim() ? { material: form.material.trim() } : {},
  };
};

const messageForError = (cause: unknown, fallback: string) =>
  cause instanceof ApiError || cause instanceof Error ? cause.message : fallback;

export const SellerProducts: React.FC = () => {
  const [products, setProducts] = useState<SellerProduct[]>([]);
  const [form, setForm] = useState<ProductFormState>(EMPTY_FORM);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  useEffect(() => {
    let active = true;
    shopProductApi.mine()
      .then(result => { if (active) setProducts(result); })
      .catch(cause => { if (active) setError(messageForError(cause, 'Product submissions could not be loaded.')); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  const updateForm = (field: keyof ProductFormState, value: string) => {
    setForm(current => ({ ...current, [field]: value }));
  };

  const openNew = () => {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setFormOpen(true);
    setError('');
    setMessage('');
  };

  const openEdit = (product: SellerProduct) => {
    setEditingId(product.id);
    setForm(toForm(product));
    setFormOpen(true);
    setError('');
    setMessage('');
  };

  const saveProduct = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError('');
    setMessage('');
    try {
      const payload = toPayload(form);
      const saved = editingId
        ? await shopProductApi.updateDraft(editingId, payload)
        : await shopProductApi.createDraft(payload);
      setProducts(current => [saved, ...current.filter(product => product.id !== saved.id)]);
      setFormOpen(false);
      setEditingId(null);
      setForm(EMPTY_FORM);
      setMessage('Product draft saved. It is not public until a private administrator publishes it.');
    } catch (cause) {
      setError(messageForError(cause, 'The product draft could not be saved.'));
    } finally {
      setBusy(false);
    }
  };

  const submitProduct = async (id: string) => {
    setBusy(true);
    setError('');
    setMessage('');
    try {
      const submitted = await shopProductApi.submit(id);
      setProducts(current => current.map(product => product.id === submitted.id ? submitted : product));
      setMessage('Product submitted for private administrator review. It is not publicly listed.');
    } catch (cause) {
      setError(messageForError(cause, 'The product could not be submitted.'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="space-y-5 rounded-3xl border border-neutral-200 bg-white p-6 dark:border-neutral-800 dark:bg-neutral-900" aria-labelledby="seller-products-heading">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 id="seller-products-heading" className="text-xl font-black">Product submissions</h2>
          <p className="mt-1 text-xs text-neutral-500">You can prepare and submit product information. Only the private administrator can publish it.</p>
        </div>
        <button type="button" onClick={openNew} disabled={busy} className="flex items-center justify-center gap-2 rounded-xl bg-neutral-950 px-4 py-2.5 text-xs font-bold text-white disabled:opacity-60 dark:bg-lime-400 dark:text-neutral-950">
          <PackagePlus className="w-4" /> New Product Draft
        </button>
      </div>

      {error && <p role="alert" className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}
      {message && <p role="status" className="rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">{message}</p>}

      {formOpen && (
        <form onSubmit={saveProduct} className="space-y-4 rounded-2xl border p-4 dark:border-neutral-700">
          <h3 className="font-black">{editingId ? 'Edit Product Draft' : 'Create Product Draft'}</h3>
          <div className="grid gap-3 text-xs sm:grid-cols-2">
            <label className="font-bold">Product name<input required minLength={2} maxLength={140} value={form.name} onChange={event => updateForm('name', event.target.value)} className="mt-1 w-full rounded-xl border p-3 dark:bg-neutral-800" /></label>
            <label className="font-bold">Brand <span className="font-normal text-neutral-500">(optional)</span><input maxLength={100} value={form.brand} onChange={event => updateForm('brand', event.target.value)} className="mt-1 w-full rounded-xl border p-3 dark:bg-neutral-800" /></label>
            <label className="font-bold">Department<select value={form.department} onChange={event => updateForm('department', event.target.value)} className="mt-1 w-full rounded-xl border p-3 dark:bg-neutral-800">{DEPARTMENTS.map(value => <option key={value} value={value}>{value}</option>)}</select></label>
            <label className="font-bold">Category<select value={form.category} onChange={event => updateForm('category', event.target.value)} className="mt-1 w-full rounded-xl border p-3 dark:bg-neutral-800">{CATEGORIES.map(value => <option key={value} value={value}>{value}</option>)}</select></label>
            <label className="font-bold">Price (INR)<input required type="number" min="1" step="0.01" value={form.price} onChange={event => updateForm('price', event.target.value)} className="mt-1 w-full rounded-xl border p-3 dark:bg-neutral-800" /></label>
            <label className="font-bold">Original price (INR)<input type="number" min="1" step="0.01" value={form.originalPrice} onChange={event => updateForm('originalPrice', event.target.value)} className="mt-1 w-full rounded-xl border p-3 dark:bg-neutral-800" /></label>
            <label className="font-bold">Inventory<input required type="number" min="0" max="100000" step="1" value={form.inventory} onChange={event => updateForm('inventory', event.target.value)} className="mt-1 w-full rounded-xl border p-3 dark:bg-neutral-800" /></label>
            <label className="font-bold">Size<input required minLength={1} maxLength={40} value={form.size} onChange={event => updateForm('size', event.target.value)} placeholder="M, UK 8, Free Size" className="mt-1 w-full rounded-xl border p-3 dark:bg-neutral-800" /></label>
            <label className="font-bold">Colour name<input required minLength={1} maxLength={80} value={form.colourName} onChange={event => updateForm('colourName', event.target.value)} className="mt-1 w-full rounded-xl border p-3 dark:bg-neutral-800" /></label>
            <label className="font-bold">Colour hex <span className="font-normal text-neutral-500">(optional)</span><input pattern="#[0-9A-Fa-f]{6}" placeholder="#000000" value={form.colourHex} onChange={event => updateForm('colourHex', event.target.value)} className="mt-1 w-full rounded-xl border p-3 dark:bg-neutral-800" /></label>
            <label className="font-bold">Material <span className="font-normal text-neutral-500">(optional)</span><input maxLength={200} value={form.material} onChange={event => updateForm('material', event.target.value)} className="mt-1 w-full rounded-xl border p-3 dark:bg-neutral-800" /></label>
            <label className="font-bold sm:col-span-2">Description<textarea required minLength={10} maxLength={2000} rows={3} value={form.description} onChange={event => updateForm('description', event.target.value)} className="mt-1 w-full rounded-xl border p-3 dark:bg-neutral-800" /></label>
            <label className="font-bold sm:col-span-2">HTTPS image URLs <span className="font-normal text-neutral-500">(one per line, 1–8)</span><textarea required rows={3} value={form.imageUrls} onChange={event => updateForm('imageUrls', event.target.value)} placeholder="https://example.com/product.jpg" className="mt-1 w-full rounded-xl border p-3 dark:bg-neutral-800" /></label>
          </div>
          <div className="flex justify-end gap-3">
            <button type="button" onClick={() => setFormOpen(false)} className="rounded-xl border px-4 py-2.5 text-xs font-bold">Cancel</button>
            <button disabled={busy} className="rounded-xl bg-neutral-950 px-5 py-2.5 text-xs font-bold text-white disabled:opacity-60 dark:bg-lime-400 dark:text-neutral-950">{busy ? 'Saving…' : 'Save Product Draft'}</button>
          </div>
        </form>
      )}

      {loading ? <p className="text-sm text-neutral-500">Loading product submissions…</p>
        : products.length === 0 ? <p className="rounded-2xl bg-neutral-50 p-4 text-sm text-neutral-500 dark:bg-neutral-800">No product drafts yet.</p>
          : <div className="space-y-3">{products.map(product => {
            const editable = product.status === 'DRAFT' || product.status === 'REJECTED';
            return <article key={product.id} className="rounded-2xl border p-4 dark:border-neutral-700">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <p className="text-xs font-black uppercase tracking-wider text-neutral-500">{product.status.replace('_', ' ')}</p>
                  <h3 className="font-black">{product.name}</h3>
                  <p className="text-xs text-neutral-500">₹{(product.pricePaise / 100).toFixed(2)} · {product.size} · {product.colourName}</p>
                  {product.status === 'REJECTED' && product.rejectionReason && <p className="mt-2 flex gap-2 text-xs text-amber-700"><AlertTriangle className="w-4 shrink-0" />{product.rejectionReason}</p>}
                  {product.status === 'PUBLISHED' && <p className="mt-2 text-xs font-bold text-emerald-700">Published publicly by the private administrator.</p>}
                </div>
                <div className="flex gap-2">
                  {editable && <button type="button" disabled={busy} onClick={() => openEdit(product)} className="flex items-center gap-1 rounded-lg border px-3 py-2 text-xs font-bold"><Edit3 className="w-3.5" /> Edit</button>}
                  {product.status === 'DRAFT' && <button type="button" disabled={busy} onClick={() => void submitProduct(product.id)} className="flex items-center gap-1 rounded-lg bg-neutral-950 px-3 py-2 text-xs font-bold text-white disabled:opacity-60 dark:bg-lime-400 dark:text-neutral-950"><Send className="w-3.5" /> Submit</button>}
                </div>
              </div>
            </article>;
          })}</div>}
    </section>
  );
};
