import { VendorStore } from '../types';
import { publicStoreApi } from '../services/businessApi';

export const vendorRepository = {
  async getAllStores(): Promise<VendorStore[]> {
    return publicStoreApi.active().catch(() => []);
  },

  async getStoreBySlug(slug: string): Promise<VendorStore | null> {
    const stores = await this.getAllStores();
    return stores.find(store => store.slug === slug || store.id === slug) || null;
  }
};
