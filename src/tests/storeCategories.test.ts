import { describe, expect, it } from 'vitest';
import { CATEGORY_DISPLAY_ORDER, STORE_CATEGORIES } from '../data/categories';
import { storeCategoryOptions } from '../utils/storeCategories';

const CANONICAL_STORE_CATEGORIES = [
  'Clothing & Fashion',
  'Footwear',
  'Accessories',
  'Beauty & Personal Care',
  'Electronics',
  'Gifts',
  'Home & Living',
];

describe('store categories', () => {
  it('exposes the full canonical store category list shared with the backend', () => {
    expect([...STORE_CATEGORIES]).toEqual(CANONICAL_STORE_CATEGORIES);
    expect(STORE_CATEGORIES).toBe(CATEGORY_DISPLAY_ORDER);
    expect(STORE_CATEGORIES).not.toContain('General Store');
  });

  it('always returns every canonical category for the partner form', () => {
    expect(storeCategoryOptions(undefined)).toEqual(CANONICAL_STORE_CATEGORIES);
    expect(storeCategoryOptions('')).toEqual(CANONICAL_STORE_CATEGORIES);
    expect(storeCategoryOptions('Footwear')).toEqual(CANONICAL_STORE_CATEGORIES);
  });

  it('preserves a legacy draft category as an additional first option', () => {
    const options = storeCategoryOptions('General Store');
    expect(options[0]).toBe('General Store');
    expect(options.slice(1)).toEqual(CANONICAL_STORE_CATEGORIES);
    expect(new Set(options).size).toBe(options.length);
  });

  it('does not duplicate a canonical current category', () => {
    const options = storeCategoryOptions('Gifts');
    expect(options.filter(category => category === 'Gifts')).toHaveLength(1);
  });
});
