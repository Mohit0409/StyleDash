import { describe, expect, it } from 'vitest';
import type { Product } from '../types';
import { rankSimilarProducts, similarProductScore } from '../utils/similarProducts';

const product = (id: string, overrides: Partial<Product> = {}): Product => ({
  id,
  slug: id,
  name: overrides.name || id,
  brand: 'Local Brand',
  department: 'unisex',
  category: 'Clothing & Fashion',
  shortDescription: '',
  description: '',
  material: '',
  careInstructions: [],
  price: 500,
  originalPrice: 600,
  discount: 17,
  images: ['/product-placeholder.svg'],
  thumbnail: '/product-placeholder.svg',
  rating: 0,
  reviewCount: 0,
  variants: [],
  tags: ['local-shop'],
  returnWindowDays: 0,
  exchangeAvailable: false,
  vendorId: 'vendor',
  active: true,
  ...overrides,
});

describe('similar products ranking', () => {
  const current = product('current', {
    category: 'Footwear',
    subcategory: 'Sneakers',
    department: 'men',
    brand: 'Campus',
    price: 1000,
  });

  it('prefers close taxonomy matches in priority order', () => {
    const sameSubcategory = product('a-sub', { category: 'Footwear', subcategory: 'Sneakers', department: 'women', brand: 'Other', price: 4000 });
    const sameCategory = product('b-cat', { category: 'Footwear', subcategory: 'Loafers', department: 'women', brand: 'Other', price: 4000 });
    const sameDepartment = product('c-dept', { category: 'Accessories', subcategory: 'Belts', department: 'men', brand: 'Other', price: 4000 });
    const unrelated = product('d-none', { category: 'Electronics', subcategory: 'Audio', department: 'unisex', brand: 'Other', price: 4000, tags: [] });

    const ranked = rankSimilarProducts(current, [unrelated, sameDepartment, sameCategory, sameSubcategory, current]);
    expect(ranked.map(item => item.id)).toEqual(['a-sub', 'b-cat', 'c-dept', 'd-none']);
  });

  it('excludes the current product and inactive products and never duplicates', () => {
    const catalogue = [
      current,
      product('inactive', { category: 'Footwear', subcategory: 'Sneakers', active: false }),
      product('dupe', { category: 'Footwear', subcategory: 'Sneakers' }),
      product('dupe', { category: 'Footwear', subcategory: 'Sneakers' }),
    ];
    const ranked = rankSimilarProducts(current, catalogue);
    expect(ranked.map(item => item.id)).toEqual(['dupe']);
    expect(ranked.some(item => item.id === 'current')).toBe(false);
  });

  it('falls back to broader catalogue entries when the subcategory is sparse', () => {
    const sparse = product('sparse', { category: 'Gifts', subcategory: 'Rare Coins', department: 'unisex' });
    const broader = Array.from({ length: 15 }, (_, index) => product(`b-${index}`, { category: 'Clothing & Fashion' }));
    const ranked = rankSimilarProducts(sparse, [sparse, ...broader], 10);
    expect(ranked).toHaveLength(10);
    expect(ranked.some(item => item.id === 'sparse')).toBe(false);
  });

  it('rewards brand match and price proximity', () => {
    const base = { category: 'Footwear', subcategory: 'Sneakers' };
    const brandMatch = product('brand', { ...base, brand: 'Campus', price: 5000 });
    const priceMatch = product('price', { ...base, brand: 'Other', price: 1100 });
    const neither = product('neither', { ...base, brand: 'Other', price: 5000 });
    expect(similarProductScore(current, brandMatch)).toBeGreaterThan(similarProductScore(current, neither));
    expect(similarProductScore(current, priceMatch)).toBeGreaterThan(similarProductScore(current, neither));
  });

  it('is deterministic for equal scores using stable tie-breaks', () => {
    const first = rankSimilarProducts(current, [product('z-last'), product('a-first')]).map(item => item.id);
    const second = rankSimilarProducts(current, [product('a-first'), product('z-last')]).map(item => item.id);
    expect(first).toEqual(['z-last', 'a-first']); // catalogue position wins over name
    expect(second).toEqual(['a-first', 'z-last']);
  });
});
