import React from 'react';
import { Activity, Clock3, Package, Star } from 'lucide-react';
import type { Product } from '../types';
import { getStoreStatistics, StoreActivityLevel } from '../utils/storeStatistics';

interface StoreStatisticsProps {
  products: readonly Pick<Product, 'id' | 'active' | 'updatedAt'>[];
  rating?: number;
  reviewCount?: number;
}

const activityLabels: Record<StoreActivityLevel, string> = {
  daily: 'Daily active',
  weekly: 'Weekly active',
  monthly: 'Monthly active',
  inactive: 'No recent updates',
  unknown: 'Activity unavailable',
};

const activityDetails: Record<StoreActivityLevel, string> = {
  daily: 'Product listing updated in the last 24 hours',
  weekly: 'Product listing updated in the last 7 days',
  monthly: 'Product listing updated in the last 30 days',
  inactive: 'No listing updates in the last 30 days',
  unknown: 'No valid product update dates recorded',
};

const formatCount = (count: number): string => count.toLocaleString('en-IN');

export const StoreStatistics: React.FC<StoreStatisticsProps> = ({
  products,
  rating,
  reviewCount,
}) => {
  const summary = getStoreStatistics(products);
  const validRating = typeof rating === 'number' && Number.isFinite(rating) && rating >= 1 && rating <= 5
    ? rating : null;
  const validReviewCount = typeof reviewCount === 'number' && Number.isInteger(reviewCount) && reviewCount > 0
    ? reviewCount : 0;
  const hasRating = validRating !== null && validReviewCount > 0;

  const updatedDate = summary.lastProductUpdate
    ? new Date(summary.lastProductUpdate).toLocaleDateString('en-IN', {
        timeZone: 'Asia/Kolkata',
        day: 'numeric',
        month: 'short',
        year: 'numeric',
      })
    : null;

  return (
    <section aria-labelledby="store-statistics-heading" data-testid="store-statistics" className="space-y-4">
      <div className="space-y-1">
        <h2 id="store-statistics-heading" className="text-xl font-black text-neutral-900 dark:text-white">
          Store at a glance
        </h2>
        <p className="text-xs text-neutral-500 dark:text-neutral-400">
          Published products, verified ratings and recent catalogue updates
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 sm:gap-4">
        <div className="rounded-2xl border border-neutral-200 bg-white p-5 dark:border-neutral-800 dark:bg-neutral-900" data-testid="store-stat-products">
          <div className="mb-3 flex items-center gap-2 text-neutral-500 dark:text-neutral-400">
            <Package aria-hidden="true" className="h-4 w-4" />
            <span className="text-xs font-bold">Published products</span>
          </div>
          <p className="text-2xl font-black tabular-nums text-neutral-950 dark:text-white">
            {formatCount(summary.productCount)}
          </p>
          <p className="mt-1 text-xs text-neutral-500 dark:text-neutral-400">
            Products listed on Vibe4You
          </p>
        </div>

        <div className="rounded-2xl border border-neutral-200 bg-white p-5 dark:border-neutral-800 dark:bg-neutral-900" data-testid="store-stat-rating">
          <div className="mb-3 flex items-center gap-2 text-neutral-500 dark:text-neutral-400">
            <Star aria-hidden="true" className="h-4 w-4 text-amber-500" />
            <span className="text-xs font-bold">Store rating</span>
          </div>
          <p className="text-2xl font-black tabular-nums text-neutral-950 dark:text-white">
            {hasRating ? validRating?.toFixed(1) + ' / 5' : 'Not rated yet'}
          </p>
          <p className="mt-1 text-xs text-neutral-500 dark:text-neutral-400">
            {hasRating
              ? formatCount(validReviewCount) + ' verified customer review' + (validReviewCount === 1 ? '' : 's')
              : 'No verified customer ratings yet'}
          </p>
        </div>

        <div className="rounded-2xl border border-neutral-200 bg-white p-5 dark:border-neutral-800 dark:bg-neutral-900" data-testid="store-stat-activity">
          <div className="mb-3 flex items-center gap-2 text-neutral-500 dark:text-neutral-400">
            <Activity aria-hidden="true" className="h-4 w-4 text-emerald-500" />
            <span className="text-xs font-bold">Catalogue activity</span>
          </div>
          <p className="text-lg font-black text-neutral-950 dark:text-white">
            {activityLabels[summary.activityLevel]}
          </p>
          <p className="mt-1 text-xs text-neutral-500 dark:text-neutral-400">
            {activityDetails[summary.activityLevel]}
          </p>
          {updatedDate && (
            <p className="mt-2 flex items-center gap-1.5 text-xs text-neutral-600 dark:text-neutral-300">
              <Clock3 aria-hidden="true" className="h-3.5 w-3.5" />
              Latest update: {updatedDate}
            </p>
          )}
        </div>
      </div>

      <div className="flex flex-wrap gap-x-5 gap-y-2 rounded-xl bg-neutral-50 px-4 py-3 text-xs text-neutral-600 dark:bg-neutral-900/60 dark:text-neutral-300" data-testid="store-stat-update-counts">
        <span><strong className="font-black text-neutral-900 dark:text-white">{formatCount(summary.updatedLast24Hours)}</strong> updated in 24h</span>
        <span><strong className="font-black text-neutral-900 dark:text-white">{formatCount(summary.updatedLast7Days)}</strong> updated in 7 days</span>
        <span><strong className="font-black text-neutral-900 dark:text-white">{formatCount(summary.updatedLast30Days)}</strong> updated in 30 days</span>
      </div>
      <p className="text-[11px] text-neutral-500 dark:text-neutral-400">
        Activity reflects the latest recorded update of each published product, not seller login, store opening hours or customer visits.
      </p>
    </section>
  );
};
