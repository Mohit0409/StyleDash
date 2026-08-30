import React, { useEffect, useState } from 'react';
import { AlertTriangle, Boxes, Edit3, PackageMinus, PackagePlus, Send } from 'lucide-react';
import { ApiError } from '../services/apiClient';
import { blobToBase64, prepareProductImage } from '../utils/productImage';
import {
  type SellerProduct,
  type SellerProductChangeDraft,
  type SellerProductChangeRequest,
  type SellerProductDraft,
  shopProductApi,
} from '../services/businessApi';

const CATEGORIES = ['Clothing & Fashion', 'Footwear', 'Electronics', 'Home & Living', 'General Store'];
const DEPARTMENTS = ['men', 'women', 'kids', 'unisex', 'footwear', 'accessories'] as const;
const INTERNAL_PRODUCT_IMAGE = /^\/media\/product-images\/[0-9a-f]{32}\.(?:webp|jpg|png)$/;

const validExternalImageLink = (value: string) => {
  try {
    const url = new URL(value);
    return url.protocol === 'https:' && !/\.html?$/i.test(url.pathname);
  } catch { return false; }
};

const validImageReference = (value: string) =>
  INTERNAL_PRODUCT_IMAGE.test(value) || validExternalImageLink(value);

interface ProductFormState {
  name: string;
  description: string;
  brand: string;
  department: SellerProductDraft['department'];
  category: string;
  price: string;
  originalPrice: string;
  variants: Array<{ size: string; inventory: string }>;
  colourName: string;
  colourHex: string;
  imageMode: 'links' | 'upload';
  imageUrls: string;
  uploadedImageUrls: string[];
  material: string;
}

const EMPTY_FORM: ProductFormState = {
  name: '', description: '', brand: '', department: 'unisex', category: CATEGORIES[0],
  price: '', originalPrice: '', variants: [{ size: '', inventory: '0' }], colourName: '', colourHex: '',
  imageMode: 'links', imageUrls: '', uploadedImageUrls: [], material: '',
};

const toForm = (product: SellerProduct): ProductFormState => {
  const uploadedImages = product.imageUrls.filter(value => INTERNAL_PRODUCT_IMAGE.test(value));
  const linkedImages = product.imageUrls.filter(value => !INTERNAL_PRODUCT_IMAGE.test(value));
  const imageMode: ProductFormState['imageMode'] = uploadedImages.length > 0 ? 'upload' : 'links';
  return {
    name: product.name,
    description: product.description,
    brand: product.brand || '',
    department: product.department,
    category: product.category,
    price: (product.pricePaise / 100).toFixed(2),
    originalPrice: (product.originalPricePaise / 100).toFixed(2),
    variants: product.variants?.length
      ? product.variants.map(variant => ({ size: variant.size, inventory: String(variant.inventory) }))
      : [{ size: product.size, inventory: String(product.inventory) }],
    colourName: product.colourName,
    colourHex: product.colourHex || '',
    imageMode,
    imageUrls: linkedImages.join('\n'),
    uploadedImageUrls: imageMode === 'upload' ? product.imageUrls : [],
    material: product.attributes.material || '',
  };
};

const toPayload = (form: ProductFormState): SellerProductDraft => {
  const pricePaise = Math.round(Number(form.price) * 100);
  const originalPricePaise = form.originalPrice
    ? Math.round(Number(form.originalPrice) * 100)
    : pricePaise;
  if (
    !Number.isSafeInteger(pricePaise) || pricePaise < 100
    || !Number.isSafeInteger(originalPricePaise) || originalPricePaise < pricePaise
  ) {
    throw new Error('Enter valid price values.');
  }
  const variants = form.variants.map(variant => ({
    size: variant.size.trim(),
    inventory: Number(variant.inventory),
  }));
  const normalizedSizes = variants.map(variant => variant.size.toLocaleLowerCase());
  if (
    variants.length < 1 || variants.length > 20
    || variants.some(variant => !variant.size || variant.size.length > 40)
    || variants.some(variant => !Number.isSafeInteger(variant.inventory) || variant.inventory < 0 || variant.inventory > 100_000)
    || new Set(normalizedSizes).size !== variants.length
    || variants.reduce((total, variant) => total + variant.inventory, 0) > 100_000
  ) {
    throw new Error('Add unique sizes with valid whole-number stock values.');
  }
  const imageUrls = form.imageMode === 'links'
    ? form.imageUrls.split(/\r?\n/).map(value => value.trim()).filter(Boolean)
    : form.uploadedImageUrls;
  if (form.imageMode === 'links') {
    if (imageUrls.length < 1 || imageUrls.length > 8 || imageUrls.some(value => !validExternalImageLink(value))) {
      throw new Error('Add 1-8 direct HTTPS image links. Webpage (.html) links are not images.');
    }
  } else if (imageUrls.length < 1 || imageUrls.length > 8 || imageUrls.some(value => !validImageReference(value))) {
    throw new Error('Upload 1-8 product images.');
  }
  return {
    name: form.name.trim(),
    description: form.description.trim(),
    brand: form.brand.trim() || undefined,
    department: form.department,
    category: form.category,
    pricePaise,
    originalPricePaise,
    variants,
    colourName: form.colourName.trim(),
    colourHex: form.colourHex.trim() || undefined,
    imageUrls,
    attributes: form.material.trim() ? { material: form.material.trim() } : {},
  };
};

const toChangePayload = (payload: SellerProductDraft): SellerProductChangeDraft => ({
  name: payload.name,
  description: payload.description,
  brand: payload.brand,
  department: payload.department,
  category: payload.category,
  pricePaise: payload.pricePaise,
  originalPricePaise: payload.originalPricePaise,
  variants: payload.variants,
  colourName: payload.colourName,
  colourHex: payload.colourHex,
  imageUrls: payload.imageUrls,
  attributes: payload.attributes,
});

const messageForError = (cause: unknown, fallback: string) =>
  cause instanceof ApiError || cause instanceof Error ? cause.message : fallback;

export const SellerProducts: React.FC = () => {
  const [products, setProducts] = useState<SellerProduct[]>([]);
  const [requests, setRequests] = useState<SellerProductChangeRequest[]>([]);
  const [form, setForm] = useState<ProductFormState>(EMPTY_FORM);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formMode, setFormMode] = useState<'draft' | 'change'>('draft');
  const [changeBaseVariantCount, setChangeBaseVariantCount] = useState(0);
  const [formOpen, setFormOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [uploadBusy, setUploadBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [stockEdit, setStockEdit] = useState<{ productId: string; variantId: string; size: string; value: string } | null>(null);
  const [unpublishConfirmId, setUnpublishConfirmId] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    Promise.all([shopProductApi.mine(), shopProductApi.requests()])
      .then(([productResult, requestResult]) => {
        if (active) {
          setProducts(productResult);
          setRequests(requestResult);
        }
      })
      .catch(cause => { if (active) setError(messageForError(cause, 'Seller catalogue data could not be loaded.')); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  const updateForm = (field: keyof ProductFormState, value: string) => {
    setForm(current => ({ ...current, [field]: value }));
  };

  const updateVariant = (index: number, field: 'size' | 'inventory', value: string) => {
    setForm(current => ({
      ...current,
      variants: current.variants.map((variant, position) => position === index ? { ...variant, [field]: value } : variant),
    }));
  };

  const addVariant = () => setForm(current => ({
    ...current,
    variants: [...current.variants, { size: '', inventory: '0' }],
  }));

  const removeVariant = (index: number) => {
    if (formMode === 'change' && index < changeBaseVariantCount) return;
    setForm(current => ({
      ...current,
      variants: current.variants.filter((_, position) => position !== index),
    }));
  };

  const openNew = () => {
    setEditingId(null);
    setFormMode('draft');
    setChangeBaseVariantCount(0);
    setForm(EMPTY_FORM);
    setFormOpen(true);
    setError('');
    setMessage('');
  };

  const openEdit = (product: SellerProduct) => {
    setEditingId(product.id);
    setFormMode('draft');
    setChangeBaseVariantCount(0);
    setForm(toForm(product));
    setFormOpen(true);
    setError('');
    setMessage('');
  };

  const openChangeRequest = (product: SellerProduct) => {
    setEditingId(product.id);
    setFormMode('change');
    setChangeBaseVariantCount(product.variants.length);
    setForm(toForm(product));
    setFormOpen(true);
    setError('');
    setMessage('');
  };

  const uploadImages = async (files: FileList | null) => {
    if (!files?.length) return;
    const existing = form.uploadedImageUrls;
    if (existing.length + files.length > 8) {
      setError('A product can have at most 8 images.');
      return;
    }
    setUploadBusy(true);
    setError('');
    setMessage('');
    try {
      const uploaded: string[] = [];
      for (const file of Array.from(files)) {
        const prepared = await prepareProductImage(file);
        const image = await shopProductApi.uploadImage({
          fileName: prepared.fileName,
          contentType: prepared.blob.type || 'image/webp',
          dataBase64: await blobToBase64(prepared.blob),
        });
        uploaded.push(image.url);
      }
      setForm(current => ({
        ...current,
        uploadedImageUrls: [...current.uploadedImageUrls, ...uploaded],
      }));
      setMessage(`${uploaded.length} image${uploaded.length === 1 ? '' : 's'} optimized and uploaded.`);
    } catch (cause) {
      setError(messageForError(cause, 'The image could not be optimized or uploaded.'));
    } finally {
      setUploadBusy(false);
    }
  };

  const setImageMode = (imageMode: ProductFormState['imageMode']) => {
    setForm(current => ({ ...current, imageMode }));
    setError('');
    setMessage('');
  };

  const removeUploadedImage = (index: number) => {
    setForm(current => ({
      ...current,
      uploadedImageUrls: current.uploadedImageUrls.filter((_, position) => position !== index),
    }));
  };

  const saveProduct = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError('');
    setMessage('');
    try {
      const payload = toPayload(form);
      if (formMode === 'change' && editingId) {
        const request = await shopProductApi.requestEdit(editingId, toChangePayload(payload));
        setRequests(current => [request, ...current]);
        setMessage('Listing changes submitted for administrator review. The current live listing stays unchanged until approval.');
      } else {
        const saved = editingId
          ? await shopProductApi.updateDraft(editingId, payload)
          : await shopProductApi.createDraft(payload);
        setProducts(current => [saved, ...current.filter(product => product.id !== saved.id)]);
        setMessage('Product draft saved. It is not public until a private administrator publishes it.');
      }
      setFormOpen(false);
      setEditingId(null);
      setFormMode('draft');
      setChangeBaseVariantCount(0);
      setForm(EMPTY_FORM);
    } catch (cause) {
      setError(messageForError(cause, formMode === 'change' ? 'The listing change request could not be submitted.' : 'The product draft could not be saved.'));
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

  const updateStock = async (product: SellerProduct, variant: SellerProduct['variants'][number], raw: string) => {
    const stock = Number(raw);
    if (!Number.isSafeInteger(stock) || stock < 0 || stock > 100_000) {
      setError('Enter a whole-number stock value from 0 to 100000.');
      return;
    }
    setBusy(true);
    setError('');
    setMessage('');
    try {
      const updated = await shopProductApi.setStock(product.id, stock, variant.id);
      setProducts(current => current.map(item => {
        if (item.id !== product.id) return item;
        const variants = item.variants.map(candidate => candidate.id === updated.variantId ? { ...candidate, inventory: updated.stock } : candidate);
        return { ...item, variants, inventory: variants.reduce((total, candidate) => total + candidate.inventory, 0) };
      }));
      setStockEdit(null);
      setMessage(`Stock for size ${variant.size} updated to ${updated.stock}.`);
    } catch (cause) {
      setError(messageForError(cause, 'Live stock could not be updated.'));
    } finally {
      setBusy(false);
    }
  };

  const requestUnpublish = async (product: SellerProduct) => {
    setBusy(true);
    setError('');
    setMessage('');
    try {
      const request = await shopProductApi.requestUnpublish(product.id);
      setRequests(current => [request, ...current]);
      setUnpublishConfirmId(null);
      setMessage('Unpublish request submitted. The product remains live until administrator approval.');
    } catch (cause) {
      setError(messageForError(cause, 'The unpublish request could not be submitted.'));
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
          <h3 className="font-black">{formMode === 'change' ? 'Request Listing Changes' : editingId ? 'Edit Product Draft' : 'Create Product Draft'}</h3>
          <div className="grid gap-3 text-xs sm:grid-cols-2">
            <label className="font-bold">Product name<input required minLength={2} maxLength={140} value={form.name} onChange={event => updateForm('name', event.target.value)} className="mt-1 w-full rounded-xl border p-3 dark:bg-neutral-800" /></label>
            <label className="font-bold">Brand <span className="font-normal text-neutral-500">(optional)</span><input maxLength={100} value={form.brand} onChange={event => updateForm('brand', event.target.value)} className="mt-1 w-full rounded-xl border p-3 dark:bg-neutral-800" /></label>
            <label className="font-bold">Department<select value={form.department} onChange={event => updateForm('department', event.target.value)} className="mt-1 w-full rounded-xl border p-3 dark:bg-neutral-800">{DEPARTMENTS.map(value => <option key={value} value={value}>{value}</option>)}</select></label>
            <label className="font-bold">Category<select value={form.category} onChange={event => updateForm('category', event.target.value)} className="mt-1 w-full rounded-xl border p-3 dark:bg-neutral-800">{CATEGORIES.map(value => <option key={value} value={value}>{value}</option>)}</select></label>
            <label className="font-bold">Price (INR)<input required type="number" min="1" step="0.01" value={form.price} onChange={event => updateForm('price', event.target.value)} className="mt-1 w-full rounded-xl border p-3 dark:bg-neutral-800" /></label>
            <label className="font-bold">Original price (INR)<input type="number" min="1" step="0.01" value={form.originalPrice} onChange={event => updateForm('originalPrice', event.target.value)} className="mt-1 w-full rounded-xl border p-3 dark:bg-neutral-800" /></label>
            <div className="sm:col-span-2 space-y-2">
              <div className="flex items-center justify-between gap-3">
                <span className="font-bold">{formMode === 'change' ? 'Sizes and inventory' : 'Sizes and stock'}</span>
                <button type="button" onClick={addVariant} disabled={form.variants.length >= 20} className="rounded-lg border px-3 py-1.5 font-bold disabled:opacity-50">+ Add size</button>
              </div>
              <p className="text-neutral-500">{formMode === 'change'
                ? 'Rename an existing size or add a new size. Existing live stock stays controlled by the Stock buttons; a newly added size can set its starting stock. Existing published size rows cannot be removed.'
                : 'Add one row per size. Stock is tracked separately for every size.'}</p>
              <div className="space-y-2">
                {form.variants.map((variant, index) => {
                  const existingPublishedVariant = formMode === 'change' && index < changeBaseVariantCount;
                  return <div key={index} className="grid grid-cols-[1fr_1fr_auto] gap-2">
                    <input aria-label={`Size ${index + 1}`} required maxLength={40} value={variant.size} onChange={event => updateVariant(index, 'size', event.target.value)} placeholder="Size, e.g. S or XL" className="w-full rounded-xl border p-3 dark:bg-neutral-800" />
                    <input aria-label={`Stock for size ${variant.size || index + 1}`} title={existingPublishedVariant ? 'Use the Stock button on the product card to change live stock.' : undefined} required type="number" min="0" max="100000" step="1" readOnly={existingPublishedVariant} value={variant.inventory} onChange={event => { if (!existingPublishedVariant) updateVariant(index, 'inventory', event.target.value); }} placeholder="Stock" className="w-full rounded-xl border p-3 read-only:bg-neutral-100 read-only:text-neutral-500 dark:bg-neutral-800 dark:read-only:bg-neutral-900" />
                    {(!existingPublishedVariant)
                      ? <button type="button" disabled={formMode === 'draft' && form.variants.length === 1} onClick={() => removeVariant(index)} className="rounded-xl border px-3 font-bold text-red-600 disabled:opacity-30" aria-label={`Remove size ${variant.size || index + 1}`}>?</button>
                      : <span aria-hidden="true" className="w-9" />}
                  </div>;
                })}
              </div>
            </div>
            <label className="font-bold">Colour name<input required minLength={1} maxLength={80} value={form.colourName} onChange={event => updateForm('colourName', event.target.value)} className="mt-1 w-full rounded-xl border p-3 dark:bg-neutral-800" /></label>
            <label className="font-bold">Colour hex <span className="font-normal text-neutral-500">(optional)</span><input pattern="#[0-9A-Fa-f]{6}" placeholder="#000000" value={form.colourHex} onChange={event => updateForm('colourHex', event.target.value)} className="mt-1 w-full rounded-xl border p-3 dark:bg-neutral-800" /></label>
            <label className="font-bold">Material <span className="font-normal text-neutral-500">(optional)</span><input maxLength={200} value={form.material} onChange={event => updateForm('material', event.target.value)} className="mt-1 w-full rounded-xl border p-3 dark:bg-neutral-800" /></label>
            <label className="font-bold sm:col-span-2">Description<textarea required minLength={10} maxLength={2000} rows={3} value={form.description} onChange={event => updateForm('description', event.target.value)} className="mt-1 w-full rounded-xl border p-3 dark:bg-neutral-800" /></label>
            <fieldset className="sm:col-span-2 space-y-3 rounded-xl border border-neutral-200 p-3 dark:border-neutral-700">
              <legend className="px-1 font-bold">Product images</legend>
              <p className="text-[11px] text-neutral-500">Choose one method: use direct image links or upload product images. Only the selected method is submitted.</p>
              <div className="grid grid-cols-2 gap-2" role="radiogroup" aria-label="Product image source">
                <button type="button" role="radio" aria-checked={form.imageMode === 'links'} onClick={() => setImageMode('links')} className={`rounded-xl border px-3 py-2.5 font-bold ${form.imageMode === 'links' ? 'border-neutral-950 bg-neutral-950 text-white dark:border-lime-400 dark:bg-lime-400 dark:text-neutral-950' : ''}`}>Image link</button>
                <button type="button" role="radio" aria-checked={form.imageMode === 'upload'} onClick={() => setImageMode('upload')} className={`rounded-xl border px-3 py-2.5 font-bold ${form.imageMode === 'upload' ? 'border-neutral-950 bg-neutral-950 text-white dark:border-lime-400 dark:bg-lime-400 dark:text-neutral-950' : ''}`}>Image upload</button>
              </div>
              {form.imageMode === 'links' ? (
                <label className="block font-bold">Direct HTTPS image links <span className="font-normal text-neutral-500">(one per line, 1-8)</span><textarea aria-label="HTTPS image URLs" rows={3} value={form.imageUrls} onChange={event => updateForm('imageUrls', event.target.value)} placeholder="https://example.com/product.jpg" className="mt-1 w-full rounded-xl border p-3 dark:bg-neutral-800" /><span className="mt-1 block text-[11px] font-normal text-neutral-500">Each link must open the image itself, not a webpage such as a .html product/gallery page.</span></label>
              ) : (
                <div className="space-y-3">
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <p className="font-bold">Upload product images</p>
                      <p className="text-[11px] text-neutral-500">JPEG, PNG or WebP. Images are resized to max 1600 px and compressed to WebP, targeting about 350 KB with a 500 KB hard limit.</p>
                    </div>
                    <label className="inline-flex cursor-pointer items-center justify-center rounded-xl border px-4 py-2.5 font-bold">
                      {uploadBusy ? 'Optimizing...' : 'Choose images'}
                      <input aria-label="Upload product images" type="file" multiple accept="image/jpeg,image/png,image/webp" disabled={busy || uploadBusy} onChange={event => { void uploadImages(event.target.files); event.currentTarget.value = ''; }} className="sr-only" />
                    </label>
                  </div>
                  {form.uploadedImageUrls.length > 0 ? <div className="flex flex-wrap gap-2">{form.uploadedImageUrls.map((value, index) => <div key={`${value}-${index}`} className="relative"><img src={value} alt={`Uploaded product image ${index + 1} preview`} loading="lazy" className="h-16 w-16 rounded-lg border object-cover" /><button type="button" onClick={() => removeUploadedImage(index)} aria-label={`Remove uploaded image ${index + 1}`} className="absolute -right-1 -top-1 rounded-full border bg-white px-1.5 py-0.5 text-[10px] font-black text-red-600 shadow">x</button></div>)}</div> : <p className="text-[11px] text-neutral-500">No images uploaded yet.</p>}
                </div>
              )}
            </fieldset>
          </div>
          <div className="flex justify-end gap-3">
            <button type="button" onClick={() => setFormOpen(false)} className="rounded-xl border px-4 py-2.5 text-xs font-bold">Cancel</button>
            <button disabled={busy || uploadBusy} className="rounded-xl bg-neutral-950 px-5 py-2.5 text-xs font-bold text-white disabled:opacity-60 dark:bg-lime-400 dark:text-neutral-950">{uploadBusy ? 'Uploading image...' : busy ? 'Saving...' : formMode === 'change' ? 'Submit Listing Changes' : 'Save Product Draft'}</button>
          </div>
        </form>
      )}

      {loading ? <p className="text-sm text-neutral-500">Loading product submissions…</p>
        : products.length === 0 ? <p className="rounded-2xl bg-neutral-50 p-4 text-sm text-neutral-500 dark:bg-neutral-800">No product drafts yet.</p>
          : <div className="space-y-3">{products.map(product => {
            const editable = product.status === 'DRAFT' || product.status === 'REJECTED';
            const latestRequest = requests.find(request => request.productId === product.id);
            const pendingRequest = latestRequest && ['SUBMITTED', 'UNDER_REVIEW'].includes(latestRequest.status) ? latestRequest : null;
            return <article key={product.id} className="rounded-2xl border p-4 dark:border-neutral-700">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <p className="text-xs font-black uppercase tracking-wider text-neutral-500">{product.status.replace('_', ' ')}</p>
                  <h3 className="font-black">{product.name}</h3>
                  <p className="text-xs text-neutral-500">₹{(product.pricePaise / 100).toFixed(2)} · {product.colourName} · Total stock: {product.inventory}</p>
                  <div className="mt-2 flex flex-wrap gap-1.5">{product.variants.map(variant => <span key={variant.id} className="rounded-lg bg-neutral-100 px-2 py-1 text-[11px] font-bold dark:bg-neutral-800">{variant.size}: {variant.inventory}</span>)}</div>
                  {product.status === 'REJECTED' && product.rejectionReason && <p className="mt-2 flex gap-2 text-xs text-amber-700"><AlertTriangle className="w-4 shrink-0" />{product.rejectionReason}</p>}
                  {product.status === 'PUBLISHED' && <p className="mt-2 text-xs font-bold text-emerald-700">Published publicly by the private administrator.</p>}
                  {pendingRequest && <p className="mt-2 rounded-lg bg-amber-50 p-2 text-xs font-bold text-amber-800">{pendingRequest.action.replace('_', ' ')} request {pendingRequest.status.replace('_', ' ').toLowerCase()}. The current listing stays live until approval.</p>}
                  {!pendingRequest && latestRequest?.status === 'REJECTED' && <p className="mt-2 flex gap-2 text-xs text-amber-700"><AlertTriangle className="w-4 shrink-0" />Last {latestRequest.action.toLowerCase()} request rejected: {latestRequest.rejectionReason || 'No reason provided.'}</p>}
                </div>
                <div className="flex flex-wrap gap-2">
                  {editable && <button type="button" disabled={busy} onClick={() => openEdit(product)} className="flex items-center gap-1 rounded-lg border px-3 py-2 text-xs font-bold"><Edit3 className="w-3.5" /> Edit</button>}
                  {product.status === 'DRAFT' && <button type="button" disabled={busy} onClick={() => void submitProduct(product.id)} className="flex items-center gap-1 rounded-lg bg-neutral-950 px-3 py-2 text-xs font-bold text-white disabled:opacity-60 dark:bg-lime-400 dark:text-neutral-950"><Send className="w-3.5" /> Submit</button>}
                  {product.status === 'PUBLISHED' && product.variants.map(variant => <button key={variant.id} type="button" disabled={busy} onClick={() => setStockEdit({ productId: product.id, variantId: variant.id, size: variant.size, value: String(variant.inventory) })} className="flex items-center gap-1 rounded-lg border px-3 py-2 text-xs font-bold"><Boxes className="w-3.5" /> {variant.size} Stock</button>)}
                  {product.status === 'PUBLISHED' && !pendingRequest && <button type="button" disabled={busy} onClick={() => openChangeRequest(product)} className="flex items-center gap-1 rounded-lg border px-3 py-2 text-xs font-bold"><Edit3 className="w-3.5" /> Edit Listing</button>}
                  {product.status === 'PUBLISHED' && !pendingRequest && <button type="button" disabled={busy} onClick={() => setUnpublishConfirmId(product.id)} className="flex items-center gap-1 rounded-lg border border-amber-300 px-3 py-2 text-xs font-bold text-amber-800"><PackageMinus className="w-3.5" /> Request Unpublish</button>}
                </div>
              </div>
              {stockEdit?.productId === product.id && (() => {
                const variant = product.variants.find(item => item.id === stockEdit.variantId);
                if (!variant) return null;
                return <div className="mt-3 flex flex-wrap items-end gap-2 rounded-xl bg-neutral-50 p-3 dark:bg-neutral-800">
                  <label className="text-xs font-bold">Stock for size {stockEdit.size}<input aria-label={`Stock for size ${stockEdit.size}`} type="number" min="0" max="100000" step="1" value={stockEdit.value} onChange={event => setStockEdit(current => current ? { ...current, value: event.target.value } : current)} className="mt-1 block w-36 rounded-lg border p-2 dark:bg-neutral-900" /></label>
                  <button type="button" disabled={busy} onClick={() => void updateStock(product, variant, stockEdit.value)} className="rounded-lg bg-neutral-950 px-3 py-2 text-xs font-bold text-white disabled:opacity-60 dark:bg-lime-400 dark:text-neutral-950">Save stock</button>
                  <button type="button" disabled={busy} onClick={() => setStockEdit(null)} className="rounded-lg border px-3 py-2 text-xs font-bold">Cancel</button>
                </div>;
              })()}
              {unpublishConfirmId === product.id && <div role="group" aria-label={`Confirm unpublish request for ${product.name}`} className="mt-3 rounded-xl border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900">
                <p className="font-bold">Request unpublishing {product.name}? The listing stays live until administrator approval.</p>
                <div className="mt-2 flex gap-2"><button type="button" disabled={busy} onClick={() => void requestUnpublish(product)} className="rounded-lg bg-amber-700 px-3 py-2 font-bold text-white disabled:opacity-60">Confirm unpublish request</button><button type="button" disabled={busy} onClick={() => setUnpublishConfirmId(null)} className="rounded-lg border border-amber-400 px-3 py-2 font-bold">Cancel</button></div>
              </div>}
            </article>;
          })}</div>}
    </section>
  );
};
