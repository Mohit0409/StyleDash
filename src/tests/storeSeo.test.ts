import { describe, expect, it } from 'vitest';
import type { VendorStore } from '../types';
import { buildStoreSeo } from '../utils/storeSeo';

const store: VendorStore = {
  id: 'store-a',
  slug: 'prime-time-abc123',
  storeName: 'Prime Time',
  category: 'Accessories',
  address: 'Dana Gali Corner',
  pincode: '458441',
  city: 'Neemuch',
  deliveryMinutes: 60,
  description: 'Local watches and accessories',
  active: true,
  approved: true,
  createdAt: '2026-10-01T00:00:00Z',
  productCount: 12,
};

describe('store search metadata', () => {
  it('includes a genuine name, category, city, canonical storefront and postal address', () => {
    const seo = buildStoreSeo(store);
    expect(seo.title).toContain('Prime Time');
    expect(seo.title).toContain('Accessories');
    expect(seo.title).toContain('Neemuch');
    expect(seo.noIndex).toBe(false);
    expect(seo.jsonLd).toMatchObject({
      '@type': 'Store',
      name: 'Prime Time',
      url: 'https://vibe4you.in/store/prime-time-abc123',
      address: {
        '@type': 'PostalAddress',
        streetAddress: 'Dana Gali Corner',
        addressLocality: 'Neemuch',
        postalCode: '458441',
        addressCountry: 'IN',
      },
    });
  });

  it('keeps empty storefronts out of search indexes', () => {
    expect(buildStoreSeo({ ...store, productCount: 0 }).noIndex).toBe(true);
  });

  it('does not invent review ratings, telephone numbers, or opening hours', () => {
    const seo = buildStoreSeo(store);
    expect(seo.jsonLd).not.toHaveProperty('aggregateRating');
    expect(seo.jsonLd).not.toHaveProperty('telephone');
    expect(seo.jsonLd).not.toHaveProperty('openingHours');
  });

  it('limits long text descriptions for readable search snippets', () => {
    const seo = buildStoreSeo({ ...store, description: 'Watch collections. '.repeat(200) });
    expect(seo.description.length).toBeLessThanOrEqual(180);
  });
});
