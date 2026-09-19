import { describe, expect, it } from 'vitest';
import type { Product, VendorStore } from '../types';
import { buildHomepageSections, selectHomepageCandidates, selectHomepageStores, selectTopPicks } from '../utils/homeMerchandising';

const product = (id: string, overrides: Partial<Product> = {}): Product => ({
  id,
  slug: id,
  name: id,
  brand: 'Local Brand',
  department: 'women',
  category: 'Clothing & Fashion',
  shortDescription: 'Local style',
  description: 'Local style',
  material: 'Cotton',
  careInstructions: [],
  price: 799,
  originalPrice: 799,
  discount: 0,
  images: ['/product-placeholder.svg'],
  thumbnail: '/product-placeholder.svg',
  rating: 4,
  reviewCount: 2,
  variants: [{ id: `${id}-v`, sku: `${id}-sku`, size: 'M', colourName: 'Blue', stock: 2, available: true }],
  tags: [], returnWindowDays: 0, exchangeAvailable: false,
  vendorId: 'store-1', storeName: 'Local Store', active: true,
  createdAt: '2026-09-04T00:00:00Z',
  ...overrides,
});
const store = (id: string, overrides: Partial<VendorStore> = {}): VendorStore => ({
  id, slug: id, storeName: id, category: 'Clothing & Fashion',
  address: 'Neemuch', pincode: '458441', city: 'Neemuch',
  deliveryMinutes: 60, description: 'Local store', active: true, approved: true,
  createdAt: '2026-09-04T00:00:00Z', ...overrides,
});

const monday = new Date('2026-09-07T06:30:00.000Z');
const saturday = new Date('2026-09-05T06:30:00.000Z');

describe('homepage merchandising', () => {
  it('keeps every product section bounded and preserves category balance after bulk new arrivals', () => {
    const bulkNew = Array.from({ length: 30 }, (_, index) => product(`new-${index}`, { newArrival: true }));
    const products = [
      ...bulkNew,
      product('men-1', { department: 'men' }),
      product('accessory-1', { category: 'Accessories' }),
      product('beauty-1', { category: 'Beauty & Personal Care' }),
      product('cheap-1', { price: 399 }),
    ];
    const sections = buildHomepageSections(products, 5);
    expect(sections.every(section => section.products.length <= 5)).toBe(true);
    expect(sections.find(section => section.id === 'new')?.products).toHaveLength(5);
    expect(sections.some(section => section.id === 'men')).toBe(true);
    expect(sections.some(section => section.id === 'accessories')).toBe(true);
    expect(sections.some(section => section.id === 'beauty')).toBe(true);
  });

  it('prefers unused alternatives before duplicating a product across rows', () => {
    const hero = product('hero', { newArrival: true, expressDelivery: true, featured: true });
    const newOnly = product('new-only', { newArrival: true });
    const expressOnly = product('express-only', { expressDelivery: true });
    const sections = buildHomepageSections([hero, newOnly, expressOnly], 1, saturday);
    const express = sections.find(section => section.id === 'express')?.products[0]?.id;
    const fresh = sections.find(section => section.id === 'new')?.products[0]?.id;
    expect(express).toBeTruthy();
    expect(fresh).toBeTruthy();
    expect(fresh).not.toBe(express);
  });


  it('hides Express merchandising on weekdays and includes every active product on weekends', () => {
    const normalStored = product('normal-stored', { deliveryType: 'normal', expressDelivery: false });
    expect(buildHomepageSections([normalStored], 5, monday).some(section => section.id === 'express')).toBe(false);
    expect(buildHomepageSections([normalStored], 5, saturday).find(section => section.id === 'express')?.products.map(item => item.id)).toEqual(['normal-stored']);
  });

  it('keeps the homepage candidate request bounded as catalogue size grows', () => {
    const products = Array.from({ length: 200 }, (_, index) => product(`p-${index}`, {
      newArrival: true, trending: true, expressDelivery: true, price: 399,
      department: index % 2 ? 'men' : 'women',
      category: index % 5 === 0 ? 'Accessories' : 'Clothing & Fashion',
    }));
    expect(selectHomepageCandidates(products, 8).length).toBeLessThanOrEqual(64);
  });

  it('spreads Top Picks across shops and categories instead of favoring one new batch', () => {
    const dominantBatch = Array.from({ length: 12 }, (_, index) => product(`beauty-batch-${index}`, {
      vendorId: 'beauty-store',
      storeName: 'Beauty Store',
      category: 'Beauty & Personal Care',
      department: 'women',
      newArrival: true,
      trending: true,
      featured: true,
      rating: 5,
      reviewCount: 50,
    }));
    const alternatives = [
      product('shoe-pick', { vendorId: 'shoe-store', storeName: 'Shoe Store', category: 'Footwear', department: 'men' }),
      product('watch-pick', { vendorId: 'watch-store', storeName: 'Watch Store', category: 'Watches', department: 'accessories' }),
      product('jeans-pick', { vendorId: 'fashion-store', storeName: 'Fashion Store', category: 'Clothing & Fashion', department: 'women' }),
      product('kids-pick', { vendorId: 'kids-store', storeName: 'Kids Store', category: 'Kids Wear', department: 'kids' }),
      product('jewellery-pick', { vendorId: 'jewel-store', storeName: 'Jewellery Store', category: 'Accessories', department: 'accessories' }),
    ];

    const picks = selectTopPicks([...dominantBatch, ...alternatives], 6, saturday);
    expect(new Set(picks.map(item => item.vendorId)).size).toBeGreaterThanOrEqual(5);
    expect(new Set(picks.map(item => item.category)).size).toBeGreaterThanOrEqual(5);
    expect(picks.filter(item => item.vendorId === 'beauty-store').length).toBeLessThanOrEqual(2);
  });

  it('keeps Weekend Express diverse across shops and categories', () => {
    const dominantBatch = Array.from({ length: 12 }, (_, index) => product(`express-batch-${index}`, {
      vendorId: 'beauty-store',
      storeName: 'Beauty Store',
      category: 'Beauty & Personal Care',
      newArrival: true,
      trending: true,
      featured: true,
      rating: 5,
      reviewCount: 50,
    }));
    const alternatives = [
      product('express-shoe', { vendorId: 'shoe-store', category: 'Footwear', department: 'men' }),
      product('express-watch', { vendorId: 'watch-store', category: 'Watches', department: 'accessories' }),
      product('express-jeans', { vendorId: 'fashion-store', category: 'Clothing & Fashion', department: 'women' }),
      product('express-kids', { vendorId: 'kids-store', category: 'Kids Wear', department: 'kids' }),
    ];

    const express = buildHomepageSections([...dominantBatch, ...alternatives], 5, saturday)
      .find(section => section.id === 'express')?.products || [];
    expect(express).toHaveLength(5);
    expect(new Set(express.map(item => item.vendorId)).size).toBe(5);
    expect(new Set(express.map(item => item.category)).size).toBe(5);
  });

  it('uses alternatives for Weekend Express before repeating Top Picks', () => {
    const products = Array.from({ length: 12 }, (_, index) => product(`mixed-${index}`, {
      vendorId: `store-${index}`,
      storeName: `Store ${index}`,
      category: `Category ${index}`,
      department: index % 2 ? 'men' : 'women',
    }));
    const topPicks = selectTopPicks(products, 5, saturday);
    const topPickIds = new Set(topPicks.map(item => item.id));
    const express = buildHomepageSections(products, 5, saturday, topPickIds)
      .find(section => section.id === 'express')?.products || [];

    expect(express).toHaveLength(5);
    expect(express.every(item => !topPickIds.has(item.id))).toBe(true);
  });

  it('keeps general catalogue categories in the bounded homepage candidate pool', () => {
    const kidsOnly = product('premium-kids', {
      vendorId: 'kids-store',
      category: 'Kids Wear',
      department: 'kids',
      price: 1299,
      newArrival: false,
      trending: false,
    });
    const candidates = selectHomepageCandidates([
      kidsOnly,
      product('women-fashion'),
      product('men-fashion', { department: 'men' }),
      product('beauty', { category: 'Beauty & Personal Care' }),
    ], 8, monday);
    expect(candidates.map(item => item.id)).toContain('premium-kids');
    expect(candidates.length).toBeLessThanOrEqual(64);
  });

  it('hides empty Beauty rows and shows them as soon as beauty inventory exists', () => {
    expect(buildHomepageSections([product('women')]).some(section => section.id === 'beauty')).toBe(false);
    expect(buildHomepageSections([product('beauty', { category: 'Beauty & Personal Care' })]).some(section => section.id === 'beauty')).toBe(true);
  });

  it('keeps legacy accessories-department products in the Accessories row', () => {
    const legacy = product('watch', { department: 'accessories', category: 'Watches' });
    const section = buildHomepageSections([legacy]).find(item => item.id === 'accessories');
    expect(section?.products.map(item => item.id)).toEqual(['watch']);
  });

  it('shows only approved active local stores and caps the row', () => {
    const stores = [
      ...Array.from({ length: 8 }, (_, index) => store(`active-${index}`, { rating: 5 - (index * 0.1) })),
      store('inactive', { active: false }),
      store('unapproved', { approved: false }),
    ];
    const selected = selectHomepageStores(stores, 5);
    expect(selected).toHaveLength(5);
    expect(selected.some(item => item.id === 'inactive' || item.id === 'unapproved')).toBe(false);
  });

  it('keeps every approved active local store when the homepage rail is uncapped', () => {
    const stores = [
      ...Array.from({ length: 10 }, (_, index) => store(`active-${index}`, { rating: 5 - (index * 0.1) })),
      store('inactive', { active: false }),
      store('unapproved', { approved: false }),
    ];
    const selected = selectHomepageStores(stores);
    expect(selected).toHaveLength(10);
    expect(selected.some(item => item.id === 'inactive' || item.id === 'unapproved')).toBe(false);
  });
});
