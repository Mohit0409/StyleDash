import { useCallback, useEffect, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { paginateItems } from '../utils/pagination';

/**
 * Shareable URL paging. Each listing uses its own query key so unrelated
 * filters and multiple offer periods preserve their place across navigation.
 */
export const useProductPagination = <T,>(
  items: readonly T[],
  pageSize: number,
  queryKey = 'page',
  ready = true,
  scrollTargetId?: string,
) => {
  const [searchParams, setSearchParams] = useSearchParams();
  const rawPage = searchParams.get(queryKey);

  const pagination = useMemo(
    () => paginateItems(items, rawPage, pageSize),
    [items, rawPage, pageSize],
  );

  // Do not normalize deep links while the asynchronous catalogue is loading.
  // Out-of-range or malformed pages are replaced without pushing a history
  // entry, while legitimate filter/sort/search parameters remain intact.
  useEffect(() => {
    if (!ready || rawPage === null) return;
    const canonicalPage = pagination.page === 1 ? null : String(pagination.page);
    if (rawPage === canonicalPage) return;

    const next = new URLSearchParams(searchParams);
    if (canonicalPage === null) next.delete(queryKey);
    else next.set(queryKey, canonicalPage);
    setSearchParams(next, { replace: true });
  }, [pagination.page, queryKey, rawPage, ready, searchParams, setSearchParams]);

  const changePage = useCallback((nextPage: number) => {
    const safePage = Math.max(1, Math.min(Math.trunc(nextPage), pagination.totalPages));
    if (!Number.isFinite(safePage) || safePage === pagination.page) return;

    const next = new URLSearchParams(searchParams);
    if (safePage === 1) next.delete(queryKey);
    else next.set(queryKey, String(safePage));
    setSearchParams(next);

    if (scrollTargetId && typeof window !== 'undefined') {
      window.requestAnimationFrame(() => {
        document.getElementById(scrollTargetId)?.scrollIntoView({
          block: 'start',
          behavior: 'auto',
        });
      });
    }
  }, [pagination.page, pagination.totalPages, queryKey, scrollTargetId, searchParams, setSearchParams]);

  return { ...pagination, changePage };
};
