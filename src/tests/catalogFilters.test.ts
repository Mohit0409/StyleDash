import { describe, expect, it } from 'vitest';
import type { Product } from '../types';
import {
  availableBrandOptions,
  availableCategoryOptions,
  availableSizeOptions,
  matchesCatalogueProduct,
  type CatalogueFilterState,
} from '../utils/catalogFilters';

const makeProduct = (overrides: Partial<Product> & Pick<Product, 'id' | 'brand' | 'department' | 'category'>): Product => ({
  id: overrides.id,
  slug: overrides.slug ?? overrides.id,
  name: overrides.name ?? overrides.id,
  brand: overrides.brand,
  department: overrides.department,
  category: overrides.category,
  shortDescription: 'Local product',
  description: 'Local product description',
  material: 'Not specified',
  careInstructions: [],
  price: overrides.price ?? 499,
  originalPrice: overrides.originalPrice ?? 499,
  discount: overrides.discount ?? 0,
  images: ['/product-placeholder.svg'],
  thumbnail: '/product-placeholder.svg',
  rating: 0,
  reviewCount: 0,
  variants: overrides.variants ?? [{ id: `${overrides.id}-v1`, sku: `${overrides.id}-sku`, size: 'M', colourName: 'Multi', stock: 1, available: true }],
  tags: overrides.tags ?? ['local-shop'],
  returnWindowDays: 0,
  exchangeAvailable: false,
  vendorId: 'vendor-1',
  storeName: overrides.storeName ?? 'Local Store',
  active: overrides.active ?? true,
  subcategory: overrides.subcategory,
  collection: overrides.collection,
  badge: overrides.badge,
  newArrival: overrides.newArrival,
  trending: overrides.trending,
  featured: overrides.featured,
  expressDelivery: overrides.expressDelivery,
});

const baseFilters = (overrides: Partial<CatalogueFilterState> = {}): CatalogueFilterState => ({
  department: 'all',
  category: 'all',
  subcategory: 'all',
  brand: 'all',
  size: 'all',
  maxPrice: 4999,
  searchQuery: '',
  filterBadge: '',
  expressFilterActive: false,
  ...overrides,
});

const products: Product[] = [
  makeProduct({
    id: 'goutam-men', brand: 'Goutam Shoes', department: 'men', category: 'Footwear',
    variants: [
      { id: 'g6', sku: 'g6', size: 'UK 6', colourName: 'Black', stock: 3, available: true },
      { id: 'g7', sku: 'g7', size: 'UK 7', colourName: 'Black', stock: 0, available: false },
    ],
  }),
  makeProduct({
    id: 'campus-men', brand: 'Campus', department: 'men', category: 'Footwear',
    variants: [{ id: 'c8', sku: 'c8', size: 'UK 8', colourName: 'Blue', stock: 2, available: true }],
    expressDelivery: true,
  }),
  makeProduct({
    id: 'nakoda-women', brand: 'Nakoda Imitation Jewellery', department: 'women', category: 'Accessories',
    variants: [{ id: 'n1', sku: 'n1', size: 'One Size', colourName: 'Gold', stock: 5, available: true }],
  }),
];

describe('catalogue dynamic facets', () => {
  it('keeps audience departments separate from merchandise categories', () => {
    expect(availableCategoryOptions(products, baseFilters())).toEqual(['Accessories', 'Footwear']);
    expect(availableCategoryOptions(products, baseFilters({ department: 'men' }))).toEqual(['Footwear']);
    expect(products.filter(product => matchesCatalogueProduct(product, baseFilters({ department: 'women', category: 'Accessories' }))).map(product => product.id)).toEqual(['nakoda-women']);
    expect(products.filter(product => matchesCatalogueProduct(product, baseFilters({ department: 'men', category: 'Footwear' }))).map(product => product.id)).toEqual(['goutam-men', 'campus-men']);
  });

  it('derives brands from products in the active catalogue scope', () => {
    expect(availableBrandOptions(products, baseFilters())).toEqual([
      'Campus', 'Goutam Shoes', 'Nakoda Imitation Jewellery',
    ]);
    expect(availableBrandOptions(products, baseFilters({ department: 'men' }))).toEqual([
      'Campus', 'Goutam Shoes',
    ]);
    expect(availableBrandOptions(products, baseFilters({ department: 'men', size: 'UK 8' }))).toEqual(['Campus']);
  });

  it('derives only actually available sizes and respects other active filters', () => {
    expect(availableSizeOptions(products, baseFilters())).toEqual(['UK 6', 'UK 8', 'One Size']);
    expect(availableSizeOptions(products, baseFilters({ department: 'men' }))).toEqual(['UK 6', 'UK 8']);
    expect(availableSizeOptions(products, baseFilters({ brand: 'Goutam Shoes' }))).toEqual(['UK 6']);
    expect(availableSizeOptions(products, baseFilters({ department: 'women' }))).toEqual(['One Size']);
  });

  it('does not apply the express product filter when weekday availability disables it', () => {
    const weekday = baseFilters({ filterBadge: 'express', expressFilterActive: false });
    expect(products.filter(product => matchesCatalogueProduct(product, weekday))).toHaveLength(3);
    const weekend = baseFilters({ filterBadge: 'express', expressFilterActive: true });
    expect(products.filter(product => matchesCatalogueProduct(product, weekend)).map(product => product.id)).toEqual(['campus-men']);
  });
});
