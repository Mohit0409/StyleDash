import React, { useEffect, useState } from 'react';
import { ImagePlus, Save, Store, Trash2 } from 'lucide-react';
import { ApiError } from '../services/apiClient';
import {
  type ShopApplication,
  vendorApplicationApi,
} from '../services/businessApi';
import { blobToBase64, prepareProductImage } from '../utils/productImage';

interface StoreBrandingProps {
  application: ShopApplication;
  onChange: (application: ShopApplication) => void;
}

const errorMessage = (cause: unknown, fallback: string) =>
  cause instanceof ApiError || cause instanceof Error ? cause.message : fallback;

export const StoreBranding: React.FC<StoreBrandingProps> = ({ application, onChange }) => {
  const [bannerImage, setBannerImage] = useState<string | null>(application.bannerImage || null);
  const [logoImage, setLogoImage] = useState<string | null>(application.logoImage || null);
  const [uploading, setUploading] = useState<'banner' | 'logo' | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  useEffect(() => {
    setBannerImage(application.bannerImage || null);
    setLogoImage(application.logoImage || null);
  }, [application.bannerImage, application.logoImage]);

  const upload = async (kind: 'banner' | 'logo', files: FileList | null) => {
    const file = files?.[0];
    if (!file) return;
    setUploading(kind);
    setError('');
    setMessage('');
    try {
      const prepared = await prepareProductImage(file);
      const uploaded = await vendorApplicationApi.uploadBrandingImage({
        fileName: prepared.fileName,
        contentType: prepared.blob.type || 'image/webp',
        dataBase64: await blobToBase64(prepared.blob),
      });
      if (kind === 'banner') setBannerImage(uploaded.url);
      else setLogoImage(uploaded.url);
      setMessage(`${kind === 'banner' ? 'Store cover' : 'Store logo'} prepared. Save branding to publish it.`);
    } catch (cause) {
      setError(errorMessage(cause, 'The store image could not be uploaded.'));
    } finally {
      setUploading(null);
    }
  };

  const save = async () => {
    setSaving(true);
    setError('');
    setMessage('');
    try {
      const updated = await vendorApplicationApi.updateBranding({ bannerImage, logoImage });
      onChange(updated);
      setMessage('Store branding saved. Your public storefront now uses these images.');
    } catch (cause) {
      setError(errorMessage(cause, 'Store branding could not be saved.'));
    } finally {
      setSaving(false);
    }
  };

  const busy = saving || uploading !== null;

  return (
    <section aria-labelledby="store-branding-heading" className="space-y-4 rounded-3xl border border-neutral-200 bg-white p-6 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
      <div>
        <h2 id="store-branding-heading" className="text-xl font-black">Store branding</h2>
        <p className="mt-1 text-xs text-neutral-500">Add your own cover and logo. Until you save them, older stores continue using the existing product-image fallback.</p>
      </div>
      {error && <p role="alert" className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}
      {message && <p role="status" className="rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">{message}</p>}
      <div className="grid gap-5 lg:grid-cols-[1.8fr_1fr]">
        <div className="space-y-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h3 className="text-sm font-black">Store cover</h3>
              <p className="text-[11px] text-neutral-500">Wide banner shown on your storefront and store cards.</p>
            </div>
            {bannerImage && <button type="button" disabled={busy} onClick={() => { setBannerImage(null); setMessage('Store cover removed from this draft. Save branding to apply.'); }} className="inline-flex items-center gap-1 rounded-lg border px-2.5 py-1.5 text-[11px] font-bold text-red-600 disabled:opacity-50"><Trash2 className="w-3.5" /> Remove</button>}
          </div>
          <div className="relative aspect-[21/9] overflow-hidden rounded-2xl border bg-neutral-100 dark:border-neutral-700 dark:bg-neutral-800">
            {bannerImage ? <img src={bannerImage} alt="Store cover preview" className="h-full w-full object-cover" /> : <div className="flex h-full items-center justify-center"><Store className="h-12 w-12 text-neutral-400" /></div>}
          </div>
          <label className="inline-flex cursor-pointer items-center gap-2 rounded-xl border px-4 py-2.5 text-xs font-bold">
            <ImagePlus className="w-4" /> {uploading === 'banner' ? 'Optimizing cover…' : bannerImage ? 'Replace cover' : 'Upload cover'}
            <input aria-label="Upload store cover image" type="file" accept="image/jpeg,image/png,image/webp" disabled={busy} onChange={event => { void upload('banner', event.target.files); event.currentTarget.value = ''; }} className="sr-only" />
          </label>
        </div>
        <div className="space-y-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h3 className="text-sm font-black">Store logo</h3>
              <p className="text-[11px] text-neutral-500">Square logo used in search and store identity.</p>
            </div>
            {logoImage && <button type="button" disabled={busy} onClick={() => { setLogoImage(null); setMessage('Store logo removed from this draft. Save branding to apply.'); }} className="inline-flex items-center gap-1 rounded-lg border px-2.5 py-1.5 text-[11px] font-bold text-red-600 disabled:opacity-50"><Trash2 className="w-3.5" /> Remove</button>}
          </div>
          <div className="mx-auto aspect-square w-full max-w-[220px] overflow-hidden rounded-3xl border bg-neutral-100 dark:border-neutral-700 dark:bg-neutral-800">
            {logoImage ? <img src={logoImage} alt="Store logo preview" className="h-full w-full object-cover" /> : <div className="flex h-full items-center justify-center"><Store className="h-12 w-12 text-neutral-400" /></div>}
          </div>
          <label className="inline-flex cursor-pointer items-center gap-2 rounded-xl border px-4 py-2.5 text-xs font-bold">
            <ImagePlus className="w-4" /> {uploading === 'logo' ? 'Optimizing logo…' : logoImage ? 'Replace logo' : 'Upload logo'}
            <input aria-label="Upload store logo image" type="file" accept="image/jpeg,image/png,image/webp" disabled={busy} onChange={event => { void upload('logo', event.target.files); event.currentTarget.value = ''; }} className="sr-only" />
          </label>
        </div>
      </div>
      <p className="text-[11px] text-neutral-500">JPEG, PNG or WebP. Images are resized to a maximum of 1600 px and compressed before upload so branding does not slow the storefront.</p>
      <div className="flex justify-end">
        <button type="button" onClick={() => void save()} disabled={busy} className="inline-flex items-center gap-2 rounded-xl bg-neutral-950 px-5 py-2.5 text-xs font-black text-white disabled:opacity-60 dark:bg-lime-400 dark:text-neutral-950"><Save className="w-4" /> {saving ? 'Saving…' : 'Save Store Branding'}</button>
      </div>
    </section>
  );
};
