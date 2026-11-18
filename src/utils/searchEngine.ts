import type { Product, VendorStore } from '../types';
import { normalizeLocalShoppingQuery } from './localSearch';

/**
 * Lightweight, deterministic client-side ranking for the published catalogue.
 * No third-party search service, user profiles, or payment/customer data.
 */
const SYNONYMS: Record<string, string> = {
  watch: 'watch', watches: 'watch', wristwatch: 'watch', wristwatches: 'watch',
  ghadi: 'watch', ghadiyan: 'watch',
  shoe: 'footwear', shoes: 'footwear', sneaker: 'footwear', sneakers: 'footwear',
  joota: 'footwear', footwear: 'footwear',
  sandal: 'sandal', sandals: 'sandal', chappal: 'sandal', slippers: 'sandal',
  mobile: 'phone', mobiles: 'phone', smartphone: 'phone', smartphones: 'phone',
  phone: 'phone', phones: 'phone',
  case: 'cover', cases: 'cover', cover: 'cover', covers: 'cover',
  tshirt: 'tshirt', tshirts: 'tshirt', tee: 'tshirt', tees: 'tshirt',
  saree: 'saree', sarees: 'saree', sari: 'saree', saris: 'saree',
  perfume: 'perfume', perfumes: 'perfume', fragrance: 'perfume',
  bag: 'bag', bags: 'bag',
};
const QUERY_FILLER = new Set(['buy', 'online', 'best', 'shop', 'shops', 'store', 'stores']);
const WORDS = /[\p{L}\p{N}]+/gu;

const clean = (value: string): string => value.normalize('NFKD')
  .replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('en-IN')
  .replace(/\bt[\s-]+shirts?\b/gu, 'tshirt')
  .replace(/\s+/g, ' ').trim();

const words = (value: string): string[] => clean(value).match(WORDS) || [];
const canon = (word: string): string => SYNONYMS[word] || word;

export interface SearchQuery {
  tokens: string[];
  compactModels: string[];
  phrase: string;
}

const QUERY_CACHE = new Map<string, SearchQuery>();
export const parseSearchQuery = (input: string): SearchQuery => {
  const cached = QUERY_CACHE.get(input);
  if (cached) return cached;
  const phrase = clean(normalizeLocalShoppingQuery(input)).slice(0, 120);
  const tokens = [...new Set(words(phrase).filter(t => !QUERY_FILLER.has(t)))].slice(0, 7);
  // Keep alphanumeric model numbers intact, e.g. "F-91W" => "f91w".
  const compactModels = new Set(tokens.filter(t => t.length >= 3 && /\d/u.test(t) && /\p{L}/u.test(t)));
  const joined = tokens.join('');
  if (joined.length >= 4 && joined.length <= 25 && /\d/u.test(joined) && /\p{L}/u.test(joined)) {
    compactModels.add(joined);
  }
  const parsed = { tokens, compactModels: [...compactModels], phrase };
  if (QUERY_CACHE.size >= 32) QUERY_CACHE.clear();
  QUERY_CACHE.set(input, parsed);
  return parsed;
};

type Field = { weight: number; text: string; tokens: string[]; compact: string };
type Indexed = { fields: Field[]; name: string; brand: string };
const productCache = new WeakMap<Product, Indexed>();
const storeCache = new WeakMap<VendorStore, Indexed>();

const field = (raw: string | undefined, weight: number): Field => {
  const text = clean(raw || '');
  const tokens = words(text).slice(0, 80);
  return { weight, text, tokens, compact: tokens.join('') };
};

const productIndex = (product: Product): Indexed => {
  const hit = productCache.get(product);
  if (hit) return hit;
  const fields = [
    field(product.name, 24),
    field(product.brand, 16),
    field(product.category, 11),
    field(product.subcategory, 12),
    field(product.storeName, 12),
    field(product.slug, 9),
    field(product.tags.join(' '), 9),
    field(product.variants.map(v => [v.sku, v.colourName].join(' ')).join(' '), 9),
    field(product.shortDescription, 3),
  ];
  const result = { fields, name: clean(product.name), brand: clean(product.brand) };
  productCache.set(product, result);
  return result;
};

const storeIndex = (store: VendorStore): Indexed => {
  const hit = storeCache.get(store);
  if (hit) return hit;
  const fields = [
    field(store.storeName, 24),
    field(store.category, 13),
    field(store.description, 5),
    field(store.city, 3),
  ];
  const result = { fields, name: clean(store.storeName), brand: '' };
  storeCache.set(store, result);
  return result;
};

// Bounded Damerau-Levenshtein: a single swapped letter ("caiso") counts as one.
const typoDistance = (a: string, b: string, limit: number): number => {
  if (Math.abs(a.length - b.length) > limit) return limit + 1;
  let previous2: number[] | undefined;
  let previous = Array.from({ length: b.length + 1 }, (_, i) => i);
  for (let i = 1; i <= a.length; i++) {
    const current = [i];
    let min = i;
    for (let j = 1; j <= b.length; j++) {
      let value = Math.min(
        current[j - 1] + 1,
        previous[j] + 1,
        previous[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1),
      );
      if (previous2 && i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1]) {
        value = Math.min(value, previous2[j - 2] + 1);
      }
      current.push(value);
      min = Math.min(min, value);
    }
    if (min > limit) return limit + 1;
    previous2 = previous;
    previous = current;
  }
  return previous[b.length];
};

const directQuality = (query: string, word: string): number => {
  if (word === query) return 6;
  if (canon(word) === canon(query)) return 5;
  if (query.length >= 2 && word.startsWith(query)) return 4;
  // Never match short brand words inside unrelated longer words:
  // "casio" is a substring of "occasion". Prefix matching remains allowed.
  if (query.length >= 6 && word.length <= query.length + 3 && word.includes(query)) return 2;
  return 0;
};

const scoreIndexed = (indexed: Indexed, query: SearchQuery): number | null => {
  if (!query.tokens.length) return null;
  let score = 0;
  for (const token of query.tokens) {
    let best = 0;
    for (const candidate of indexed.fields) {
      if (!candidate.tokens.length) continue;
      for (const word of candidate.tokens) {
        const quality = directQuality(token, word);
        if (quality) best = Math.max(best, candidate.weight * quality);
      }
      // Punctuation-insensitive alphanumeric model ID: F91W vs F-91W.
      if (/\d/u.test(token) && /\p{L}/u.test(token) && token.length >= 3
        && candidate.compact.includes(token)) {
        best = Math.max(best, candidate.weight * 5);
      }
    }
    if (!best && token.length >= 4 && !/\d/u.test(token)) {
      // Typos are low-ranked and only considered after literal/synonym matching.
      const limit = token.length >= 8 ? 2 : 1;
      for (const candidate of indexed.fields.slice(0, 5)) {
        for (const word of candidate.tokens) {
          if (word.length < 4 || !/\p{L}/u.test(word) || /\d/u.test(word)) continue;
          if (typoDistance(token, word, limit) <= limit) {
            best = Math.max(best, candidate.weight * (limit === 1 ? 1.6 : 1));
          }
        }
      }
    }
    if (!best) return null; // All significant words must match somewhere.
    score += best;
  }

  if (indexed.name === query.phrase) score += 250;
  else if (indexed.name.startsWith(query.phrase)) score += 110;
  else if (indexed.name.includes(query.phrase)) score += 40;
  if (indexed.brand === query.phrase) score += 60;
  // Don't let description-only matching outrank a matching product name.
  return score;
};

export const scoreProductSearch = (product: Product, raw: string | SearchQuery): number | null => {
  if (product.active !== true) return null;
  const query = typeof raw === 'string' ? parseSearchQuery(raw) : raw;
  return scoreIndexed(productIndex(product), query);
};

export const scoreStoreSearch = (store: VendorStore, raw: string | SearchQuery): number | null => {
  if (!store.active || !store.approved) return null;
  const query = typeof raw === 'string' ? parseSearchQuery(raw) : raw;
  return scoreIndexed(storeIndex(store), query);
};

export const rankSearchProducts = (products: Product[], raw: string): Product[] => {
  const query = parseSearchQuery(raw);
  if (!query.tokens.length) return products.filter(product => product.active === true);
  return products
    .map((product, index) => ({ product, index, score: scoreProductSearch(product, query) }))
    .filter((item): item is { product: Product; index: number; score: number } => item.score !== null)
    .sort((a, b) => b.score - a.score || a.index - b.index)
    .map(item => item.product);
};

/** Rank a standalone category/brand label using the same language rules. */
export const scoreSearchLabel = (label: string, raw: string | SearchQuery): number | null => {
  const query = typeof raw === 'string' ? parseSearchQuery(raw) : raw;
  return scoreIndexed({ fields: [field(label, 16)], name: clean(label), brand: '' }, query);
};