import { describe, expect, it } from 'vitest';
import type { Product, VendorStore } from '../types';
import { buildSearchSuggestions, highlightSearchMatch } from '../utils/searchSuggestions';

const product = (overrides: Partial<Product> = {}): Product => ({
  id: 'p1', slug: 'rose-perfume', name: 'Rose Perfume', brand: 'Aura', department: 'women',
  category: 'Beauty & Personal Care', subcategory: 'Perfume', shortDescription: '', description: '', material: '',
  careInstructions: [], price: 499, originalPrice: 499, discount: 0, images: ['/product-placeholder.svg'],
  thumbnail: '/product-placeholder.svg', rating: 0, reviewCount: 0,
  variants: [{ id: 'v1', sku: 'sku1', size: 'One Size', colourName: 'Rose', stock: 5, available: true }],
  tags: ['fragrance'], returnWindowDays: 0, exchangeAvailable: false, vendorId: 's1', storeName: 'Aura Beauty', active: true,
  ...overrides,
});

const store = (overrides: Partial<VendorStore> = {}): VendorStore => ({
  id: 's1', slug: 'aura-beauty', storeName: 'Aura Beauty', category: 'Clothing & Fashion', address: 'Neemuch',
  pincode: '458441', city: 'Neemuch', deliveryMinutes: 60, description: 'Local beauty store', active: true, approved: true,
  createdAt: '2026-09-03T00:00:00Z', ...overrides,
});

describe('search suggestions', () => {
  it('returns exact routes for product, store, category and brand matches', () => {
    const products = [product()];
    const stores = [store()];
    expect(buildSearchSuggestions('rose', products, stores).find(item => item.type === 'product')?.href).toBe('/product/rose-perfume');
    expect(buildSearchSuggestions('aura', products, stores).find(item => item.type === 'store')?.href).toBe('/store/aura-beauty');
    expect(buildSearchSuggestions('beauty', products, stores).find(item => item.type === 'category')?.href)
      .toBe('/products?category=Beauty%20%26%20Personal%20Care');
    expect(buildSearchSuggestions('aura', products, stores).find(item => item.type === 'brand')?.href).toBe('/products?brand=Aura');
  });

  it('can match a product using brand/category/store metadata while keeping exact labels ranked first', () => {
    const results = buildSearchSuggestions('aura', [product()], [store()]);
    expect(results[0]).toMatchObject({ type: 'brand', label: 'Aura' });
    expect(results.some(item => item.type === 'store' && item.label === 'Aura Beauty')).toBe(true);
    expect(results.some(item => item.type === 'product' && item.label === 'Rose Perfume')).toBe(true);
  });

  it('excludes inactive products and unapproved/inactive stores', () => {
    expect(buildSearchSuggestions('rose', [product({ active: false })], [store({ approved: false })])).toEqual([]);
  });

  it('does not offer suggestions for one-character input', () => {
    expect(buildSearchSuggestions('r', [product()], [store()])).toEqual([]);
  });

  it('splits matching text for highlighting without changing the original casing', () => {
    expect(highlightSearchMatch('Rose Perfume', 'per')).toEqual([
      { text: 'Rose ', match: false }, { text: 'Per', match: true }, { text: 'fume', match: false },
    ]);
  });
});
