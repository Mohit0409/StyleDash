import { Product } from '../types';
import { PRODUCTS } from '../data/products';
import { inventoryRepository } from './inventoryRepository';
import { shopProductApi } from '../services/businessApi';

const PUBLISHED_SHOP_CACHE_MS = 15_000;
let publishedShopCache: { expiresAt: number; products: Product[] } | null = null;
let publishedShopRequest: Promise<Product[]> | null = null;
let availabilityRequest: ReturnType<typeof inventoryRepository.getAvailability> | null = null;

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
    if (!availabilityRequest) availabilityRequest = inventoryRepository.getAvailability();
    const request = availabilityRequest;
    const { availability } = await request;
    if (availabilityRequest === request) availabilityRequest = null;
    const byVariantId = new Map(availability.map(item => [item.variantId, item.available]));
    return products.map(product => ({
      ...product,
      variants: product.variants.map(variant => ({
        ...variant,
        available: byVariantId.get(variant.id) === true,
      })),
    }));
  } catch {
    availabilityRequest = null;
    // Do not claim stock when the authoritative server cannot be reached.
    return products.map(product => ({
      ...product,
      variants: product.variants.map(variant => ({ ...variant, available: false })),
    }));
  }
};

const getPublishedShopProducts = async (): Promise<Product[]> => {
  if (publishedShopCache && publishedShopCache.expiresAt > Date.now()) return publishedShopCache.products;
  if (publishedShopRequest) return publishedShopRequest;

  publishedShopRequest = shopProductApi.published()
    .then(products => products.filter(product => product.active === true))
    .then(products => {
      publishedShopCache = { expiresAt: Date.now() + PUBLISHED_SHOP_CACHE_MS, products };
      return products;
    })
    .catch(() => [])
    .finally(() => { publishedShopRequest = null; });
  return publishedShopRequest;
};

const getCatalogue = async (): Promise<Product[]> => {
  const staticProducts = PRODUCTS.map(normalizeStoreMetadata);
  const shopProducts = await getPublishedShopProducts();
  const seenIds = new Set(staticProducts.map(product => product.id));
  const seenSlugs = new Set(staticProducts.map(product => product.slug));
  return staticProducts.concat(shopProducts.filter(product => {
    if (seenIds.has(product.id) || seenSlugs.has(product.slug)) return false;
    seenIds.add(product.id);
    seenSlugs.add(product.slug);
    return true;
  }));
};

export const productRepository = {
  async getAllProducts(): Promise<Product[]> {
    // Start both public requests together; availability remains fail-closed.
    if (!availabilityRequest) availabilityRequest = inventoryRepository.getAvailability();
    return withServerAvailability(await getCatalogue());
  },

  async getProductBySlug(slug: string): Promise<Product | null> {
    const products = await this.getAllProducts();
    return products.find(p => p.slug === slug || p.id === slug) || null;
  }
};
