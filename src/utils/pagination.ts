/** Pure, bounded client-side pagination of a previously filtered/sorted list. */
export interface PagedItems<T> {
  items: T[];
  page: number;
  totalPages: number;
  totalItems: number;
  from: number;
  to: number;
}

export const normalizePageNumber = (value: string | null, totalPages: number): number => {
  const lastPage = Math.max(1, Math.trunc(totalPages));
  if (!value || !/^[1-9]\d*$/.test(value)) return 1;
  const parsed = Number(value);
  if (!Number.isSafeInteger(parsed)) return lastPage;
  return Math.max(1, Math.min(parsed, lastPage));
};

export const paginateItems = <T,>(
  allItems: readonly T[],
  rawPage: string | null,
  pageSize: number,
): PagedItems<T> => {
  const size = Number.isFinite(pageSize) && pageSize > 0 ? Math.max(1, Math.trunc(pageSize)) : 1;
  const totalItems = allItems.length;
  const totalPages = Math.max(1, Math.ceil(totalItems / size));
  const page = normalizePageNumber(rawPage, totalPages);
  const fromIndex = (page - 1) * size;
  const items = allItems.slice(fromIndex, fromIndex + size);

  return {
    items,
    page,
    totalPages,
    totalItems,
    from: totalItems === 0 ? 0 : fromIndex + 1,
    to: fromIndex + items.length,
  };
};

export type PageSlot = number | 'gap';

/** At most five numbered links plus separating ellipses on large catalogues. */
export const paginationSlots = (page: number, totalPages: number): PageSlot[] => {
  if (totalPages <= 7) {
    return Array.from({ length: Math.max(0, totalPages) }, (_, index) => index + 1);
  }
  const selected = new Set([1, totalPages, page - 1, page, page + 1]);
  const numbered = [...selected]
    .filter(number => number >= 1 && number <= totalPages)
    .sort((a, b) => a - b);
  const slots: PageSlot[] = [];
  for (const number of numbered) {
    const previous = slots.length ? slots[slots.length - 1] : undefined;
    if (typeof previous === 'number' && number - previous > 1) {
      if (number - previous === 2) slots.push(previous + 1);
      else slots.push('gap');
    }
    slots.push(number);
  }
  return slots;
};
