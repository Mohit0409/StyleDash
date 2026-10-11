import { Product } from '../types';
import { ApiError } from '../services/apiClient';
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
// Display-only snapshots prevent bursts of identical GETs. Cart/order validation
// always uses inventoryRepository.getAvailability(variantId), never this snapshot.
const DISPLAY_INVENTORY_TTL_MS = 10_000;
const REVIEW_SUMMARY_TTL_MS = 120_000;
const RATE_LIMIT_COOLDOWN_MS = 60_000;
let availabilityCache: { expiresAt: number; response: Awaited<ReturnType<typeof inventoryRepository.getAvailability>> } | null = null;
let availabilityCooldownUntil = 0;
let homepageCache: { expiresAt: number; products: Product[] } | null = null;
let homepageRequest: Promise<Product[]> | null = null;

const retryOnce = async <T>(request: () => Promise<T>): Promise<T> => {
  try {
    return await request();
  } catch (error) {
    // A 429 is not a transient network failure; immediately repeating it
    // worsens the shared server-side per-client rate limit.
    if (error instanceof ApiError && error.status === 429) throw error;
    await new Promise(resolve => setTimeout(resolve, 150));
    return request();
  }
};

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
      const safeVariantImages = variant.images?.filter(image => !isObviouslyPageUrl(image));
      return {
        ...variant,
        // The published catalogue carries a fail-closed placeholder. Only the live
        // inventory endpoint is authoritative for customer-facing availability.
        available: undefined,
        images: safeVariantImages && safeVariantImages.length > 0 ? safeVariantImages : undefined,
      };
    }),
    vendorId: product.vendorId || launchStore.vendorId,
    storeName: product.storeName || launchStore.storeName,
    storeSlug: product.storeSlug || launchStore.storeSlug,
  };
};

const getDisplayAvailability = async (): Promise<
  Awaited<ReturnType<typeof inventoryRepository.getAvailability>> | null
> => {
  const now = Date.now();
  if (availabilityCache && availabilityCache.expiresAt > now) return availabilityCache.response;
  if (now < availabilityCooldownUntil) return null;
  if (!availabilityRequest) availabilityRequest = retryOnce(() => inventoryRepository.getAvailability());
  const request = availabilityRequest;
  try {
    const response = await request;
    availabilityCache = { expiresAt: Date.now() + DISPLAY_INVENTORY_TTL_MS, response };
    return response;
  } catch (error) {
    availabilityCooldownUntil = Date.now() + (error instanceof ApiError && error.status === 429
      ? RATE_LIMIT_COOLDOWN_MS : 2_000);
    return null;
  } finally {
    if (availabilityRequest === request) availabilityRequest = null;
  }
};

const withServerAvailability = async (products: Product[]): Promise<Product[]> => {
  const response = await getDisplayAvailability();
  if (!response) return products;
  const byVariantId = new Map(response.availability.map(item => [item.variantId, item.available]));
  return products.map(product => ({
    ...product,
    variants: product.variants.map(variant => ({
      ...variant,
      available: byVariantId.has(variant.id) ? byVariantId.get(variant.id) === true : undefined,
    })),
  }));
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
const REVIEW_SUMMARY_CONCURRENCY = 2;
const reviewBatchCache = new Map<string, { expiresAt: number; summaries: Record<string, ReviewSummary> }>();
const reviewBatchRequests = new Map<string, Promise<Record<string, ReviewSummary>>>();
let reviewCooldownUntil = 0;

const getReviewBatch = (batch: string[]): Promise<Record<string, ReviewSummary>> => {
  const key = batch.join('|');
  const cached = reviewBatchCache.get(key);
  if (cached && cached.expiresAt > Date.now()) return Promise.resolve(cached.summaries);
  const inFlight = reviewBatchRequests.get(key);
  if (inFlight) return inFlight;
  if (Date.now() < reviewCooldownUntil) return Promise.resolve({});
  const request = reviewApi.summaries(batch)
    .then(summaries => {
      const result = summaries && typeof summaries === 'object' ? summaries : {};
      // Bound memory use if the user visits many different catalog subsets.
      if (reviewBatchCache.size >= 64) reviewBatchCache.delete(reviewBatchCache.keys().next().value as string);
      reviewBatchCache.set(key, { expiresAt: Date.now() + REVIEW_SUMMARY_TTL_MS, summaries: result });
      return result;
    })
    .catch(error => {
      if (error instanceof ApiError && error.status === 429) {
        reviewCooldownUntil = Date.now() + RATE_LIMIT_COOLDOWN_MS;
      }
      // Ratings are optional presentation data. Never convert an error into fake ratings.
      return {};
    })
    .finally(() => {
      if (reviewBatchRequests.get(key) === request) reviewBatchRequests.delete(key);
    });
  reviewBatchRequests.set(key, request);
  return request;
};

const getReviewSummaries = async (products: Product[]): Promise<Record<string, ReviewSummary>> => {
  if (!products.length) return {};
  const uniqueIds = [...new Set(products.map(product => product.id))];
  const batches: string[][] = [];
  for (let offset = 0; offset < uniqueIds.length; offset += REVIEW_SUMMARY_BATCH_SIZE) {
    batches.push(uniqueIds.slice(offset, offset + REVIEW_SUMMARY_BATCH_SIZE));
  }
  const summaries: Record<string, ReviewSummary> = {};
  for (let index = 0; index < batches.length; index += REVIEW_SUMMARY_CONCURRENCY) {
    const responses = await Promise.all(
      batches.slice(index, index + REVIEW_SUMMARY_CONCURRENCY).map(getReviewBatch)
    );
    Object.assign(summaries, ...responses);
  }
  return summaries;
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
    const { availability } = await retryOnce(() =>
      inventoryRepository.getAvailabilityForProducts(products.map(product => product.id))
    );
    const byVariantId = new Map(availability.map(item => [item.variantId, item.available]));
    return products.map(product => ({ ...product, variants: product.variants.map(variant => ({
      ...variant, available: byVariantId.has(variant.id) ? byVariantId.get(variant.id) === true : undefined,
    })) }));
  } catch {
    return products;
  }
};

export const productRepository = {
  async getHomepageProducts(): Promise<Product[]> {
    if (homepageCache && homepageCache.expiresAt > Date.now()) return homepageCache.products;
    if (homepageRequest) return homepageRequest;
    homepageRequest = (async () => {
      const products = selectHomepageProducts(await getCatalogue());
      const [availableProducts, summaries] = await Promise.all([
        withHomepageAvailability(products),
        getReviewSummaries(products),
      ]);
      return applyReviewSummaries(availableProducts, summaries);
    })().then(products => {
      homepageCache = { expiresAt: Date.now() + DISPLAY_INVENTORY_TTL_MS, products };
      return products;
    }).finally(() => { homepageRequest = null; });
    return homepageRequest;
  },

  async getAllProducts(): Promise<Product[]> {
    // Snapshot and in-flight request are shared across rapid route transitions.
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

// Explicit reset is used only by tests to avoid cross-case module cache leakage.
export const resetPublicProductCachesForTests = (): void => {
  publishedShopCache = null;
  publishedShopRequest = null;
  availabilityRequest = null;
  availabilityCache = null;
  availabilityCooldownUntil = 0;
  homepageCache = null;
  homepageRequest = null;
  reviewBatchCache.clear();
  reviewBatchRequests.clear();
  reviewCooldownUntil = 0;
};
