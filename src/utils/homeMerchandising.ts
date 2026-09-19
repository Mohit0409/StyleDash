import type { Product, VendorStore } from '../types';
import { isExpressDeliveryAvailable } from './delivery';

export type HomeMerchSectionId =
  | 'express'
  | 'new'
  | 'trending'
  | 'under499'
  | 'women'
  | 'men'
  | 'accessories'
  | 'beauty';

export interface HomeMerchSection {
  id: HomeMerchSectionId;
  title: string;
  subtitle: string;
  href: string;
  products: Product[];
}

interface SectionDefinition {
  id: HomeMerchSectionId;
  title: string;
  subtitle: string;
  href: string;
  matches: (product: Product) => boolean;
}
const SECTIONS: SectionDefinition[] = [
  { id: 'express', title: 'Weekend Express Picks', subtitle: 'Every active product supports Same Day (₹50 below ₹300, free from ₹300) + ₹80 Express Delivery on Saturday and Sunday', href: '/products?filter=express', matches: () => true },
  { id: 'new', title: 'New Drops', subtitle: 'Freshly added styles without taking over your whole feed', href: '/products?filter=new', matches: p => p.newArrival === true },
  { id: 'trending', title: 'Trending in Neemuch', subtitle: 'Popular local styles customers are checking out now', href: '/products?sort=rating', matches: p => p.trending === true },
  { id: 'under499', title: 'Styles Under ₹499', subtitle: 'Budget-friendly finds from local stores', href: '/products?maxPrice=499', matches: p => p.price <= 499 },
  { id: 'women', title: 'Women', subtitle: 'A balanced edit from the women’s catalogue', href: '/products?dept=women', matches: p => p.department === 'women' },
  { id: 'men', title: 'Men', subtitle: 'Everyday and occasion-ready men’s styles', href: '/products?dept=men', matches: p => p.department === 'men' },
  { id: 'accessories', title: 'Accessories', subtitle: 'Jewellery, bags and finishing touches', href: '/products?category=Accessories', matches: p => p.category === 'Accessories' || p.department === 'accessories' },
  { id: 'beauty', title: 'Beauty & Care', subtitle: 'Beauty and personal-care picks from local sellers', href: '/products?category=Beauty%20%26%20Personal%20Care', matches: p => p.category === 'Beauty & Personal Care' },
];

const sectionsForDate = (date: Date): SectionDefinition[] =>
  SECTIONS.filter(definition => definition.id !== 'express' || isExpressDeliveryAvailable(date));

const merchandisingScore = (product: Product): number =>
  (product.featured ? 50 : 0)
  + (product.trending ? 30 : 0)
  + (product.newArrival ? 20 : 0)
  + Math.round((product.rating || 0) * 5)
  + Math.min(product.reviewCount || 0, 20);

const newestFirst = (a: Product, b: Product): number =>
  Date.parse(b.createdAt || '') - Date.parse(a.createdAt || '');

const indiaDateSeed = (date: Date): string =>
  new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Kolkata',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(date);

const stableHash = (value: string): number => {
  let hash = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
};

const storeKey = (product: Product): string =>
  product.vendorId || product.storeSlug || product.storeName || 'unknown-store';

const categoryKey = (product: Product): string =>
  product.category || product.department || 'uncategorized';

/**
 * Produces a stable daily discovery mix that balances stores and categories
 * before repeating either. This prevents one newly-uploaded shop batch from
 * monopolising homepage discovery rows while avoiding UI reshuffles on every
 * React render.
 */
export const selectDiverseProducts = (
  products: Product[],
  limit: number,
  namespace = 'homepage-discovery',
  date = new Date(),
  excludedIds: Iterable<string> = [],
): Product[] => {
  const safeLimit = Math.max(0, Math.floor(limit));
  if (safeLimit === 0) return [];

  const excluded = new Set(excludedIds);
  const seed = `${namespace}:${indiaDateSeed(date)}`;
  const remaining = products
    .filter(product => product.active === true && !excluded.has(product.id))
    .sort((a, b) => {
      const hashDifference = stableHash(`${seed}:${a.id}`) - stableHash(`${seed}:${b.id}`);
      return hashDifference || a.id.localeCompare(b.id);
    });

  const chosen: Product[] = [];
  const storeUsage = new Map<string, number>();
  const categoryUsage = new Map<string, number>();

  while (chosen.length < safeLimit && remaining.length > 0) {
    let bestIndex = 0;
    let bestPenalty = Number.POSITIVE_INFINITY;

    for (let index = 0; index < remaining.length; index += 1) {
      const product = remaining[index];
      const usedStore = storeUsage.get(storeKey(product)) || 0;
      const usedCategory = categoryUsage.get(categoryKey(product)) || 0;
      // Prefer a product that introduces both a new shop and category, then
      // progressively relax diversity only when the catalogue requires it.
      const penalty = (Math.max(usedStore, usedCategory) * 1000) + ((usedStore + usedCategory) * 100);
      if (penalty < bestPenalty) {
        bestPenalty = penalty;
        bestIndex = index;
      }
    }

    const [picked] = remaining.splice(bestIndex, 1);
    chosen.push(picked);
    storeUsage.set(storeKey(picked), (storeUsage.get(storeKey(picked)) || 0) + 1);
    categoryUsage.set(categoryKey(picked), (categoryUsage.get(categoryKey(picked)) || 0) + 1);
  }

  return chosen;
};

const sectionCandidates = (
  products: Product[],
  definition: SectionDefinition,
  date = new Date(),
): Product[] => {
  const filtered = products.filter(product => product.active === true && definition.matches(product));
  if (definition.id === 'express') {
    return selectDiverseProducts(filtered, filtered.length, 'weekend-express', date);
  }
  return filtered.sort((a, b) => {
    if (definition.id === 'new') return newestFirst(a, b) || merchandisingScore(b) - merchandisingScore(a);
    return merchandisingScore(b) - merchandisingScore(a) || newestFirst(a, b) || a.name.localeCompare(b.name);
  });
};

export const selectTopPicks = (
  products: Product[],
  limit = 8,
  date = new Date(),
): Product[] => selectDiverseProducts(products, limit, 'top-picks', date);

export const selectHomepageCandidates = (products: Product[], perSection = 8, date = new Date()): Product[] => {
  const definitions = sectionsForDate(date);
  const capacity = Math.max(perSection, perSection * SECTIONS.length);
  const generalBudget = Math.min(perSection, capacity);
  const remainingBudget = Math.max(0, capacity - generalBudget);
  const sectionBudget = definitions.length > 0
    ? Math.max(1, Math.floor(remainingBudget / definitions.length))
    : 0;

  const selected = new Map<string, Product>();
  for (const product of selectDiverseProducts(products, generalBudget, 'homepage-candidate-pool', date)) {
    selected.set(product.id, product);
  }

  for (const definition of definitions) {
    for (const product of sectionCandidates(products, definition, date).slice(0, sectionBudget)) {
      if (selected.size >= capacity) break;
      selected.set(product.id, product);
    }
    if (selected.size >= capacity) break;
  }
  return [...selected.values()];
};

export const buildHomepageSections = (
  products: Product[],
  limit = 5,
  date = new Date(),
  avoidProductIds: Iterable<string> = [],
): HomeMerchSection[] => {
  const usage = new Map<string, number>();
  for (const productId of avoidProductIds) usage.set(productId, 1);

  return sectionsForDate(date).map(definition => {
    const candidates = sectionCandidates(products, definition, date).sort((a, b) => {
      const usageDifference = (usage.get(a.id) || 0) - (usage.get(b.id) || 0);
      if (usageDifference) return usageDifference;
      // Express is already diversity/random ordered; preserve that order for ties.
      if (definition.id === 'express') return 0;
      return merchandisingScore(b) - merchandisingScore(a)
        || newestFirst(a, b)
        || a.name.localeCompare(b.name);
    });
    const chosen = candidates.slice(0, limit);
    chosen.forEach(product => usage.set(product.id, (usage.get(product.id) || 0) + 1));
    return { ...definition, products: chosen };
  }).filter(section => section.products.length > 0);
};

export const selectHomepageStores = (stores: VendorStore[], limit?: number): VendorStore[] => {
  const selected = stores
    .filter(store => store.approved === true && store.active === true)
    .sort((a, b) =>
      (b.rating || 0) - (a.rating || 0)
      || (b.reviewCount || 0) - (a.reviewCount || 0)
      || a.storeName.localeCompare(b.storeName),
    );
  return typeof limit === 'number' ? selected.slice(0, Math.max(0, limit)) : selected;
};
