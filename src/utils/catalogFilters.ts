import type { Product } from '../types';

export interface CatalogueFilterState {
  department: string;
  category: string;
  subcategory: string;
  brand: string;
  size: string;
  maxPrice: number;
  searchQuery: string;
  filterBadge: string;
  expressFilterActive: boolean;
}

interface MatchOptions {
  ignoreCategory?: boolean;
  ignoreBrand?: boolean;
  ignoreSize?: boolean;
}

const matchesSearch = (product: Product, searchQuery: string): boolean => {
  if (!searchQuery.trim()) return true;
  const query = searchQuery.trim().toLocaleLowerCase();
  return (
    product.name.toLocaleLowerCase().includes(query)
    || product.brand.toLocaleLowerCase().includes(query)
    || product.category.toLocaleLowerCase().includes(query)
    || (product.subcategory?.toLocaleLowerCase().includes(query) ?? false)
    || product.tags.some(tag => tag.toLocaleLowerCase().includes(query))
    || (product.storeName?.toLocaleLowerCase().includes(query) ?? false)
  );
};

export const matchesCatalogueProduct = (
  product: Product,
  filters: CatalogueFilterState,
  options: MatchOptions = {},
): boolean => {
  if (product.active !== true) return false;
  if (filters.department !== 'all' && product.department !== filters.department) return false;
  if (!options.ignoreCategory && filters.category !== 'all' && product.category !== filters.category) return false;
  if (filters.subcategory !== 'all' && product.subcategory !== filters.subcategory) return false;
  if (!options.ignoreBrand && filters.brand !== 'all' && product.brand !== filters.brand) return false;
  if (
    !options.ignoreSize
    && filters.size !== 'all'
    && !product.variants.some(variant => variant.size === filters.size && variant.available === true)
  ) return false;
  if (product.price > filters.maxPrice) return false;
  if (!matchesSearch(product, filters.searchQuery)) return false;

  if (filters.filterBadge === 'express' && filters.expressFilterActive && !product.expressDelivery) return false;
  if (filters.filterBadge === 'new' && !product.newArrival) return false;
  if (filters.filterBadge === 'sale' && product.discount === 0) return false;
  return true;
};

const uniqueSorted = (values: string[]): string[] =>
  [...new Set(values.map(value => value.trim()).filter(Boolean))]
    .sort((a, b) => a.localeCompare(b, undefined, { sensitivity: 'base', numeric: true }));


export const availableCategoryOptions = (
  products: Product[],
  filters: CatalogueFilterState,
): string[] => uniqueSorted(
  products
    .filter(product => matchesCatalogueProduct(product, filters, { ignoreCategory: true }))
    .map(product => product.category),
);

export const availableBrandOptions = (
  products: Product[],
  filters: CatalogueFilterState,
): string[] => uniqueSorted(
  products
    .filter(product => matchesCatalogueProduct(product, filters, { ignoreBrand: true }))
    .map(product => product.brand),
);

const APPAREL_SIZE_ORDER = new Map(
  ['XXS', 'XS', 'S', 'M', 'L', 'XL', 'XXL', 'XXXL'].map((value, index) => [value, index]),
);

const parsedShoeSize = (value: string): { system: number; value: number } | null => {
  const match = value.trim().match(/^(UK|US|EU)\s*(\d+(?:\.5)?)$/i);
  if (!match) return null;
  const system = { UK: 0, US: 1, EU: 2 }[match[1].toUpperCase() as 'UK' | 'US' | 'EU'];
  return { system, value: Number(match[2]) };
};

export const compareProductSizes = (a: string, b: string): number => {
  const aApparel = APPAREL_SIZE_ORDER.get(a.toUpperCase());
  const bApparel = APPAREL_SIZE_ORDER.get(b.toUpperCase());
  if (aApparel !== undefined || bApparel !== undefined) {
    if (aApparel === undefined) return 1;
    if (bApparel === undefined) return -1;
    return aApparel - bApparel;
  }
  if (a.toLocaleLowerCase() === 'one size' || b.toLocaleLowerCase() === 'one size') {
    if (a.toLocaleLowerCase() === 'one size' && b.toLocaleLowerCase() === 'one size') return 0;
    return a.toLocaleLowerCase() === 'one size' ? 1 : -1;
  }
  const aShoe = parsedShoeSize(a);
  const bShoe = parsedShoeSize(b);
  if (aShoe || bShoe) {
    if (!aShoe) return 1;
    if (!bShoe) return -1;
    return aShoe.system - bShoe.system || aShoe.value - bShoe.value;
  }
  return a.localeCompare(b, undefined, { sensitivity: 'base', numeric: true });
};

export const availableSizeOptions = (
  products: Product[],
  filters: CatalogueFilterState,
): string[] => {
  const sizes = products
    .filter(product => matchesCatalogueProduct(product, filters, { ignoreSize: true }))
    .flatMap(product => product.variants)
    .filter(variant => variant.available === true)
    .map(variant => variant.size.trim())
    .filter(Boolean);
  return [...new Set(sizes)].sort(compareProductSizes);
};
