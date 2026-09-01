import React, { useCallback, useEffect, useState } from 'react';
import { CheckCircle, Star, Trash2 } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { ApiError } from '../services/apiClient';
import {
  ProductReviews as ProductReviewsData,
  ReviewDraft,
  ReviewEligibility,
  ReviewSort,
  reviewApi,
} from '../services/reviewApi';

interface ProductReviewsProps {
  productId: string;
  onSummaryChange?: (rating: number, reviewCount: number) => void;
}

const emptyData = (productId: string): ProductReviewsData => ({
  productId,
  rating: 0,
  reviewCount: 0,
  distribution: { '5': 0, '4': 0, '3': 0, '2': 0, '1': 0 },
  reviews: [],
});

export const ProductReviews: React.FC<ProductReviewsProps> = ({ productId, onSummaryChange }) => {
  const { user } = useAuth();
  const { showToast } = useToast();
  const [data, setData] = useState<ProductReviewsData>(() => emptyData(productId));
  const [eligibility, setEligibility] = useState<ReviewEligibility | null>(null);
  const [sort, setSort] = useState<ReviewSort>('newest');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [rating, setRating] = useState(5);
  const [title, setTitle] = useState('');
  const [comment, setComment] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const reviews = await reviewApi.list(productId, sort);
      setData(reviews);
      onSummaryChange?.(reviews.rating, reviews.reviewCount);
      if (user) {
        const nextEligibility = await reviewApi.eligibility(productId);
        setEligibility(nextEligibility);
        if (nextEligibility.existingReview) {
          setRating(nextEligibility.existingReview.rating);
          setTitle(nextEligibility.existingReview.title || '');
          setComment(nextEligibility.existingReview.comment);
        } else {
          setRating(5);
          setTitle('');
          setComment('');
        }
      } else {
        setEligibility(null);
      }
    } catch (cause) {
      showToast(cause instanceof ApiError ? cause.message : 'Could not load customer reviews.', 'error');
    } finally {
      setLoading(false);
    }
  }, [onSummaryChange, productId, showToast, sort, user]);

  useEffect(() => { void load(); }, [load]);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!eligibility?.eligible) return;
    const draft: ReviewDraft = { rating, title: title.trim() || undefined, comment };
    setSaving(true);
    try {
      if (eligibility.existingReview) {
        await reviewApi.edit(eligibility.existingReview.id, draft);
        showToast('Your review was updated.', 'success');
      } else {
        await reviewApi.create(productId, draft);
        showToast('Thanks! Your verified review is live.', 'success');
      }
      await load();
    } catch (cause) {
      showToast(cause instanceof ApiError ? cause.message : 'Could not save your review.', 'error');
    } finally {
      setSaving(false);
    }
  };

  const remove = async () => {
    const existing = eligibility?.existingReview;
    if (!existing || saving) return;
    if (!window.confirm('Delete your review?')) return;
    setSaving(true);
    try {
      await reviewApi.delete(existing.id);
      showToast('Your review was deleted.', 'success');
      await load();
    } catch (cause) {
      showToast(cause instanceof ApiError ? cause.message : 'Could not delete your review.', 'error');
    } finally {
      setSaving(false);
    }
  };

  const form = user ? (
    eligibility?.eligible ? (
      <form onSubmit={submit} className="rounded-2xl border border-neutral-200 dark:border-neutral-800 p-5 space-y-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h4 className="font-black text-sm">
              {eligibility.existingReview ? 'Edit your review' : 'Review your purchase'}
            </h4>
            <p className="text-[11px] text-neutral-500 mt-1 flex items-center gap-1">
              <CheckCircle className="w-3.5 h-3.5 text-emerald-500" /> Verified delivered purchase
            </p>
          </div>
          {eligibility.existingReview && (
            <button type="button" onClick={remove} disabled={saving}
              className="text-xs font-bold text-rose-600 flex items-center gap-1 disabled:opacity-50">
              <Trash2 className="w-3.5 h-3.5" /> Delete
            </button>
          )}
        </div>
        <fieldset>
          <legend className="text-xs font-bold mb-2">Your rating</legend>
          <div className="flex gap-1" role="radiogroup" aria-label="Star rating">
            {[1, 2, 3, 4, 5].map(stars => (
              <button key={stars} type="button" role="radio" aria-checked={rating === stars}
                aria-label={`${stars} star${stars === 1 ? '' : 's'}`} onClick={() => setRating(stars)}
                className="p-1 rounded focus:outline-none focus:ring-2 focus:ring-lime-500">
                <Star className={`w-6 h-6 ${stars <= rating ? 'fill-amber-400 text-amber-400' : 'text-neutral-300'}`} />
              </button>
            ))}
          </div>
        </fieldset>

        <label className="block text-xs font-bold">
          Title <span className="font-normal text-neutral-400">(optional)</span>
          <input value={title} onChange={event => setTitle(event.target.value)} maxLength={80}
            className="mt-1.5 w-full rounded-xl border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-3 py-2.5 text-sm"
            placeholder="What stood out?" />
        </label>

        <label className="block text-xs font-bold">
          Review
          <textarea value={comment} onChange={event => setComment(event.target.value)} minLength={3} maxLength={1000} required rows={4}
            className="mt-1.5 w-full rounded-xl border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-3 py-2.5 text-sm resize-y"
            placeholder="Share your experience with this product." />
        </label>

        <button type="submit" disabled={saving || comment.trim().length < 3}
          className="px-5 py-2.5 rounded-xl bg-neutral-950 dark:bg-lime-400 text-white dark:text-neutral-950 text-xs font-black disabled:opacity-50">
          {saving ? 'Saving...' : eligibility.existingReview ? 'Update Review' : 'Publish Review'}
        </button>
      </form>
    ) : (
      <div className="rounded-2xl border border-neutral-200 dark:border-neutral-800 p-5 text-xs text-neutral-500">
        Reviews are available after this product has been delivered to you.
      </div>
    )
  ) : (
    <div className="rounded-2xl border border-neutral-200 dark:border-neutral-800 p-5 text-xs text-neutral-500">
      <Link to="/login" className="font-black text-neutral-900 dark:text-white underline">Sign in</Link> to review a delivered purchase.
    </div>
  );

  return (
    <section className="pt-10 border-t border-neutral-200 dark:border-neutral-800 space-y-6" aria-labelledby="customer-reviews-heading">
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <h2 id="customer-reviews-heading" className="text-xl font-black">Customer Reviews</h2>
          {data.reviewCount > 0 ? (
            <div className="flex items-center gap-2 mt-2">
              <span className="text-3xl font-black">{data.rating}</span>
              <div>
                <div className="flex text-amber-400" aria-label={`${data.rating} out of 5 stars`}>
                  {[1, 2, 3, 4, 5].map(stars => (
                    <Star key={stars} className={`w-4 h-4 ${stars <= Math.round(data.rating) ? 'fill-amber-400' : ''}`} />
                  ))}
                </div>
                <p className="text-[11px] text-neutral-500 mt-1">Based on {data.reviewCount} verified review{data.reviewCount === 1 ? '' : 's'}</p>
              </div>
            </div>
          ) : <p className="text-xs text-neutral-500 mt-2">No customer reviews yet.</p>}
        </div>
        {data.reviewCount > 1 && (
          <label className="text-xs font-bold">
            Sort reviews
            <select value={sort} onChange={event => setSort(event.target.value as ReviewSort)}
              className="ml-2 rounded-lg border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-2 py-1.5">
              <option value="newest">Newest</option>
              <option value="highest">Highest rated</option>
              <option value="lowest">Lowest rated</option>
            </select>
          </label>
        )}
      </div>

      {form}

      {loading ? (
        <p className="text-xs text-neutral-500">Loading reviews...</p>
      ) : data.reviews.length > 0 ? (
        <div className="space-y-4">
          {data.reviews.map(review => (
            <article key={review.id} className="rounded-2xl bg-neutral-50 dark:bg-neutral-900/50 border border-neutral-200 dark:border-neutral-800 p-5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="font-black text-sm">{review.userName}</p>
                  <p className="text-[11px] text-emerald-600 dark:text-emerald-400 font-bold flex items-center gap-1 mt-0.5">
                    <CheckCircle className="w-3.5 h-3.5" /> Verified Purchase
                  </p>
                </div>
                <time className="text-[11px] text-neutral-400" dateTime={review.createdAt}>
                  {new Date(review.createdAt).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}
                </time>
              </div>
              <div className="flex gap-0.5 mt-3 text-amber-400" aria-label={`${review.rating} out of 5 stars`}>
                {[1, 2, 3, 4, 5].map(stars => (
                  <Star key={stars} className={`w-4 h-4 ${stars <= review.rating ? 'fill-amber-400' : ''}`} />
                ))}
              </div>
              {review.title && <h3 className="font-black text-sm mt-3">{review.title}</h3>}
              <p className="text-sm text-neutral-600 dark:text-neutral-300 mt-2 whitespace-pre-wrap break-words">{review.comment}</p>
            </article>
          ))}
        </div>
      ) : null}
    </section>
  );
};
