import type { Product, VendorStore } from '../types';

export type SearchSuggestionType = 'product' | 'store' | 'category' | 'brand';

export interface SearchSuggestion {
  id: string;
  type: SearchSuggestionType;
  label: string;
  secondary: string;
  href: string;
  score: number;
}

export interface HighlightPart {
  text: string;
  match: boolean;
}

const normalize = (value: string): string => value.trim().toLocaleLowerCase();

const labelScore = (label: string, query: string): number | null => {
  const normalized = normalize(label);
  if (!normalized) return null;
  if (normalized === query) return 0;
  if (normalized.startsWith(query)) return 1;
  const index = normalized.indexOf(query);
  if (index >= 0) return 2 + Math.min(index, 8) / 10;
  return null;
};

const bestScore = (label: string, keywords: Array<string | undefined>, query: string): number | null => {
  const direct = labelScore(label, query);
  if (direct !== null) return direct;
  const keywordMatch = keywords
    .filter((value): value is string => Boolean(value))
    .map(value => labelScore(value, query))
    .filter((value): value is number => value !== null)
    .sort((a, b) => a - b)[0];
  return keywordMatch === undefined ? null : 4 + keywordMatch;
};

const uniqueByLabel = (values: string[]): string[] => {
  const seen = new Set<string>();
  return values.filter(value => {
    const key = normalize(value);
    if (!key || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
};

const TYPE_PRIORITY: Record<SearchSuggestionType, number> = {
  product: 0,
  store: 1,
  category: 2,
  brand: 3,
};

export const buildSearchSuggestions = (
  queryValue: string,
  products: Product[],
  stores: VendorStore[],
  limit = 10,
): SearchSuggestion[] => {
  const query = normalize(queryValue);
  if (query.length < 2) return [];

  const activeProducts = products.filter(product => product.active === true);
  const activeStores = stores.filter(store => store.active === true && store.approved === true);
  const suggestions: SearchSuggestion[] = [];

  for (const product of activeProducts) {
    const score = bestScore(product.name, [
      product.brand,
      product.category,
      product.subcategory,
      product.storeName,
      ...product.tags,
    ], query);
    if (score === null) continue;
    suggestions.push({
      id: `product:${product.id}`,
      type: 'product',
      label: product.name,
      secondary: [product.brand, product.storeName].filter(Boolean).join(' | '),
      href: `/product/${encodeURIComponent(product.slug || product.id)}`,
      score,
    });
  }

  for (const store of activeStores) {
    const score = bestScore(store.storeName, [store.category, store.description, store.address, store.city], query);
    if (score === null) continue;
    suggestions.push({
      id: `store:${store.id}`,
      type: 'store',
      label: store.storeName,
      secondary: [store.category, store.city].filter(Boolean).join(' | '),
      href: `/store/${encodeURIComponent(store.slug || store.id)}`,
      score,
    });
  }

  for (const category of uniqueByLabel(activeProducts.map(product => product.category))) {
    const score = labelScore(category, query);
    if (score === null) continue;
    suggestions.push({
      id: `category:${normalize(category)}`,
      type: 'category',
      label: category,
      secondary: 'Category',
      href: `/products?category=${encodeURIComponent(category)}`,
      score,
    });
  }

  for (const brand of uniqueByLabel(activeProducts.map(product => product.brand))) {
    const score = labelScore(brand, query);
    if (score === null) continue;
    suggestions.push({
      id: `brand:${normalize(brand)}`,
      type: 'brand',
      label: brand,
      secondary: 'Brand',
      href: `/products?brand=${encodeURIComponent(brand)}`,
      score,
    });
  }

  return suggestions
    .sort((a, b) => a.score - b.score || TYPE_PRIORITY[a.type] - TYPE_PRIORITY[b.type] || a.label.localeCompare(b.label))
    .slice(0, Math.max(1, limit));
};

export const highlightSearchMatch = (value: string, queryValue: string): HighlightPart[] => {
  const query = queryValue.trim();
  if (!query) return [{ text: value, match: false }];
  const index = value.toLocaleLowerCase().indexOf(query.toLocaleLowerCase());
  if (index < 0) return [{ text: value, match: false }];
  const parts: HighlightPart[] = [];
  if (index > 0) parts.push({ text: value.slice(0, index), match: false });
  parts.push({ text: value.slice(index, index + query.length), match: true });
  if (index + query.length < value.length) parts.push({ text: value.slice(index + query.length), match: false });
  return parts;
};
