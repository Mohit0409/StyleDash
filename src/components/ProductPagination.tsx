import React from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { paginationSlots } from '../utils/pagination';

interface ProductPaginationProps {
  page: number;
  totalPages: number;
  totalItems: number;
  from: number;
  to: number;
  onPageChange: (page: number) => void;
  label?: string;
  testId?: string;
}

/** Mobile-friendly, keyboard accessible page numbers for actual product grids. */
export const ProductPagination: React.FC<ProductPaginationProps> = ({
  page,
  totalPages,
  totalItems,
  from,
  to,
  onPageChange,
  label = 'products',
  testId,
}) => {
  if (totalPages <= 1) return null;

  const style = 'inline-flex h-11 min-w-11 items-center justify-center rounded-xl border px-2 text-sm font-bold transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-lime-600';
  const inactive = 'border-neutral-200 bg-white text-neutral-800 hover:border-lime-500 hover:bg-lime-50 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-100 dark:hover:bg-neutral-800';
  const active = 'border-neutral-950 bg-neutral-950 text-white dark:border-lime-400 dark:bg-lime-400 dark:text-neutral-950';

  return (
    <nav aria-label={`${label} pagination`} data-testid={testId} className="flex scroll-mt-24 flex-col items-center gap-3 pt-5">
      <p role="status" aria-live="polite" className="text-xs font-semibold text-neutral-600 dark:text-neutral-300">
        Showing {from}–{to} of {totalItems} {label}
      </p>
      <div className="flex max-w-full flex-wrap items-center justify-center gap-1.5 sm:gap-2">
        <button type="button" disabled={page === 1} onClick={() => onPageChange(page - 1)}
          className={`${style} ${inactive} gap-1 disabled:cursor-not-allowed disabled:opacity-40`}
          aria-label={`Previous ${label} page`}>
          <ChevronLeft className="h-4 w-4" aria-hidden="true" /><span className="hidden sm:inline">Previous</span>
        </button>
        {paginationSlots(page, totalPages).map((slot, index) => slot === 'gap' ? (
          <span key={`gap-${index}`} aria-hidden="true" className="px-1 text-neutral-500">…</span>
        ) : (
          <button key={slot} type="button" onClick={() => onPageChange(slot)}
            aria-label={`Page ${slot} of ${totalPages} for ${label}`}
            aria-current={page === slot ? 'page' : undefined}
            className={`${style} ${page === slot ? active : inactive}`}>
            {slot}
          </button>
        ))}
        <button type="button" disabled={page === totalPages} onClick={() => onPageChange(page + 1)}
          className={`${style} ${inactive} gap-1 disabled:cursor-not-allowed disabled:opacity-40`}
          aria-label={`Next ${label} page`}>
          <span className="hidden sm:inline">Next</span><ChevronRight className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>
      <span className="sr-only">Page {page} of {totalPages}</span>
    </nav>
  );
};
