import { Product } from '../types';
import { PRODUCTS } from '../data/products';
import { db, isFirebaseConfigured } from '../firebase/config';
import { collection, getDocs, doc, getDoc, setDoc, query, where } from 'firebase/firestore';

const launchStore = {
  vendorId: 'v-urban-style',
  storeName: 'Urban Style Boutique (Main Store)',
  storeSlug: 'urban-style-store',
};

const normalizeStoreMetadata = (product: Product): Product => ({
  ...product,
  vendorId: product.vendorId || launchStore.vendorId,
  storeName: product.storeName || launchStore.storeName,
  storeSlug: product.storeSlug || launchStore.storeSlug,
});

export const productRepository = {
  async getAllProducts(): Promise<Product[]> {
    if (isFirebaseConfigured && db) {
      try {
        const snap = await getDocs(collection(db, 'products'));
        if (!snap.empty) {
          return snap.docs.map(d => normalizeStoreMetadata({ id: d.id, ...d.data() } as Product));
        }
      } catch (e) {
        console.warn('Firestore fetch failed, using local products fallback', e);
      }
    }
    const local = localStorage.getItem('sd_products');
    if (local) {
      try { return (JSON.parse(local) as Product[]).map(normalizeStoreMetadata); } catch { /* Ignore malformed local product data. */ }
    }
    return PRODUCTS.map(normalizeStoreMetadata);
  },

  async getProductBySlug(slug: string): Promise<Product | null> {
    const products = await this.getAllProducts();
    return products.find(p => p.slug === slug || p.id === slug) || null;
  },

  async saveProduct(product: Product): Promise<void> {
    product = normalizeStoreMetadata(product);
    const products = await this.getAllProducts();
    const idx = products.findIndex(p => p.id === product.id);
    if (idx >= 0) {
      products[idx] = product;
    } else {
      products.push(product);
    }
    localStorage.setItem('sd_products', JSON.stringify(products));

    if (isFirebaseConfigured && db) {
      try {
        await setDoc(doc(db, 'products', product.id), product);
      } catch (e) {
        console.warn('Firestore product save failed', e);
      }
    }
  },

  async updateStock(productId: string, variantId: string, delta: number): Promise<void> {
    const products = await this.getAllProducts();
    const p = products.find(item => item.id === productId);
    if (p) {
      const v = p.variants.find(varItem => varItem.id === variantId);
      if (v) {
        v.stock = Math.max(0, v.stock + delta);
        await this.saveProduct(p);
      }
    }
  }
};
