import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
// Product cards need cart and wishlist providers; this test only checks headings.
vi.mock('../components/ProductCard', () => ({
  ProductCard: ({ product }: { product: { name: string } }) => <div>{product.name}</div>,
}));

import { HomepageMerchandising } from '../components/HomepageMerchandising';
import type { Product } from '../types';

const product = (id: string, category: string): Product => ({
  id,
  slug: id,
  name: id,
  brand: 'Local Brand',
  department: 'women',
  category,
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
});

const CATEGORY_ICONS: Array<[string, string]> = [
  ['Clothing & Fashion', 'lucide-shirt'],
  ['Footwear', 'lucide-footprints'],
  ['Accessories', 'lucide-watch'],
  ['Beauty & Personal Care', 'lucide-sparkles'],
  ['Electronics', 'lucide-smartphone'],
  ['Gifts', 'lucide-gift'],
  ['Home & Living', 'lucide-sofa'],
];

describe('homepage section icons', () => {
  const products = CATEGORY_ICONS.flatMap(([category], index) =>
    [0, 1, 2, 3].map(n => product(`p-${index}-${n}`, category)));
  const html = renderToStaticMarkup(
    <MemoryRouter>
      <HomepageMerchandising products={products} loading={false} />
    </MemoryRouter>,
  );

  it.each(CATEGORY_ICONS)('shows a relevant icon for %s', (_category, iconClass) => {
    expect(html).toContain(iconClass);
  });

  it('never falls back to the generic diamond icon', () => {
    expect(html).not.toContain('lucide-gem');
  });
});
