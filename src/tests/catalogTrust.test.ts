import { describe, expect, it } from 'vitest';
import { PRODUCTS } from '../data/products';

describe('catalog trust signals', () => {
  it('does not publish placeholder customer reviews as verified purchases', () => {
    for (const product of PRODUCTS) {
      expect(product.reviews ?? []).toEqual([]);
      expect(product.reviewCount).toBe(0);
      expect(product.rating).toBe(0);
    }
  });
});
