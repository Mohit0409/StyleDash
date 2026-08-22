import { VendorStore } from '../types';
import { INITIAL_STORES } from '../data/vendors';
import { publicStoreApi } from '../services/businessApi';

const mergeStores = (staticStores: VendorStore[], dynamicStores: VendorStore[]): VendorStore[] => {
  const seenIds = new Set(staticStores.map(store => store.id));
  const seenSlugs = new Set(staticStores.map(store => store.slug));
  return staticStores.concat(dynamicStores.filter(store => {
    if (seenIds.has(store.id) || seenSlugs.has(store.slug)) return false;
    seenIds.add(store.id); seenSlugs.add(store.slug); return true;
  }));
};

export const vendorRepository = {
  async getAllStores(): Promise<VendorStore[]> {
    const dynamic = await publicStoreApi.active().catch(() => []);
    return mergeStores(INITIAL_STORES, dynamic);
  },

  async getStoreBySlug(slug: string): Promise<VendorStore | null> {
    const stores = await this.getAllStores();
    return stores.find(s => s.slug === slug || s.id === slug) || null;
  }
};
