import { VendorStore } from '../types';
import { publicStoreApi } from '../services/businessApi';

// Short-lived cache dedupes /api/stores/active across Home, Stores and
// StoreDetail navigations (same TTL discipline as the product repository).
const STORE_CACHE_MS = 15_000;
let storeCache: { expiresAt: number; stores: VendorStore[] } | null = null;
let storeRequest: Promise<VendorStore[]> | null = null;

export const vendorRepository = {
  async getAllStores(): Promise<VendorStore[]> {
    if (storeCache && storeCache.expiresAt > Date.now()) return storeCache.stores;
    if (storeRequest) return storeRequest;
    storeRequest = publicStoreApi.active()
      .then(stores => {
        storeCache = { expiresAt: Date.now() + STORE_CACHE_MS, stores };
        return stores;
      })
      .catch(() => [] as VendorStore[])
      .finally(() => { storeRequest = null; });
    return storeRequest;
  },

  async getStoreBySlug(slug: string): Promise<VendorStore | null> {
    const stores = await this.getAllStores();
    return stores.find(store => store.slug === slug || store.id === slug) || null;
  }
};
