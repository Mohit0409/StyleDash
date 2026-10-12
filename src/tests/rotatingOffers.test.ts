import { describe, expect, it } from 'vitest';
import type { Product } from '../types';
import { neemuchCalendarKeys, selectRotatingOffers, verifiedDiscountPercent } from '../utils/rotatingOffers';
import { HOME_PROMO_SLIDES } from '../data/homePromoSlides';

const product = (id: number, changes: Partial<Product> = {}): Product => ({
  id: `product-${id}`,
  slug: `product-${id}`,
  name: `Product ${id}`,
  price: 100,
  originalPrice: 200,
  discount: 0,
  active: true,
  vendorId: `store-${id % 8}`,
  variants: [{ id: `variant-${id}`, available: true }],
  ...changes,
} as Product);

describe('homepage promotional navigation', () => {
  it('replaces the three department cards with categories, offers and newest stores', () => {
    expect(HOME_PROMO_SLIDES).toHaveLength(6);
    expect(HOME_PROMO_SLIDES.map(slide => slide.id)).toEqual([
      'shop-local', 'categories', 'offers', 'new-shops', 'beauty', 'budget',
    ]);
    expect(HOME_PROMO_SLIDES.map(slide => slide.targetUrl)).toEqual([
      '/stores',
      '/categories',
      '/offers',
      '/stores?sort=newest',
      '/products?category=Beauty%20%26%20Personal%20Care',
      '/products?maxPrice=499',
    ]);
    expect(HOME_PROMO_SLIDES.every(slide => slide.imageUrl.startsWith('https://images.unsplash.com/'))).toBe(true);
  });
});

describe('rotating offers', () => {
  it('uses the Neemuch calendar day, Monday week and month', () => {
    expect(neemuchCalendarKeys(new Date('2026-10-11T20:00:00Z'))).toEqual({
      today: '2026-10-12',
      week: '2026-10-12',
      month: '2026-10',
    });
    expect(neemuchCalendarKeys(new Date('2026-11-01T00:00:00Z')).month).toBe('2026-11');
  });

  it('rejects fabricated discounts, inactive stock and sold-out products', () => {
    const products = [
      product(1, { price: 100, originalPrice: 200, discount: 0 }),
      product(2, { price: 201, originalPrice: 200, discount: 99 }),
      product(3, { price: 100, originalPrice: 200, active: false }),
      product(4, { price: 100, originalPrice: 200, variants: [{ id: 'out', available: false }] as Product['variants'] }),
      product(5, { price: 0, originalPrice: 200 }),
    ];
    const selected = selectRotatingOffers(products, new Date('2026-10-12T10:00:00Z'));
    expect(selected.flatMap(section => section.products.map(item => item.id))).toEqual(['product-1']);
    expect(selected[0].products[0].discount).toBe(50);
    expect(verifiedDiscountPercent(product(2, { price: 250, originalPrice: 200 }))).toBe(0);
  });

  it('gives each period distinct products without repeating them', () => {
    const items = Array.from({ length: 35 }, (_, index) => product(index + 1, {
      price: 100 + index,
      originalPrice: 240,
    }));
    const sections = selectRotatingOffers(items, new Date('2026-10-12T15:00:00Z'));
    expect(sections.map(item => item.title)).toEqual([
      "Today's Top Offers", 'Weekly Top Offers', 'Monthly Top Offers',
    ]);
    expect(sections.map(item => item.products.length)).toEqual([8, 8, 8]);
    expect(new Set(sections.flatMap(section => section.products.map(item => item.id))).size).toBe(24);
  });

  it('keeps selection stable during a period and never adds offers for a zero limit', () => {
    const items = Array.from({ length: 20 }, (_, index) => product(index));
    const morning = selectRotatingOffers(items, new Date('2026-10-12T04:00:00Z'));
    const evening = selectRotatingOffers(items, new Date('2026-10-12T13:00:00Z'));
    expect(morning).toEqual(evening);
    expect(selectRotatingOffers(items, new Date('2026-10-12T04:00:00Z'), 0)
      .every(section => section.products.length === 0)).toBe(true);
  });
});
