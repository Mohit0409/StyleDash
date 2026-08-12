import { VendorStore } from '../types';
import { INITIAL_STORES } from '../data/vendors';

const LOCAL_STORES_KEY = 'sd_stores_v1';

export const vendorRepository = {
  async getAllStores(): Promise<VendorStore[]> {
    const saved = localStorage.getItem(LOCAL_STORES_KEY);
    if (saved) {
      try { return JSON.parse(saved); } catch { /* Ignore malformed local store data. */ }
    }
    return INITIAL_STORES;
  },

  async getStoreBySlug(slug: string): Promise<VendorStore | null> {
    const stores = await this.getAllStores();
    return stores.find(s => s.slug === slug || s.id === slug) || null;
  },

  async registerNewStore(newStore: Partial<VendorStore>): Promise<VendorStore> {
    const stores = await this.getAllStores();
    const id = `v-store-${Date.now()}`;
    const slug = (newStore.storeName || 'local-store').toLowerCase().replace(/[^a-z0-9]+/g, '-');

    const store: VendorStore = {
      id,
      slug,
      storeName: newStore.storeName || 'New Local Store',
      ownerName: newStore.ownerName || 'Store Owner',
      email: newStore.email || 'partner@neemuch.in',
      phone: newStore.phone || '+919876543210',
      category: newStore.category || 'Clothing & Fashion',
      address: newStore.address || 'Neemuch Main Market',
      pincode: newStore.pincode || '458441',
      city: 'Neemuch',
      rating: 5.0,
      reviewCount: 0,
      deliveryMinutes: 60,
      commissionPercent: 12,
      bannerImage: 'https://images.unsplash.com/photo-1441986300917-64674bd600d8?auto=format&fit=crop&w=1200&q=80',
      logoImage: 'https://images.unsplash.com/photo-1521572267360-ee0c2909d518?auto=format&fit=crop&w=200&q=80',
      description: newStore.description || 'Newly onboarded local store in Neemuch.',
      totalSales: 0,
      active: true,
      approved: false, // Pending admin approval
      createdAt: new Date().toISOString()
    };

    stores.push(store);
    localStorage.setItem(LOCAL_STORES_KEY, JSON.stringify(stores));
    return store;
  },

  async approveStore(storeId: string): Promise<void> {
    const stores = await this.getAllStores();
    const store = stores.find(s => s.id === storeId);
    if (store) {
      store.approved = true;
      localStorage.setItem(LOCAL_STORES_KEY, JSON.stringify(stores));
    }
  }
};
