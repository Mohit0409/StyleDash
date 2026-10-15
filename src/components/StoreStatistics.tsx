import React, { useId, useState } from 'react';
import { Activity, Info, ChevronDown, Clock3, Package, Star } from 'lucide-react';
import type { Product } from '../types';
import { StoreReviews } from './StoreReviews';
import { getStoreStatistics, StoreActivityLevel } from '../utils/storeStatistics';
import { getStoreRatingLabel } from '../utils/storeRating';

interface StoreStatisticsProps {
  storeId: string;
  products: readonly Pick<Product, 'id' | 'active' | 'updatedAt'>[];
  rating?: number;
  reviewCount?: number;
  publishedProductCount?: number;
  onReviewSummaryChange?: (rating: number, reviewCount: number) => void;
}

const activityLabels: Record<StoreActivityLevel, string> = {
  daily: 'Daily active',
  weekly: 'Weekly active',
  monthly: 'Monthly active',
  inactive: 'No recent updates',
  unknown: 'Activity unavailable',
};

const activityDetails: Record<StoreActivityLevel, string> = {
  daily: 'A product listing was updated in the last 24 hours',
  weekly: 'A product listing was updated in the last 7 days',
  monthly: 'A product listing was updated in the last 30 days',
  inactive: 'No product listing updates in the last 30 days',
  unknown: 'No valid product update dates recorded',
};

const formatCount = (count: number): string => count.toLocaleString('en-IN');

/**
 * The trigger is positioned over the store cover by StoreDetail's relative
 * wrapper. A closed dropdown takes no space underneath the cover.
 * The existing verified-review component mounts ONLY on explicit expansion.
 */
export const StoreStatistics: React.FC<StoreStatisticsProps> = ({
  storeId,
  products,
  rating,
  reviewCount,
  publishedProductCount,
  onReviewSummaryChange,
}) => {
  const [expanded, setExpanded] = useState(false);
  const [reviewsExpanded, setReviewsExpanded] = useState(false);
  const panelId = useId();
  const reviewsId = useId();

  const summary = getStoreStatistics(products);
  const productCount = typeof publishedProductCount === 'number'
    && Number.isSafeInteger(publishedProductCount) && publishedProductCount >= 0
    ? publishedProductCount : summary.productCount;
  const ratingLabel = getStoreRatingLabel(rating, reviewCount);
  const verifiedReviewCount = ratingLabel && reviewCount ? reviewCount : 0;
  const updatedDate = summary.lastProductUpdate
    ? new Date(summary.lastProductUpdate).toLocaleDateString('en-IN', {
        timeZone: 'Asia/Kolkata',
        day: 'numeric',
        month: 'short',
        year: 'numeric',
      })
    : null;

  const toggleStatistics = () => {
    if (expanded) setReviewsExpanded(false);
    setExpanded(!expanded);
  };

  return (
    <section data-testid="store-statistics" aria-label="Store statistics">
      <button
        type="button"
        className="absolute top-4 left-4 z-30 flex h-10 w-10 items-center justify-center rounded-xl border border-white/40 bg-neutral-950/80 text-white shadow-lg backdrop-blur-md transition-colors hover:bg-neutral-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lime-400 focus-visible:ring-offset-2"
        aria-label={expanded ? 'Hide store statistics' : 'Show store statistics'}
        title="Store statistics"
        aria-controls={panelId}
        aria-expanded={expanded}
        data-testid="store-stat-trigger"
        onClick={toggleStatistics}
      >
        <Info className="h-5 w-5" aria-hidden="true" />
      </button>

      {expanded && (
        <div
          id={panelId}
          data-testid="store-stat-panel"
          className="mt-3 max-w-3xl overflow-hidden rounded-2xl border border-neutral-200 bg-white shadow-sm dark:border-neutral-800 dark:bg-neutral-900"
        >
          <h2 className="sr-only">Store statistics</h2>
          <div className="divide-y divide-neutral-100 dark:divide-neutral-800">
            <div className="flex items-center justify-between gap-4 px-4 py-3 sm:px-5" data-testid="store-stat-products">
              <div className="flex items-center gap-2 text-sm font-semibold text-neutral-700 dark:text-neutral-200">
                <Package className="h-4 w-4 shrink-0 text-neutral-500" aria-hidden="true" />
                <span>Published products</span>
              </div>
              <strong className="text-sm font-black tabular-nums text-neutral-950 dark:text-white">
                {formatCount(productCount)}
              </strong>
            </div>

            <div data-testid="store-stat-rating">
              <button
                type="button"
                className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left transition-colors hover:bg-neutral-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-lime-500 dark:hover:bg-neutral-800 sm:px-5"
                aria-expanded={reviewsExpanded}
                aria-controls={reviewsId}
                onClick={() => setReviewsExpanded(value => !value)}
                data-testid="store-rating-toggle"
              >
                <span className="flex items-center gap-2 text-sm font-semibold text-neutral-700 dark:text-neutral-200">
                  <Star className="h-4 w-4 shrink-0 text-amber-500" aria-hidden="true" />
                  Store rating
                </span>
                <span className="flex items-center gap-2 text-right text-sm font-black text-neutral-950 dark:text-white">
                  <span>
                    {ratingLabel ?? 'Not rated yet'}
                    {verifiedReviewCount > 0 && (
                      <span className="ml-1 font-normal text-neutral-500 dark:text-neutral-400">
                        ({formatCount(verifiedReviewCount)})
                      </span>
                    )}
                  </span>
                  <ChevronDown
                    className={`h-4 w-4 shrink-0 text-neutral-500 transition-transform ${reviewsExpanded ? 'rotate-180' : ''}`}
                    aria-hidden="true"
                  />
                </span>
              </button>

              {reviewsExpanded && (
                <div id={reviewsId} data-testid="store-rating-reviews" className="px-4 pb-4 sm:px-5">
                  <StoreReviews
                    storeId={storeId}
                    onSummaryChange={onReviewSummaryChange}
                    compact
                  />
                </div>
              )}
            </div>

            <div className="flex flex-wrap items-start justify-between gap-2 px-4 py-3 sm:px-5" data-testid="store-stat-activity">
              <div className="flex items-center gap-2 text-sm font-semibold text-neutral-700 dark:text-neutral-200">
                <Activity className="h-4 w-4 shrink-0 text-emerald-500" aria-hidden="true" />
                <span>Catalogue activity</span>
              </div>
              <div className="text-left sm:text-right">
                <p className="text-sm font-black text-neutral-950 dark:text-white">{activityLabels[summary.activityLevel]}</p>
                <p className="mt-0.5 text-xs text-neutral-500 dark:text-neutral-400">{activityDetails[summary.activityLevel]}</p>
                {updatedDate && (
                  <p className="mt-1 inline-flex items-center gap-1 text-xs text-neutral-500 dark:text-neutral-400">
                    <Clock3 className="h-3 w-3" aria-hidden="true" /> Latest update: {updatedDate}
                  </p>
                )}
              </div>
              <div className="flex w-full flex-wrap gap-x-4 gap-y-1 pt-1 text-xs text-neutral-600 dark:text-neutral-300" data-testid="store-stat-update-counts">
                <span><strong className="tabular-nums">{formatCount(summary.updatedLast24Hours)}</strong> updated in 24h</span>
                <span><strong className="tabular-nums">{formatCount(summary.updatedLast7Days)}</strong> updated in 7 days</span>
                <span><strong className="tabular-nums">{formatCount(summary.updatedLast30Days)}</strong> updated in 30 days</span>
              </div>
            </div>
          </div>
          <p className="border-t border-neutral-100 px-4 py-2.5 text-[11px] text-neutral-500 dark:border-neutral-800 dark:text-neutral-400 sm:px-5">
            Activity tracks product listing updates, not seller login, opening hours or customer visits.
          </p>
        </div>
      )}
    </section>
  );
};
