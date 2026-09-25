import { describe, expect, it } from 'vitest';
import type { VendorStore } from '../types';
import { rankStoresByProductCount } from '../utils/storeRanking';

const store = (
  id: string,
  storeName: string,
  productCount: number,
  createdAt: string,
): VendorStore => ({
  id,
  slug: `local-shop-${id}`,
  storeName,
  category: 'Clothing & Fashion',
  address: 'Neemuch',
  pincode: '458441',
  city: 'Neemuch',
  deliveryMinutes: 60,
  description: 'Local store',
  active: true,
  approved: true,
  createdAt,
  productCount,
});

describe('Local Stores ranking', () => {
  it('puts shops with more published products first instead of newest shops', () => {
    const newest = store('newest', 'Newest Shop', 1, '2026-09-25T10:00:00Z');
    const mostProducts = store('most', 'Most Products Shop', 12, '2026-08-01T10:00:00Z');
    const middle = store('middle', 'Middle Shop', 5, '2026-07-01T10:00:00Z');

    expect(rankStoresByProductCount([newest, middle, mostProducts]).map(item => item.id))
      .toEqual(['most', 'middle', 'newest']);
  });

  it('uses shop name as a deterministic tie-breaker and does not mutate input', () => {
    const input = [
      store('z', 'Zulu Store', 4, '2026-09-25T10:00:00Z'),
      store('a', 'Alpha Store', 4, '2026-01-01T10:00:00Z'),
    ];

    expect(rankStoresByProductCount(input).map(item => item.storeName))
      .toEqual(['Alpha Store', 'Zulu Store']);
    expect(input.map(item => item.storeName)).toEqual(['Zulu Store', 'Alpha Store']);
  });
});
