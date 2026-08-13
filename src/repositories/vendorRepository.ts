import { VendorStore } from '../types';
import { INITIAL_STORES } from '../data/vendors';

export const vendorRepository = {
  async getAllStores(): Promise<VendorStore[]> {
    return INITIAL_STORES;
  },

  async getStoreBySlug(slug: string): Promise<VendorStore | null> {
    const stores = await this.getAllStores();
    return stores.find(s => s.slug === slug || s.id === slug) || null;
  }
};
