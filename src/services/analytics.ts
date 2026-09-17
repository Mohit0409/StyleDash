import { initializeAnalytics, isSupported, logEvent, type Analytics } from 'firebase/analytics';
import type { ServerOrder } from './paymentApi';
import { getFirebaseApp } from './firebaseClient';

const MEASUREMENT_ID = import.meta.env.VITE_FIREBASE_MEASUREMENT_ID || 'G-PSHXB46P50';
const PURCHASE_STORAGE_KEY = 'vibe4you.ga4.purchases.v1';
const PRODUCTION_HOSTS = new Set(['vibe4you.in', 'www.vibe4you.in']);
const ALLOWED_PARAM_KEYS = new Set([
  'affiliation', 'coupon', 'currency', 'item_list_id', 'item_list_name', 'items',
  'method', 'page_location', 'page_path', 'page_title', 'payment_type',
  'promotion_id', 'search_term', 'shipping', 'store_category', 'store_id',
  'store_name', 'tax', 'transaction_id', 'value',
]);

type AnalyticsItem = Record<string, string | number | boolean>;
type AnalyticsParams = Record<string, unknown>;

let analyticsPromise: Promise<Analytics | null> | null = null;

const safeText = (value: unknown, maximum = 160): string | undefined => {
  if (typeof value !== 'string') return undefined;
  const cleaned = value.trim().replace(/\s+/g, ' ');
  return cleaned ? cleaned.slice(0, maximum) : undefined;
};

const safeNumber = (value: unknown): number | undefined => {
  if (typeof value !== 'number' || !Number.isFinite(value)) return undefined;
  return value;
};

const isAnalyticsRuntime = (): boolean => {
  if (typeof window === 'undefined' || !MEASUREMENT_ID) return false;
  if (window.location.pathname === '/reset-password') return false;
  return PRODUCTION_HOSTS.has(window.location.hostname.toLowerCase());
};

const sanitizeItem = (source: Record<string, unknown>): AnalyticsItem => {
  const allowed = new Set([
    'affiliation', 'coupon', 'index', 'item_brand', 'item_category', 'item_id',
    'item_list_name', 'item_name', 'item_variant', 'price', 'quantity',
  ]);
  const result: AnalyticsItem = {};
  for (const [key, value] of Object.entries(source)) {
    if (!allowed.has(key)) continue;
    if (typeof value === 'string') {
      const cleaned = safeText(value, 200);
      if (cleaned !== undefined) result[key] = cleaned;
    } else if (typeof value === 'number' && Number.isFinite(value)) {
      result[key] = value;
    } else if (typeof value === 'boolean') {
      result[key] = value;
    }
  }
  return result;
};

const sanitizeParams = (source: AnalyticsParams): AnalyticsParams => {
  const result: AnalyticsParams = {};
  for (const [key, value] of Object.entries(source)) {
    if (!ALLOWED_PARAM_KEYS.has(key)) continue;
    if (key === 'search_term') {
      if (typeof value === 'string' && value.trim()) result.search_term = 'site_search';
      continue;
    }
    if (Array.isArray(value)) {
      result[key] = value
        .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === 'object' && !Array.isArray(item))
        .slice(0, 200)
        .map(sanitizeItem);
      continue;
    }
    if (typeof value === 'string') {
      const cleaned = safeText(value, 500);
      if (cleaned !== undefined) result[key] = cleaned;
    } else if (typeof value === 'number' && Number.isFinite(value)) {
      result[key] = value;
    } else if (typeof value === 'boolean') {
      result[key] = value;
    }
  }
  return result;
};

const normalizeLegacyCartEvent = (eventName: string, params: AnalyticsParams): AnalyticsParams => {
  if (!['add_to_cart', 'remove_from_cart'].includes(eventName) || Array.isArray(params.items)) return params;
  const itemId = safeText(params.item_id, 200);
  if (!itemId) return params;

  const quantity = safeNumber(params.quantity) ?? 1;
  const price = safeNumber(params.price);
  const size = safeText(params.size, 80);
  const colour = safeText(params.colour, 80);
  const item: AnalyticsItem = { item_id: itemId, quantity };
  const itemName = safeText(params.item_name, 200);
  const category = safeText(params.item_category, 120);
  if (itemName) item.item_name = itemName;
  if (category) item.item_category = category;
  if (price !== undefined) item.price = price;
  if (size || colour) item.item_variant = [size, colour].filter(Boolean).join(' / ');

  return {
    currency: 'INR',
    ...(price !== undefined ? { value: price * quantity } : {}),
    items: [item],
  };
};

const getAnalyticsClient = async (): Promise<Analytics | null> => {
  if (!isAnalyticsRuntime()) return null;
  if (!analyticsPromise) {
    analyticsPromise = isSupported()
      .then((supported) => supported ? initializeAnalytics(getFirebaseApp(), { config: { send_page_view: false } }) : null)
      .catch(() => null);
  }
  return analyticsPromise;
};

export const trackEvent = async (eventName: string, eventParams: AnalyticsParams = {}): Promise<boolean> => {
  const normalized = normalizeLegacyCartEvent(eventName, eventParams);
  const sanitized = sanitizeParams(normalized);
  if (import.meta.env.DEV) console.debug(`[Analytics] ${eventName}`, sanitized);
  const analytics = await getAnalyticsClient();
  if (!analytics) return false;
  try {
    logEvent(analytics, eventName, sanitized);
    return true;
  } catch {
    return false;
  }
};

const sanitizePagePath = (pathWithSearch: string): string => {
  const rawPath = pathWithSearch.split('?', 1)[0] || '/';
  const normalized = rawPath.startsWith('/') ? rawPath.slice(0, 500) : `/${rawPath.slice(0, 499)}`;
  return normalized
    .replace(/^\/order-success\/[^/]+$/, '/order-success/:orderId')
    .replace(/^\/orders\/[^/]+\/track$/, '/orders/:orderId/track');
};

export const trackPageView = async (pathWithSearch: string): Promise<boolean> => {
  if (typeof window === 'undefined') return false;
  const safePath = sanitizePagePath(pathWithSearch);
  return trackEvent('page_view', {
    page_location: `${window.location.origin}${safePath}`,
    page_path: safePath,
    page_title: document.title.slice(0, 200),
  });
};

const readTrackedPurchases = (): string[] => {
  if (typeof window === 'undefined') return [];
  try {
    const parsed = JSON.parse(window.localStorage.getItem(PURCHASE_STORAGE_KEY) || '[]');
    return Array.isArray(parsed)
      ? parsed.filter((value): value is string => typeof value === 'string').slice(-100)
      : [];
  } catch {
    return [];
  }
};

export const trackPurchase = async (order: ServerOrder): Promise<boolean> => {
  if (!order.id || order.isPaymentTestOrder || order.fulfillmentRequired === false) return false;
  if (order.paymentMethod !== 'cod' && order.paymentStatus !== 'paid') return false;
  if (['cancelled', 'returned'].includes(order.status)) return false;
  const tracked = readTrackedPurchases();
  if (tracked.includes(order.id)) return true;

  const sent = await trackEvent('purchase', {
    transaction_id: order.id,
    affiliation: 'Vibe4You',
    currency: 'INR',
    value: order.grandTotal,
    tax: order.taxes,
    shipping: order.deliveryFee,
    payment_type: order.paymentMethod,
    items: order.items.map((item) => ({
      item_id: item.productId,
      item_name: item.productName,
      item_variant: [item.size, item.colourName].filter(Boolean).join(' / '),
      affiliation: item.storeName || 'Vibe4You',
      price: item.unitPrice,
      quantity: item.quantity,
    })),
  });

  if (sent && typeof window !== 'undefined') {
    try {
      window.localStorage.setItem(PURCHASE_STORAGE_KEY, JSON.stringify([...tracked, order.id].slice(-100)));
    } catch {
      // Analytics deduplication storage is best-effort only.
    }
  }
  return sent;
};
