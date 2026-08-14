import { Product } from '../types';
import { PRODUCTS } from '../data/products';
import { inventoryRepository } from './inventoryRepository';

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

const withServerAvailability = async (products: Product[]): Promise<Product[]> => {
  try {
    const { availability } = await inventoryRepository.getAvailability();
    const byVariantId = new Map(availability.map(item => [item.variantId, item.available]));
    return products.map(product => ({
      ...product,
      variants: product.variants.map(variant => ({
        ...variant,
        available: byVariantId.get(variant.id) === true,
      })),
    }));
  } catch {
    // Do not claim stock when the authoritative server cannot be reached.
    return products.map(product => ({
      ...product,
      variants: product.variants.map(variant => ({ ...variant, available: false })),
    }));
  }
};

export const productRepository = {
  async getAllProducts(): Promise<Product[]> {
    return withServerAvailability(PRODUCTS.map(normalizeStoreMetadata));
  },

  async getProductBySlug(slug: string): Promise<Product | null> {
    const products = await this.getAllProducts();
    return products.find(p => p.slug === slug || p.id === slug) || null;
  }
};
