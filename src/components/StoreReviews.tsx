import React, { useCallback, useEffect, useState } from 'react';
import { CheckCircle, Star } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { ApiError } from '../services/apiClient';
import {
  ReviewDraft, ReviewEligibility, ReviewSort, StoreReviews as StoreReviewsData, storeReviewApi,
} from '../services/reviewApi';

interface StoreReviewsProps {
  storeId: string;
  onSummaryChange?: (rating: number, reviewCount: number) => void;
}

const emptyData = (storeId: string): StoreReviewsData => ({
  storeId, rating: 0, reviewCount: 0,
  distribution: { '5': 0, '4': 0, '3': 0, '2': 0, '1': 0 }, reviews: [],
});

export const StoreReviews: React.FC<StoreReviewsProps> = ({ storeId, onSummaryChange }) => {
  const { user } = useAuth();
  const { showToast } = useToast();
  const [data, setData] = useState<StoreReviewsData>(() => emptyData(storeId));
  const [eligibility, setEligibility] = useState<ReviewEligibility | null>(null);
  const [sort, setSort] = useState<ReviewSort>('newest');
  const [rating, setRating] = useState(5);
  const [title, setTitle] = useState('');
  const [comment, setComment] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const result = await storeReviewApi.list(storeId, sort);
      setData(result);
      onSummaryChange?.(result.rating, result.reviewCount);
      if (user) {
        const next = await storeReviewApi.eligibility(storeId);
        setEligibility(next);
        if (next.existingReview) {
          setRating(next.existingReview.rating);
          setTitle(next.existingReview.title || '');
          setComment(next.existingReview.comment);
        }
      } else {
        setEligibility(null);
      }
    } catch (cause) {
      showToast(cause instanceof ApiError ? cause.message : 'Could not load local store reviews.', 'error');
    } finally {
      setLoading(false);
    }
  }, [onSummaryChange, showToast, sort, storeId, user]);

  useEffect(() => { void load(); }, [load]);

  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!eligibility?.eligible || saving) return;
    setSaving(true);
    const draft: ReviewDraft = { rating, title, comment };
    try {
      if (eligibility.existingReview) {
        await storeReviewApi.edit(eligibility.existingReview.id, draft);
        showToast('Your local store review was updated.', 'success');
      } else {
        await storeReviewApi.create(storeId, draft);
        showToast('Thanks! Your verified local store review is live.', 'success');
      }
      await load();
    } catch (cause) {
      showToast(cause instanceof ApiError ? cause.message : 'Could not save your local store review.', 'error');
    } finally {
      setSaving(false);
    }
  };

  const remove = async () => {
    const existing = eligibility?.existingReview;
    if (!existing || saving || !window.confirm('Delete your local store review?')) return;
    setSaving(true);
    try {
      await storeReviewApi.delete(existing.id);
      setTitle(''); setComment(''); setRating(5);
      showToast('Your local store review was deleted.', 'success');
      await load();
    } catch (cause) {
      showToast(cause instanceof ApiError ? cause.message : 'Could not delete your local store review.', 'error');
    } finally {
      setSaving(false);
    }
  };

  const form = eligibility?.eligible ? (
    <form onSubmit={save} className="rounded-2xl border border-neutral-200 dark:border-neutral-800 p-5 space-y-3">
      <div className="flex items-center justify-between gap-3"><div><h3 className="font-black text-sm">{eligibility.existingReview ? 'Edit your store review' : 'Review this local store'}</h3><p className="text-[11px] text-neutral-500 mt-1 flex gap-1 items-center"><CheckCircle className="w-3.5 h-3.5 text-emerald-500" /> Verified delivered purchase</p></div>{eligibility.existingReview && <button type="button" onClick={() => void remove()} className="text-xs font-bold text-red-600">Delete</button>}</div>
      <div className="flex gap-1" aria-label="Store rating">{[1, 2, 3, 4, 5].map(value => <button type="button" key={value} onClick={() => setRating(value)} aria-label={`${value} stars`} className="p-1"><Star className={`w-6 h-6 ${value <= rating ? 'fill-amber-400 text-amber-400' : 'text-neutral-300'}`} /></button>)}</div>
      <input value={title} onChange={event => setTitle(event.target.value)} maxLength={80} placeholder="Title (optional)" className="w-full rounded-xl border border-neutral-300 dark:border-neutral-700 bg-transparent px-3 py-2 text-sm" />
      <textarea required minLength={3} maxLength={1000} value={comment} onChange={event => setComment(event.target.value)} placeholder="Tell neighbours about your experience" className="w-full min-h-24 rounded-xl border border-neutral-300 dark:border-neutral-700 bg-transparent px-3 py-2 text-sm" />
      <button disabled={saving} className="rounded-xl bg-neutral-950 dark:bg-white text-white dark:text-neutral-950 px-4 py-2 text-xs font-black disabled:opacity-50">{saving ? 'Saving…' : eligibility.existingReview ? 'Update review' : 'Publish review'}</button>
    </form>
  ) : user ? <p className="rounded-2xl border border-neutral-200 dark:border-neutral-800 p-4 text-xs text-neutral-500">{eligibility?.reason === 'own_store_review_forbidden' ? 'Store owners cannot review their own store.' : 'You can review this store after a delivered purchase from it.'}</p>
    : <p className="rounded-2xl border border-neutral-200 dark:border-neutral-800 p-4 text-xs text-neutral-500"><Link to="/login" className="font-black underline text-neutral-900 dark:text-white">Sign in</Link> to review a delivered local-store purchase.</p>;

  return <section className="border-t border-neutral-200 dark:border-neutral-800 pt-8 space-y-5" aria-labelledby="store-reviews-heading">
    <div className="flex flex-wrap items-end justify-between gap-3"><div><h2 id="store-reviews-heading" className="text-xl font-black">Store Reviews</h2>{data.reviewCount ? <p className="mt-1 text-xs text-neutral-500"><strong className="text-neutral-900 dark:text-white">{data.rating} / 5</strong> from {data.reviewCount} verified customer review{data.reviewCount === 1 ? '' : 's'}</p> : <p className="mt-1 text-xs text-neutral-500">No customer reviews yet.</p>}</div>{data.reviewCount > 1 && <label className="text-xs font-bold">Sort <select value={sort} onChange={event => setSort(event.target.value as ReviewSort)} className="ml-1 rounded-lg border border-neutral-300 dark:border-neutral-700 bg-transparent p-1"><option value="newest">Newest</option><option value="highest">Highest rated</option><option value="lowest">Lowest rated</option></select></label>}</div>
    {form}
    {loading ? <p className="text-xs text-neutral-500">Loading reviews…</p> : data.reviews.length ? <div className="space-y-3">{data.reviews.map(review => <article key={review.id} className="rounded-2xl bg-neutral-50 dark:bg-neutral-900/50 border border-neutral-200 dark:border-neutral-800 p-4"><div className="flex items-start justify-between gap-3"><div><p className="font-black text-sm">{review.userName}</p><p className="mt-1 flex gap-0.5 text-amber-400" aria-label={`${review.rating} out of 5 stars`}>{[1,2,3,4,5].map(value => <Star key={value} className={`w-3.5 h-3.5 ${value <= review.rating ? 'fill-amber-400' : ''}`} />)}</p></div><time className="text-[11px] text-neutral-400" dateTime={review.createdAt}>{new Date(review.createdAt).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}</time></div>{review.title && <h3 className="font-black text-sm mt-3">{review.title}</h3>}<p className="mt-2 whitespace-pre-wrap break-words text-sm text-neutral-600 dark:text-neutral-300">{review.comment}</p></article>)}</div> : <p className="text-xs text-neutral-500">Be the first verified customer to review this local store.</p>}
  </section>;
};
