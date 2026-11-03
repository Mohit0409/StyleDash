import { describe, expect, it } from 'vitest';
import { NEEMUCH_SHOPPING_PAGES, neemuchShoppingPageBySlug } from '../data/neemuchShopping';
import { catalogueUrl, matchesPage } from '../pages/NeemuchShopping';
import type { Product } from '../types';

const productionSlugs = [
  'beauty', 'casio-watches', 'clothes', 'electronics', 'gifts', 'groceries',
  'handbags', 'home-and-living', 'jewellery', 'kids-wear', 'lavie-bags',
  'mens-clothing', 'mobile-accessories', 'mobile-covers', 'mobile-phones',
  'same-day-delivery', 'shoes', 'shops', 'watches', 'womens-clothing',
];

describe('production Neemuch landing pages', () => {
  it('covers each of the 20 published server routes once', () => {
    expect(NEEMUCH_SHOPPING_PAGES.map(page => page.slug).sort()).toEqual(productionSlugs);
  });

  it('has unique, valid slugs and search-visible titles for every page', () => {
    expect(new Set(NEEMUCH_SHOPPING_PAGES.map(page => page.slug)).size).toBe(20);
    for (const page of NEEMUCH_SHOPPING_PAGES) {
      expect(page.slug).toMatch(/^[a-z0-9-]+$/);
      expect(page.title).toContain('Neemuch');
      expect(page.description.trim().length).toBeGreaterThan(60);
      expect(page.heading.trim().length).toBeGreaterThan(5);
    }
  });

  it('routes the shops landing page to real storefronts, not a generic product list', () => {
    expect(neemuchShoppingPageBySlug('shops')).toMatchObject({
      directory: 'stores',
      catalogueUrl: '/stores',
    });
  });

  it('preserves brand-specific discovery for Casio watches and Lavie bags', () => {
    expect(neemuchShoppingPageBySlug('casio-watches')?.nameTerms).toContain('casio');
    expect(neemuchShoppingPageBySlug('lavie-bags')?.nameTerms).toContain('lavie');
    expect(neemuchShoppingPageBySlug('casio-watches')?.catalogueUrl).toContain('Watches');
    expect(neemuchShoppingPageBySlug('lavie-bags')?.catalogueUrl).toContain('Handbags');
  });

  it('matches a watch or bag by verified brand even without the brand in its title', () => {
    const watch = {
      name: 'Digital Watch Blue', brand: 'Casio', category: 'Accessories',
      department: 'unisex', subcategory: 'Watches',
    } as Product;
    const bag = {
      name: 'Everyday Handbag', brand: 'Lavie', category: 'Accessories',
      department: 'women', subcategory: 'Handbags',
    } as Product;
    expect(matchesPage(watch, 'casio-watches')).toBe(true);
    expect(matchesPage(bag, 'lavie-bags')).toBe(true);
    expect(matchesPage(bag, 'casio-watches')).toBe(false);
    expect(matchesPage(watch, 'shops')).toBe(false);
  });

  it('uses the production catalogue destination for shops and branded listings', () => {
    expect(catalogueUrl('shops')).toBe('/stores');
    expect(catalogueUrl('casio-watches')).toBe('/products?category=Accessories&subcategory=Watches');
    expect(catalogueUrl('lavie-bags')).toBe('/products?category=Accessories&subcategory=Handbags');
  });

  it('does not invent unknown shopping landing routes', () => {
    expect(neemuchShoppingPageBySlug('not-a-real-category')).toBeUndefined();
  });
});
