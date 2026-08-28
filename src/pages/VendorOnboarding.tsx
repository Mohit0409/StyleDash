import React, { useEffect, useState } from 'react';
import { AlertTriangle, ArrowRight, CheckCircle2, Clock3, Save, ShieldCheck, Store } from 'lucide-react';
import { SEO } from '../components/SEO';
import {
  type ShopApplication,
  type ShopApplicationDraft,
  type ShopApplicationStatus,
  vendorApplicationApi,
} from '../services/businessApi';
import { ApiError } from '../services/apiClient';
import { useToast } from '../context/ToastContext';
import { useAuth } from '../context/AuthContext';
import { CONFIG } from '../config';
import { SellerProducts } from '../components/SellerProducts';

const CATEGORIES = [
  'Clothing & Fashion',
  'Footwear',
  'Electronics',
  'Home & Living',
  'General Store',
] as const;

const EMPTY_DRAFT: ShopApplicationDraft = {
  shopName: '',
  ownerName: '',
  category: CATEGORIES[0],
  description: '',
  address: '',
  city: CONFIG.SERVICE_CITY,
  state: 'Madhya Pradesh',
  pincode: CONFIG.DEFAULT_PINCODE,
  businessInformation: '',
};

const STATUS_CONTENT: Record<ShopApplicationStatus, { title: string; description: string }> = {
  DRAFT: {
    title: 'Continue Application',
    description: 'Your draft is private. Complete it and submit when you are ready for review.',
  },
  SUBMITTED: {
    title: 'Application Submitted',
    description: 'Your application is waiting for the private Vibe4You review team. It is not publicly active.',
  },
  UNDER_REVIEW: {
    title: 'Under Review',
    description: 'The private Vibe4You team is reviewing your shop application. No action is needed right now.',
  },
  APPROVED: {
    title: 'Shop Approved',
    description: 'Your application is approved. The private team will activate the shop after launch checks are complete.',
  },
  REJECTED: {
    title: 'Changes Requested',
    description: 'Review the reason below, correct the application, and submit it again when ready.',
  },
  ACTIVE: {
    title: 'Shop Active',
    description: 'Your approved shop is active. Products still require private administrator review before publication.',
  },
  SUSPENDED: {
    title: 'Shop Suspended',
    description: 'This shop is currently suspended. Contact Vibe4You support for next steps.',
  },
};

const draftFromApplication = (application: ShopApplication): ShopApplicationDraft => ({
  shopName: application.shopName || '',
  ownerName: application.ownerName || '',
  category: application.category || CATEGORIES[0],
  description: application.description || '',
  address: application.address || '',
  city: application.city || CONFIG.SERVICE_CITY,
  state: application.state || 'Madhya Pradesh',
  pincode: application.pincode || CONFIG.DEFAULT_PINCODE,
  businessInformation: application.businessInformation || '',
});

const ONBOARDING_STAGES = ['Application', 'Submitted', 'Under Review', 'Approved', 'Active', 'Products'] as const;

const stageIndexFor = (status: ShopApplicationStatus) => ({
  DRAFT: 0,
  SUBMITTED: 1,
  UNDER_REVIEW: 2,
  APPROVED: 3,
  REJECTED: 2,
  ACTIVE: 5,
  SUSPENDED: 4,
}[status]);

const errorMessage = (cause: unknown, fallback: string) =>
  cause instanceof ApiError ? cause.message : fallback;

export const VendorOnboarding: React.FC = () => {
  const { showToast } = useToast();
  const { user } = useAuth();
  const [application, setApplication] = useState<ShopApplication | null>(null);
  const [draft, setDraft] = useState<ShopApplicationDraft>(() => ({
    ...EMPTY_DRAFT,
    ownerName: user?.name || '',
  }));
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  useEffect(() => {
    let active = true;
    vendorApplicationApi.mine()
      .then(current => {
        if (!active) return;
        setApplication(current);
        if (current) setDraft(draftFromApplication(current));
        else setDraft(value => ({ ...value, ownerName: value.ownerName || user?.name || '' }));
      })
      .catch(cause => {
        if (active) setError(errorMessage(cause, 'Your shop application could not be loaded.'));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, [user?.name]);

  const setField = (field: keyof ShopApplicationDraft, value: string) => {
    setDraft(current => ({ ...current, [field]: value }));
  };

  const saveDraft = async (announce = true): Promise<ShopApplication | null> => {
    setSaving(true);
    setError('');
    setMessage('');
    try {
      const saved = application
        ? await vendorApplicationApi.updateDraft(draft)
        : await vendorApplicationApi.createDraft(draft);
      setApplication(saved);
      setDraft(draftFromApplication(saved));
      if (announce) {
        setMessage('Draft saved securely to your Vibe4You account.');
        showToast('Shop application draft saved.', 'success');
      }
      return saved;
    } catch (cause) {
      setError(errorMessage(cause, 'Your draft could not be saved.'));
      return null;
    } finally {
      setSaving(false);
    }
  };

  const submitApplication = async (event: React.FormEvent) => {
    event.preventDefault();
    const saved = await saveDraft(false);
    if (!saved) return;
    setSaving(true);
    setError('');
    try {
      const submitted = await vendorApplicationApi.submit();
      setApplication(submitted);
      setMessage('Application submitted for private Vibe4You review.');
      showToast('Application submitted for review.', 'success');
    } catch (cause) {
      setError(errorMessage(cause, 'Your application could not be submitted. The draft remains saved.'));
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div className="min-h-[50vh] flex items-center justify-center text-sm font-bold">Loading your shop applicationâ€¦</div>;
  }

  const editable = !application || application.status === 'DRAFT' || application.status === 'REJECTED';
  const statusContent = application ? STATUS_CONTENT[application.status] : null;
  const registeredContact = application
    ? application.registeredMobile || application.registeredEmail
    : user?.phone || user?.email;

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      <SEO title="List Your Shop - Vibe4You" />

      <div className="text-center space-y-2">
        <div className="w-16 h-16 bg-lime-400 text-neutral-950 rounded-3xl flex items-center justify-center mx-auto shadow-xl">
          <Store className="w-8 h-8" />
        </div>
        <h1 className="text-2xl sm:text-3xl font-black text-neutral-900 dark:text-white">
          {application ? statusContent?.title : 'Start Shop Application'}
        </h1>
        <p className="text-sm text-neutral-500 max-w-xl mx-auto">
          {statusContent?.description || `Apply to list your fashion shop in ${CONFIG.SERVICE_CITY}. Submission never activates a shop automatically.`}
        </p>
      </div>

      {application && (
        <nav aria-label="Shop onboarding progress" className="rounded-3xl border border-neutral-200 bg-white p-4 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
          <ol className="grid grid-cols-3 gap-2 sm:grid-cols-6">
            {ONBOARDING_STAGES.map((stage, index) => {
              const current = stageIndexFor(application.status);
              const complete = index <= current;
              const isCurrent = index === current;
              return (
                <li key={stage} aria-current={isCurrent ? 'step' : undefined} className="text-center">
                  <span className={`mx-auto flex h-8 w-8 items-center justify-center rounded-full text-xs font-black ${complete ? 'bg-lime-400 text-neutral-950' : 'bg-neutral-100 text-neutral-400 dark:bg-neutral-800'}`}>{index + 1}</span>
                  <span className={`mt-1 block text-[10px] font-bold sm:text-xs ${isCurrent ? 'text-neutral-950 dark:text-white' : 'text-neutral-500'}`}>{stage}</span>
                </li>
              );
            })}
          </ol>
          {application.status === 'ACTIVE' && <p className="mt-3 text-center text-xs text-neutral-500">Your shop is active. Add products below and submit them for administrator review.</p>}
        </nav>
      )}

      {error && <p role="alert" className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}
      {message && <p role="status" className="rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">{message}</p>}

      {application && (
        <section aria-label="Application status" className="rounded-3xl border border-neutral-200 bg-white p-6 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
          <div className="flex items-start gap-3">
            {application.status === 'REJECTED' ? <AlertTriangle className="mt-0.5 w-6 text-amber-500" />
              : ['APPROVED', 'ACTIVE'].includes(application.status) ? <CheckCircle2 className="mt-0.5 w-6 text-emerald-500" />
                : <Clock3 className="mt-0.5 w-6 text-lime-600" />}
            <div className="space-y-1">
              <p className="text-xs font-black uppercase tracking-wider text-neutral-500">Status: {application.status.replace('_', ' ')}</p>
              <h2 className="text-xl font-black">{statusContent?.title}</h2>
              <p className="text-sm text-neutral-500">{statusContent?.description}</p>
            </div>
          </div>
          {application.status === 'REJECTED' && application.rejectionReason && (
            <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">
              <strong>Review note:</strong> {application.rejectionReason}
            </div>
          )}
          {application.status === 'SUSPENDED' && (
            <p className="mt-4 text-xs text-neutral-500">Private administrative details are not shown here.</p>
          )}
        </section>
      )}

      {editable ? (
        <form onSubmit={submitApplication} className="p-6 sm:p-8 bg-white dark:bg-neutral-900 rounded-3xl border border-neutral-200 dark:border-neutral-800 space-y-6 shadow-sm">
          <div className="border-b border-neutral-100 pb-3 dark:border-neutral-800">
            <h2 className="font-extrabold text-lg">{application ? 'Shop application details' : 'Tell us about your shop'}</h2>
            <p className="mt-1 text-xs text-neutral-500">Save an incomplete draft anytime. Required fields are checked before submission.</p>
          </div>

          <div className="rounded-2xl border border-lime-200 bg-lime-50 p-4 text-xs text-lime-950 dark:border-lime-900 dark:bg-lime-950/20 dark:text-lime-200">
            <div className="flex gap-2 font-bold"><ShieldCheck className="w-4 shrink-0" />Application ownership is linked to your authenticated Vibe4You account.</div>
            <p className="mt-1 ml-6">Registered contact: {registeredContact || 'Complete your account contact details before submission.'}</p>
          </div>

          <div className="grid sm:grid-cols-2 gap-4 text-xs">
            <label className="font-bold">Shop name
              <input required minLength={2} maxLength={100} value={draft.shopName} onChange={event => setField('shopName', event.target.value)} placeholder="e.g. Royal Fashion Boutique" className="mt-1 w-full p-3 rounded-xl border dark:bg-neutral-800" />
            </label>
            <label className="font-bold">Owner / contact name
              <input required minLength={2} maxLength={80} value={draft.ownerName} onChange={event => setField('ownerName', event.target.value)} placeholder="e.g. Ramesh Kumar" className="mt-1 w-full p-3 rounded-xl border dark:bg-neutral-800" />
            </label>
            <label className="font-bold">Category
              <select value={draft.category} onChange={event => setField('category', event.target.value)} className="mt-1 w-full p-3 rounded-xl border dark:bg-neutral-800">
                {CATEGORIES.map(category => <option key={category} value={category}>{category}</option>)}
              </select>
            </label>
            <label className="font-bold">Pincode
              <input required inputMode="numeric" pattern="[0-9]{6}" maxLength={6} value={draft.pincode} onChange={event => setField('pincode', event.target.value.replace(/\D/g, ''))} className="mt-1 w-full p-3 rounded-xl border dark:bg-neutral-800" />
            </label>
            <label className="font-bold sm:col-span-2">Shop address
              <input required minLength={5} maxLength={250} value={draft.address} onChange={event => setField('address', event.target.value)} placeholder="Street, market, landmark" className="mt-1 w-full p-3 rounded-xl border dark:bg-neutral-800" />
            </label>
            <label className="font-bold">City
              <input required minLength={2} maxLength={80} value={draft.city} onChange={event => setField('city', event.target.value)} className="mt-1 w-full p-3 rounded-xl border dark:bg-neutral-800" />
            </label>
            <label className="font-bold">State
              <input required minLength={2} maxLength={80} value={draft.state} onChange={event => setField('state', event.target.value)} className="mt-1 w-full p-3 rounded-xl border dark:bg-neutral-800" />
            </label>
            <label className="font-bold sm:col-span-2">Shop description
              <textarea required minLength={10} maxLength={1000} rows={4} value={draft.description} onChange={event => setField('description', event.target.value)} placeholder="Describe your shop, fashion categories, and the products you stock." className="mt-1 w-full p-3 rounded-xl border dark:bg-neutral-800" />
            </label>
            <label className="font-bold sm:col-span-2">Business information <span className="font-normal text-neutral-500">(optional)</span>
              <textarea maxLength={1000} rows={3} value={draft.businessInformation || ''} onChange={event => setField('businessInformation', event.target.value)} placeholder="Any non-sensitive business information helpful for review." className="mt-1 w-full p-3 rounded-xl border dark:bg-neutral-800" />
            </label>
          </div>

          <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
            <button type="button" disabled={saving} onClick={() => void saveDraft()} className="flex items-center justify-center gap-2 rounded-xl border px-5 py-3 font-bold disabled:opacity-60">
              <Save className="w-4" /> {saving ? 'Savingâ€¦' : 'Save Draft'}
            </button>
            <button type="submit" disabled={saving} className="flex items-center justify-center gap-2 rounded-xl bg-neutral-950 px-6 py-3 font-black text-white disabled:opacity-60 dark:bg-lime-400 dark:text-neutral-950">
              Submit for Review <ArrowRight className="w-4" />
            </button>
          </div>
          <p className="text-center text-xs text-neutral-500">Only the private Vibe4You administrator can approve or activate a shop and publish products.</p>
        </form>
      ) : (
        <section className="rounded-3xl border border-neutral-200 bg-white p-6 text-sm dark:border-neutral-800 dark:bg-neutral-900">
          <dl className="grid gap-4 sm:grid-cols-2">
            <div><dt className="text-xs font-bold text-neutral-500">Shop</dt><dd className="font-bold">{application?.shopName}</dd></div>
            <div><dt className="text-xs font-bold text-neutral-500">Category</dt><dd className="font-bold">{application?.category}</dd></div>
            <div className="sm:col-span-2"><dt className="text-xs font-bold text-neutral-500">Location</dt><dd>{application?.address}, {application?.city}, {application?.state} {application?.pincode}</dd></div>
          </dl>
        </section>
      )}

      {application && ['APPROVED', 'ACTIVE'].includes(application.status) && <SellerProducts />}
    </div>
  );
};
