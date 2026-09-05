import type { Product, VendorStore } from '../types';

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
  { id: 'express', title: 'Weekend Express Picks', subtitle: 'Fast local picks ready for Neemuch weekends', href: '/products?filter=express', matches: p => p.expressDelivery === true },
  { id: 'new', title: 'New Drops', subtitle: 'Freshly added styles without taking over your whole feed', href: '/products?filter=new', matches: p => p.newArrival === true },
  { id: 'trending', title: 'Trending in Neemuch', subtitle: 'Popular local styles customers are checking out now', href: '/products?sort=rating', matches: p => p.trending === true },
  { id: 'under499', title: 'Styles Under ₹499', subtitle: 'Budget-friendly finds from local stores', href: '/products?maxPrice=499', matches: p => p.price <= 499 },
  { id: 'women', title: 'Women', subtitle: 'A balanced edit from the women’s catalogue', href: '/products?dept=women', matches: p => p.department === 'women' },
  { id: 'men', title: 'Men', subtitle: 'Everyday and occasion-ready men’s styles', href: '/products?dept=men', matches: p => p.department === 'men' },
  { id: 'accessories', title: 'Accessories', subtitle: 'Jewellery, bags and finishing touches', href: '/products?category=Accessories', matches: p => p.category === 'Accessories' || p.department === 'accessories' },
  { id: 'beauty', title: 'Beauty & Care', subtitle: 'Beauty and personal-care picks from local sellers', href: '/products?category=Beauty%20%26%20Personal%20Care', matches: p => p.category === 'Beauty & Personal Care' },
];

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

export const selectHomepageCandidates = (products: Product[], perSection = 8): Product[] => {
  const selected = new Map<string, Product>();
  for (const definition of SECTIONS) {
    for (const product of sectionCandidates(products, definition).slice(0, perSection)) {
      selected.set(product.id, product);
    }
  }
  return [...selected.values()];
};

export const buildHomepageSections = (products: Product[], limit = 5): HomeMerchSection[] => {
  const usage = new Map<string, number>();
  return SECTIONS.map(definition => {
    const candidates = sectionCandidates(products, definition).sort((a, b) =>
      (usage.get(a.id) || 0) - (usage.get(b.id) || 0)
      || merchandisingScore(b) - merchandisingScore(a)
      || newestFirst(a, b),
    );
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
