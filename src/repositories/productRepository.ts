import { Product } from '../types';
import { PRODUCTS } from '../data/products';

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
    return PRODUCTS.map(normalizeStoreMetadata);
  },

  async getProductBySlug(slug: string): Promise<Product | null> {
    const products = await this.getAllProducts();
    return products.find(p => p.slug === slug || p.id === slug) || null;
  }
};
