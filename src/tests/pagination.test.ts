import { describe, expect, it } from 'vitest';
import { normalizePageNumber, paginateItems, paginationSlots } from '../utils/pagination';

const items = Array.from({ length: 53 }, (_, index) => `item-${index + 1}`);

describe('safe Vibe4You product pagination', () => {
  it('shows the correct slice without altering the ordering or the source list', () => {
    const first = paginateItems(items, null, 24);
    const second = paginateItems(items, '2', 24);
    const last = paginateItems(items, '3', 24);
    expect(first).toMatchObject({ page: 1, totalPages: 3, totalItems: 53, from: 1, to: 24 });
    expect(second).toMatchObject({ page: 2, from: 25, to: 48 });
    expect(last).toMatchObject({ page: 3, from: 49, to: 53 });
    expect(first.items[0]).toBe('item-1');
    expect(second.items[0]).toBe('item-25');
    expect(last.items).toEqual(['item-49', 'item-50', 'item-51', 'item-52', 'item-53']);
    expect(items).toHaveLength(53);
    expect(new Set([ ...first.items, ...second.items, ...last.items ]).size).toBe(53);
  });

  it('clamps unsupported page numbers safely, including huge and malicious-looking values', () => {
    expect(normalizePageNumber('10000', 3)).toBe(3);
    expect(normalizePageNumber('99999999999999999999999999', 3)).toBe(3);
    for (const raw of [null, '0', '-4', '', '2.5', '0x03', '01', 'NaN', '<script>', 'Infinity', '2e2']) {
      expect(normalizePageNumber(raw, 3)).toBe(1);
    }
    expect(normalizePageNumber('3', 3)).toBe(3);
  });

  it('does not invent product pages for empty or single-page results', () => {
    expect(paginateItems([], '15', 24)).toEqual({
      items: [], page: 1, totalPages: 1, totalItems: 0, from: 0, to: 0,
    });
    expect(paginateItems(['a'], '10', 24)).toEqual({
      items: ['a'], page: 1, totalPages: 1, totalItems: 1, from: 1, to: 1,
    });
  });

  it('protects against zero, invalid, and fractional page sizes', () => {
    expect(paginateItems(items, null, 0).items).toHaveLength(1);
    expect(paginateItems(items, null, NaN).items).toHaveLength(1);
    expect(paginateItems(items, null, 0.5).items).toHaveLength(1);
    expect(paginateItems(items, null, Infinity).items).toHaveLength(1);
  });

  it('keeps numbered controls short with ellipses on very large catalogues', () => {
    expect(paginationSlots(1, 3)).toEqual([1, 2, 3]);
    expect(paginationSlots(1, 100)).toEqual([1, 2, 'gap', 100]);
    expect(paginationSlots(50, 100)).toEqual([1, 'gap', 49, 50, 51, 'gap', 100]);
    expect(paginationSlots(99, 100)).toEqual([1, 'gap', 98, 99, 100]);
  });
});
