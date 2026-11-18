import { describe, expect, it } from 'vitest';
import type { Product, VendorStore } from '../types';
import { parseSearchQuery, rankSearchProducts, scoreProductSearch, scoreStoreSearch } from '../utils/searchEngine';
import { matchesCatalogueProduct } from '../utils/catalogFilters';
import { buildSearchSuggestions } from '../utils/searchSuggestions';

const item = (name: string, extra: Partial<Product> = {}): Product => ({
  id: name, slug: name.toLowerCase().replace(/\s+/g, '-'), name, brand: '',
  department: 'unisex', category: 'Accessories', subcategory: '',
  shortDescription: '', description: '', material: '', careInstructions: [],
  price: 999, originalPrice: 999, discount: 0, images: [], thumbnail: '',
  rating: 0, reviewCount: 0, variants: [], tags: [], returnWindowDays: 0,
  exchangeAvailable: false, vendorId: 'store-1', active: true, ...extra,
});

const seller = (storeName: string, extra: Partial<VendorStore> = {}): VendorStore => ({
  id: storeName, slug: storeName.toLowerCase().replace(/\s+/g,'-'),
  storeName, category: 'Accessories', description: '', address: '', city: 'Neemuch',
  pincode: '458441', deliveryMinutes: 60, active: true, approved: true,
  createdAt: '2026-11-01T00:00:00Z', ...extra,
});

const casioBlue = item('Casio F-91W Digital Watch', {
  brand: 'Casio', category: 'Watches', storeName: 'Prime Time',
  variants: [{ id:'v1',sku:'F-91W-BLU',size:'One Size',colourName:'Blue',stock:2,available:true }],
});

describe('search engine v2 regression', () => {
  it('matches words across name, brand, category, colour and shop', () => {
    expect(scoreProductSearch(casioBlue, 'casio blue watch')).not.toBeNull();
    expect(scoreProductSearch(casioBlue, 'prime time casio')).not.toBeNull();
    expect(scoreProductSearch(casioBlue, 'black casio')).toBeNull();
  });

  it('recognizes exact watch models with and without hyphens', () => {
    expect(scoreProductSearch(casioBlue, 'F91W')).not.toBeNull();
    expect(scoreProductSearch(casioBlue, 'F-91W')).not.toBeNull();
    expect(scoreProductSearch(casioBlue, 'f91w blue')).not.toBeNull();
  });

  it('recovers one adjacent transposition in a brand', () => {
    expect(scoreProductSearch(casioBlue, 'caiso')).not.toBeNull();
    expect(scoreProductSearch(casioBlue, 'caiso watch')).not.toBeNull();
  });

  it('normalizes Neemuch, NMH and filler words', () => {
    expect(parseSearchQuery('buy watch in NMH').tokens).toEqual(['watch']);
    expect(parseSearchQuery('watch in Neemuch').tokens).toEqual(['watch']);
    expect(scoreProductSearch(casioBlue, 'buy casio watches in neemuch')).not.toBeNull();
  });

  it('handles common Hindi-English words and inflections', () => {
    expect(scoreProductSearch(casioBlue, 'ghadi')).not.toBeNull();
    const shoe = item('Campus Running Shoes', { category: 'Footwear' });
    expect(scoreProductSearch(shoe, 'joota')).not.toBeNull();
    const cover = item('Silicon Mobile Back Cover', { category: 'Mobile Accessories' });
    expect(scoreProductSearch(cover, 'phone case')).not.toBeNull();
    const tee = item('Oversized Cotton T-Shirt', { category: 'Clothing' });
    expect(scoreProductSearch(tee, 'oversized tshirt')).not.toBeNull();
  });

  it('ranks exact products over category-only matches and preserves order for ties', () => {
    const generic = item('Local Gift Box', { category: 'Watches' });
    const exact = item('Casio Digital Watch', { category: 'Watches', brand: 'Casio' });
    const order = rankSearchProducts([generic, exact], 'casio digital watch');
    expect(order.map(x => x.name)).toEqual(['Casio Digital Watch']);
    expect(rankSearchProducts([generic, exact], 'watch')[0].name).toBe('Casio Digital Watch');
  });

  it('excludes inactive products and unapproved stores', () => {
    expect(scoreProductSearch(item('Secret Watch', { active:false }), 'watch')).toBeNull();
    expect(scoreStoreSearch(seller('Prime Time', { approved: false }), 'prime time')).toBeNull();
  });

  it('reaches a store by name and excludes missing unrelated words', () => {
    expect(scoreStoreSearch(seller('Prime Time Watches'), 'prime watch')).not.toBeNull();
    expect(scoreStoreSearch(seller('Prime Time Watches'), 'prime perfume')).toBeNull();
  });

  it('returns useful autocomplete suggestions for misspelled and multi-word queries', () => {
    expect(buildSearchSuggestions('caiso', [casioBlue], [seller('Prime Time')])
      .some(s => s.type === 'product')).toBe(true);
    expect(buildSearchSuggestions('prime time casio', [casioBlue], [seller('Prime Time')])
      .some(s => s.id === 'product:Casio F-91W Digital Watch')).toBe(true);
  });

  it('applies search without changing unrelated catalogue filters', () => {
    const filters = {
      department:'all', category:'Watches', subcategory:'all',brand:'all',size:'all',
      maxPrice:2000,searchQuery:'casio blue',filterBadge:'',expressFilterActive:false,
    };
    expect(matchesCatalogueProduct(casioBlue, filters)).toBe(true);
    expect(matchesCatalogueProduct(casioBlue, { ...filters, maxPrice:100 })).toBe(false);
    expect(matchesCatalogueProduct(casioBlue, { ...filters, brand:'Timex' })).toBe(false);
  });

  it('does not interpret punctuation or script as instructions', () => {
    expect(scoreProductSearch(casioBlue, '<script>alert(1)</script>')).toBeNull();
    expect(scoreProductSearch(casioBlue, '!!!!')).toBeNull();
  });
});
