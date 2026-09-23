import { describe, expect, it } from 'vitest';
import type { Product } from '../types';
import { buildCatalogueTaxonomy } from '../utils/catalogTaxonomy';

const product = (
  id: string,
  category: string,
  subcategory?: string,
  active = true,
): Product => ({
  id,
  slug: id,
  name: id,
  brand: 'Local Brand',
  department: 'unisex',
  category,
  subcategory,
  shortDescription: '',
  description: '',
  material: '',
  careInstructions: [],
  price: 100,
  originalPrice: 100,
  discount: 0,
  images: ['/product-placeholder.svg'],
  thumbnail: '/product-placeholder.svg',
  rating: 0,
  reviewCount: 0,
  variants: [],
  tags: ['local-shop'],
  returnWindowDays: 0,
  exchangeAvailable: false,
  vendorId: 'vendor',
  active,
});

describe('catalogue taxonomy', () => {
  it('derives categories and positive subcategory counts from active products', () => {
    const taxonomy = buildCatalogueTaxonomy([
      product('shoe-1', 'Footwear', 'Sneakers'),
      product('shoe-2', 'Footwear', 'Sneakers'),
      product('shoe-3', 'Footwear', 'Sliders'),
      product('gift-1', 'Gifts', 'Gift Hampers'),
      product('hidden', 'Electronics', 'Audio', false),
    ]);

    expect(taxonomy).toEqual([
      {
        name: 'Footwear',
        count: 3,
        subcategories: [
          { name: 'Sliders', count: 1 },
          { name: 'Sneakers', count: 2 },
        ],
      },
      {
        name: 'Gifts',
        count: 1,
        subcategories: [{ name: 'Gift Hampers', count: 1 }],
      },
    ]);
    expect(taxonomy.flatMap(category => category.subcategories).every(item => item.count > 0)).toBe(true);
  });

  it('keeps products without a subcategory in the parent category count', () => {
    expect(buildCatalogueTaxonomy([product('home-1', 'Home & Living')])).toEqual([
      { name: 'Home & Living', count: 1, subcategories: [] },
    ]);
  });
});
