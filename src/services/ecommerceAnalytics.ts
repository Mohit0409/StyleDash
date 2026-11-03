import type { CartItem, Product, ProductVariant } from '../types';
import type { ServerOrder } from './paymentApi';
import { readAnalyticsConsent, trackEvent } from './analytics';

const currency = 'INR';

const money = (value: number): number => Number.isFinite(value) && value >= 0
  ? Math.round(value * 100) / 100
  : 0;

export const itemFromProduct = (product: Product, variant?: ProductVariant, quantity = 1) => ({
  item_id: product.id,
  item_name: product.name,
  item_category: product.category,
  ...(variant ? { item_variant: variant.sku || variant.id } : {}),
  price: money(variant?.price ?? product.price),
  quantity,
});

const itemFromCart = (item: CartItem) => ({
  item_id: item.productId,
  item_name: item.product.name,
  item_category: item.product.category,
  item_variant: item.sku || item.variantId,
  price: money(item.unitPrice),
  quantity: item.quantity,
});

export const trackProductView = (product: Product): void => {
  trackEvent('view_item', {
    currency,
    value: money(product.price),
    items: [itemFromProduct(product)],
  });
};

export const trackCartAddition = (product: Product, variant: ProductVariant, quantity: number): void => {
  const price = money(variant.price ?? product.price);
  trackEvent('add_to_cart', {
    currency,
    value: money(price * quantity),
    items: [itemFromProduct(product, variant, quantity)],
  });
};

export const trackCheckoutBegin = (items: CartItem[], total: number): void => {
  if (!items.length) return;
  trackEvent('begin_checkout', {
    currency,
    value: money(total),
    items: items.map(itemFromCart),
  });
};

// Use only verified, finalized orders. Do not count unpaid quotes, pending captures,
// review-pending transactions or test purchases as revenue.
export const eligibleForPurchaseTracking = (order: ServerOrder): boolean =>
  order.isPaymentTestOrder !== true
  && order.status !== 'payment_review_required'
  && (order.paymentStatus === 'paid'
    || (order.paymentMethod === 'cod' && order.codAdvancePaid === true))
  && Boolean(order.id && order.items.length);

export const trackVerifiedPurchase = async (order: ServerOrder): Promise<void> => {
  if (readAnalyticsConsent() !== 'accepted' || !eligibleForPurchaseTracking(order)) return;
  // The private order reference is never sent to GA4. A stable SHA-256 digest
  // lets GA4 and the browser deduplicate without exposing the raw order ID.
  if (!globalThis.crypto?.subtle) return;
  const bytes = new TextEncoder().encode(order.id);
  const digest = await globalThis.crypto.subtle.digest('SHA-256', bytes);
  const transactionId = 'v4y_' + Array.from(new Uint8Array(digest))
    .map(byte => byte.toString(16).padStart(2, '0')).join('');
  const dedupeKey = 'vibe4you_ga4_purchase_' + transactionId;
  try {
    if (window.localStorage.getItem(dedupeKey) === '1') return;
  } catch { /* Storage may be unavailable; GA4 transaction_id still deduplicates. */ }

  trackEvent('purchase', {
    transaction_id: transactionId,
    currency,
    value: money(order.grandTotal),
    shipping: money(order.deliveryFee),
    items: order.items.map(item => ({
      item_id: item.productId,
      item_name: item.productName,
      item_variant: item.sku || item.variantId,
      price: money(item.unitPrice),
      quantity: item.quantity,
    })),
  });
  try {
    window.localStorage.setItem(dedupeKey, '1');
  } catch { /* GA4 still uses the stable transaction_id. */ }
};
