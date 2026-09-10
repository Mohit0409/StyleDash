import { Product } from '../types';
import { inventoryRepository } from './inventoryRepository';
import { shopProductApi } from '../services/businessApi';
import { reviewApi, ReviewSummary } from '../services/reviewApi';
import { selectHomepageCandidates } from '../utils/homeMerchandising';

const PUBLISHED_SHOP_CACHE_MS = 15_000;
const PRODUCT_IMAGE_FALLBACK = '/product-placeholder.svg';

const isObviouslyPageUrl = (value: string): boolean => {
  try {
    const pathname = new URL(value, 'https://vibe4you.invalid').pathname.toLowerCase();
    return /\.x?html?$/.test(pathname);
  } catch {
    return false;
  }
};

let publishedShopCache: { expiresAt: number; products: Product[] } | null = null;
let publishedShopRequest: Promise<Product[]> | null = null;
let availabilityRequest: ReturnType<typeof inventoryRepository.getAvailability> | null = null;

const launchStore = {
  vendorId: 'v-urban-style',
  storeName: 'Urban Style Boutique (Main Store)',
  storeSlug: 'urban-style-store',
};

const normalizeStoreMetadata = (product: Product): Product => {
  const safeImages = product.images.filter(image => !isObviouslyPageUrl(image));
  const safeThumbnail = product.thumbnail && !isObviouslyPageUrl(product.thumbnail)
    ? product.thumbnail
    : null;
  const thumbnail = safeThumbnail || safeImages[0] || PRODUCT_IMAGE_FALLBACK;
  const images = safeImages.length > 0 ? safeImages : [thumbnail];
  return {
    ...product,
    images,
    thumbnail,
    variants: product.variants.map(variant => {
      if (!variant.images) return variant;
      const safeVariantImages = variant.images.filter(image => !isObviouslyPageUrl(image));
      return { ...variant, images: safeVariantImages.length > 0 ? safeVariantImages : undefined };
    }),
    vendorId: product.vendorId || launchStore.vendorId,
    storeName: product.storeName || launchStore.storeName,
    storeSlug: product.storeSlug || launchStore.storeSlug,
  };
};

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
    .then(products => products.filter(product => product.active === true).map(normalizeStoreMetadata))
    .then(products => {
      publishedShopCache = { expiresAt: Date.now() + PUBLISHED_SHOP_CACHE_MS, products };
      return products;
    })
    .catch(() => [])
    .finally(() => { publishedShopRequest = null; });
  return publishedShopRequest;
};

const mergeCatalogue = (staticProducts: Product[], shopProducts: Product[]): Product[] => {
  const seenIds = new Set(staticProducts.map(product => product.id));
  const seenSlugs = new Set(staticProducts.map(product => product.slug));
  return staticProducts.concat(shopProducts.filter(product => {
    if (seenIds.has(product.id) || seenSlugs.has(product.slug)) return false;
    seenIds.add(product.id);
    seenSlugs.add(product.slug);
    return true;
  }));
};

const shouldLoadDemoCatalogue = (): boolean => {
  if (typeof window === 'undefined') return true;
  const hostname = window.location.hostname.toLowerCase();
  return hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '::1';
};

const getStaticProducts = async (): Promise<Product[]> => {
  // The generated StyleDash catalogue is retained only as a deterministic local/E2E fixture.
  // Real Vibe4You domains render DB-backed seller products exclusively.
  if (!shouldLoadDemoCatalogue()) return [];
  const { PRODUCTS } = await import('../data/products');
  return PRODUCTS.map(normalizeStoreMetadata);
};

const getCatalogue = async (): Promise<Product[]> => {
  const [staticProducts, shopProducts] = await Promise.all([
    getStaticProducts(),
    getPublishedShopProducts(),
  ]);
  return mergeCatalogue(staticProducts, shopProducts);
};


const REVIEW_SUMMARY_BATCH_SIZE = 64;

const getReviewSummaries = async (products: Product[]): Promise<Record<string, ReviewSummary>> => {
  if (!products.length) return {};
  const productIds = products.map(product => product.id);
  const batches: string[][] = [];
  for (let offset = 0; offset < productIds.length; offset += REVIEW_SUMMARY_BATCH_SIZE) {
    batches.push(productIds.slice(offset, offset + REVIEW_SUMMARY_BATCH_SIZE));
  }
  const results = await Promise.all(batches.map(async batch => {
    try {
      const summaries = await reviewApi.summaries(batch);
      return summaries && typeof summaries === 'object' ? summaries : {};
    } catch {
      return {};
    }
  }));
  return Object.assign({}, ...results);
};

const applyReviewSummaries = (products: Product[], summaries: Record<string, ReviewSummary>): Product[] =>
  products.map(product => ({
    ...product,
    rating: summaries[product.id]?.rating ?? product.rating,
    reviewCount: summaries[product.id]?.reviewCount ?? product.reviewCount,
  }));

const selectHomepageProducts = (products: Product[]): Product[] =>
  selectHomepageCandidates(products, 8);

const withHomepageAvailability = async (products: Product[]): Promise<Product[]> => {
  try {
    const { availability } = await inventoryRepository.getAvailabilityForProducts(products.map(product => product.id));
    const byVariantId = new Map(availability.map(item => [item.variantId, item.available]));
    return products.map(product => ({ ...product, variants: product.variants.map(variant => ({
      ...variant, available: byVariantId.get(variant.id) === true,
    })) }));
  } catch {
    return products.map(product => ({ ...product, variants: product.variants.map(variant => ({ ...variant, available: false })) }));
  }
};

export const productRepository = {
  async getHomepageProducts(): Promise<Product[]> {
    const products = selectHomepageProducts(await getCatalogue());
    const [availableProducts, summaries] = await Promise.all([
      withHomepageAvailability(products),
      getReviewSummaries(products),
    ]);
    return applyReviewSummaries(availableProducts, summaries);
  },

  async getAllProducts(): Promise<Product[]> {
    // Start availability while catalogue data loads; review summaries are independent and fail open to zero.
    if (!availabilityRequest) availabilityRequest = inventoryRepository.getAvailability();
    const products = await getCatalogue();
    const [availableProducts, summaries] = await Promise.all([
      withServerAvailability(products),
      getReviewSummaries(products),
    ]);
    return applyReviewSummaries(availableProducts, summaries);
  },

  async getProductBySlug(slug: string): Promise<Product | null> {
    const products = await this.getAllProducts();
    return products.find(p => p.slug === slug || p.id === slug) || null;
  }
};
