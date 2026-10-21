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
  'Groceries',
  'Home & Living',
  'Health & Pharmacy',
  'Health & Nutrition',
  'Baby Care',
  'Pet Supplies',
  'Mobile Accessories',
  'Automotive Accessories',
  'Toys & Games',
  'Stationery & Books',
  'Sports & Fitness',
  'Hardware & Tools',
  'General Store',
];

describe('store categories', () => {
  it('exposes the full canonical store category list shared with the backend', () => {
    expect([...STORE_CATEGORIES]).toEqual(CANONICAL_STORE_CATEGORIES);
    expect(STORE_CATEGORIES).toBe(CATEGORY_DISPLAY_ORDER);
    expect(STORE_CATEGORIES).toContain('General Store');
    expect(STORE_CATEGORIES).toContain('Health & Nutrition');
  });

  it('always returns every canonical category for the partner form', () => {
    expect(storeCategoryOptions(undefined)).toEqual(CANONICAL_STORE_CATEGORIES);
    expect(storeCategoryOptions('')).toEqual(CANONICAL_STORE_CATEGORIES);
    expect(storeCategoryOptions('Footwear')).toEqual(CANONICAL_STORE_CATEGORIES);
  });

  it('preserves a legacy draft category as an additional first option', () => {
    const options = storeCategoryOptions('Legacy Cafe');
    expect(options[0]).toBe('Legacy Cafe');
    expect(options.slice(1)).toEqual(CANONICAL_STORE_CATEGORIES);
    expect(new Set(options).size).toBe(options.length);
  });

  it('does not duplicate a canonical current category', () => {
    const options = storeCategoryOptions('Gifts');
    expect(options.filter(category => category === 'Gifts')).toHaveLength(1);
  });
});
