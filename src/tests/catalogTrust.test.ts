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
  it('does not expose placeholder brand values', () => {
    expect(PRODUCTS.some(product => product.brand.trim().toLowerCase() === 'wrong')).toBe(false);
  });

  it('does not ship commission metadata in the customer product bundle', () => {
    for (const product of PRODUCTS) {
      expect('commissionPercent' in product).toBe(false);
      expect('commissionPaise' in product).toBe(false);
      expect('customerPricePaise' in product).toBe(false);
    }
  });

});
