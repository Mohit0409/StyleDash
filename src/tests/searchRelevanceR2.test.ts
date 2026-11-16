import { describe, expect, it } from 'vitest';
import type { Product, VendorStore } from '../types';
import { canonicalBrandOptions, availableBrandOptions, matchesCatalogueProduct, type CatalogueFilterState } from '../utils/catalogFilters';
import { scoreProductSearch, scoreStoreSearch } from '../utils/searchEngine';

const product = (name: string, extra: Partial<Product> = {}): Product => ({
 id: name, slug: name.toLocaleLowerCase(), name, brand: '', department: 'unisex',
 category: 'Accessories', subcategory: '', shortDescription: '', description: '',
 material: '', careInstructions: [], price: 500, originalPrice: 500, discount: 0,
 images: [], thumbnail: '', rating: 0, reviewCount: 0, variants: [],
 tags: [], returnWindowDays: 0, exchangeAvailable: false, vendorId: 'vendor',
 storeName: 'Local Store', active: true, ...extra
});
const shop = (name: string, extra: Partial<VendorStore> = {}): VendorStore => ({
 id: name, slug: name.toLowerCase(), storeName: name, category: 'Clothing & Fashion',
 description: '', address: '', city: 'Neemuch', pincode: '458441',
 deliveryMinutes: 60, active: true, approved: true, createdAt:'2026-11-14',
 ...extra
});
const filters = (brand='all',searchQuery=''):CatalogueFilterState=>({
 department:'all', category:'all', subcategory:'all', brand, size:'all',
 maxPrice: 5000, searchQuery, filterBadge:'',expressFilterActive:false
});
describe('Search V2 relevance fix R2',()=>{
 it('does not match casio within the word occasion in product descriptions',()=>{
   const slipper=product("Women's slippers",{category:'Footwear',brand:'Springle',
     shortDescription:'Perfect for every occasion'});
   expect(scoreProductSearch(slipper,'casio')).toBeNull();
   expect(scoreProductSearch(slipper,'caiso')).toBeNull();
   expect(matchesCatalogueProduct(slipper,filters('all','casio'))).toBe(false);
 });
 it('does not match casio inside the word occasion in shop descriptions',()=>{
   const fashion=shop('Uphaar Basket',{description:'Gifts for every occasion in Neemuch'});
   expect(scoreStoreSearch(fashion,'casio')).toBeNull();
 });
 it('keeps actual Casio matches and misspelling recovery',()=>{
   const watch=product('Casio F-91W Blue',{brand:'Casio',subcategory:'Watches'});
   expect(scoreProductSearch(watch,'casio')).not.toBeNull();
   expect(scoreProductSearch(watch,'caiso watch')).not.toBeNull();
   expect(scoreProductSearch(watch,'casioo')).not.toBeNull();
   expect(scoreProductSearch(watch,'F91W')).not.toBeNull();
   expect(scoreProductSearch(watch,'ghadi')).not.toBeNull();
 });
 it('collapses all case variants of a brand to the most common display form',()=>{
   expect(canonicalBrandOptions(['CASIO','Casio','casio','Casio','TIMEX','Timex']))
     .toEqual(['Casio','Timex']);
 });
 it('deduplicates brand options from matching products only',()=>{
   const inventory=[product('Casio 1',{brand:'CASIO'}),product('Casio 2',{brand:'Casio'}),
      product('Casio 3',{brand:'Casio'}),product('Casio 4',{brand:'casio'}),
      product('Another',{brand:'Timex'})];
   expect(availableBrandOptions(inventory,filters())).toEqual(['Casio','Timex']);
   expect(availableBrandOptions(inventory,filters('all','casio'))).toEqual(['Casio']);
 });
 it('existing deep-link brand casing still matches products',()=>{
   const watch=product('Casio Watch',{brand:'CASIO'});
   expect(matchesCatalogueProduct(watch, filters('Casio','casio'))).toBe(true);
   expect(matchesCatalogueProduct(watch, filters('casio','casio'))).toBe(true);
 });
});
