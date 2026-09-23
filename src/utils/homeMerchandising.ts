import type { Product, VendorStore } from '../types';
import { isExpressDeliveryAvailable } from './delivery';

export type HomeMerchSectionId =
  | 'express'
  | 'new'
  | 'trending'
  | 'under499'
  | 'women'
  | 'men'
  | 'clothing'
  | 'footwear'
  | 'accessories'
  | 'beauty'
  | 'electronics'
  | 'gifts'
  | 'home';

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
  { id: 'express', title: 'Weekend Express Picks', subtitle: 'Fast weekend delivery picks from local Neemuch stores', href: '/products?filter=express', matches: () => true },
  { id: 'new', title: 'New Drops', subtitle: 'Freshly added styles without taking over your whole feed', href: '/products?filter=new', matches: p => p.newArrival === true },
  { id: 'trending', title: 'Trending in Neemuch', subtitle: 'Popular local styles customers are checking out now', href: '/products?sort=rating', matches: p => p.trending === true },
  { id: 'under499', title: 'Styles Under ₹499', subtitle: 'Budget-friendly finds from local stores', href: '/products?maxPrice=499', matches: p => p.price <= 499 },
  { id: 'women', title: 'Women', subtitle: 'A balanced edit from the women’s catalogue', href: '/products?dept=women', matches: p => p.department === 'women' },
  { id: 'men', title: 'Men', subtitle: 'Everyday and occasion-ready men’s styles', href: '/products?dept=men', matches: p => p.department === 'men' },
  { id: 'clothing', title: 'Clothing & Fashion', subtitle: 'Everyday fashion and occasion-ready styles from local stores', href: '/products?category=Clothing%20%26%20Fashion', matches: p => p.category === 'Clothing & Fashion' },
  { id: 'footwear', title: 'Footwear', subtitle: 'Sneakers, sandals, sliders and more from Neemuch stores', href: '/products?category=Footwear', matches: p => p.category === 'Footwear' },
  { id: 'accessories', title: 'Accessories', subtitle: 'Jewellery, bags and finishing touches', href: '/products?category=Accessories', matches: p => p.category === 'Accessories' || p.department === 'accessories' },
  { id: 'beauty', title: 'Beauty & Care', subtitle: 'Beauty and personal-care picks from local sellers', href: '/products?category=Beauty%20%26%20Personal%20Care', matches: p => p.category === 'Beauty & Personal Care' },
  { id: 'electronics', title: 'Electronics', subtitle: 'Useful electronics and everyday tech from local sellers', href: '/products?category=Electronics', matches: p => p.category === 'Electronics' },
  { id: 'gifts', title: 'Gifts', subtitle: 'Gift-ready finds for celebrations and thoughtful surprises', href: '/products?category=Gifts', matches: p => p.category === 'Gifts' },
  { id: 'home', title: 'Home & Living', subtitle: 'Home, kitchen and everyday living essentials', href: '/products?category=Home%20%26%20Living', matches: p => p.category === 'Home & Living' },
];

const HOMEPAGE_SECTION_PRIORITY: Record<HomeMerchSectionId, number> = {
  clothing: 0,
  footwear: 1,
  accessories: 2,
  beauty: 3,
  electronics: 4,
  gifts: 5,
  home: 6,
  express: 7,
  new: 8,
  trending: 9,
  under499: 10,
  women: 11,
  men: 12,
};

const sectionsForDate = (date: Date): SectionDefinition[] =>
  SECTIONS
    .filter(definition => definition.id !== 'express' || isExpressDeliveryAvailable(date))
    .sort((first, second) => HOMEPAGE_SECTION_PRIORITY[first.id] - HOMEPAGE_SECTION_PRIORITY[second.id]);


const CATEGORY_SECTION_IDS = new Set<HomeMerchSectionId>([
  'clothing',
  'footwear',
  'accessories',
  'beauty',
  'electronics',
  'gifts',
  'home',
]);

const merchandisingScore = (product: Product): number =>
  (product.featured ? 50 : 0)
  + (product.trending ? 30 : 0)
  + (product.newArrival ? 20 : 0)
  + Math.round((product.rating || 0) * 5)
  + Math.min(product.reviewCount || 0, 20);

const newestFirst = (a: Product, b: Product): number =>
  Date.parse(b.createdAt || '') - Date.parse(a.createdAt || '');
const sectionCandidates = (products: Product[], definition: SectionDefinition): Product[] =>
  products
    .filter(product => product.active === true && definition.matches(product))
    .sort((a, b) => {
      if (definition.id === 'new') return newestFirst(a, b) || merchandisingScore(b) - merchandisingScore(a);
      return merchandisingScore(b) - merchandisingScore(a) || newestFirst(a, b) || a.name.localeCompare(b.name);
    });

export const selectHomepageCandidates = (products: Product[], perSection = 8, date = new Date()): Product[] => {
  const selected = new Map<string, Product>();
  for (const definition of sectionsForDate(date)) {
    for (const product of sectionCandidates(products, definition).slice(0, perSection)) {
      selected.set(product.id, product);
    }
  }
  return [...selected.values()];
};

export const buildHomepageSections = (
  products: Product[],
  limit = 5,
  date = new Date(),
  fallbackProducts: Product[] = [],
): HomeMerchSection[] => {
  const usedProductIds = new Set<string>();
  return sectionsForDate(date).map(definition => {
    const categorySection = CATEGORY_SECTION_IDS.has(definition.id);
    const unused = (product: Product) => categorySection || !usedProductIds.has(product.id);
    const candidates = sectionCandidates(products, definition);
    const primary = candidates
      .filter(unused)
      .slice(0, limit);
    const fallbackCandidates = sectionCandidates(fallbackProducts, definition);
    const chosen = primary.length > 0
      ? primary
      : categorySection
        ? fallbackCandidates.slice(0, limit)
        : candidates.slice(0, 1).length > 0
          ? candidates.slice(0, 1)
          : fallbackCandidates.slice(0, 1);
    if (!categorySection) chosen.forEach(product => usedProductIds.add(product.id));
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
