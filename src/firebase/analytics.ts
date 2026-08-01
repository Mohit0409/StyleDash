import { logEvent, setUserId, setUserProperties } from 'firebase/analytics'
import { analytics } from './config'
import type { Product, Coupon } from '../types'

/**
 * Centralized analytics service.
 *
 * Every commercially-relevant action in the app should be logged here.
 * These events map to Firebase's recommended e-commerce events, which
 * means they show up automatically in:
 *   - Firebase Analytics dashboard (funnels, retention)
 *   - Google Ads (if linked) for conversion tracking & remarketing
 *   - GA4 BigQuery export (if enabled) for custom revenue analysis
 *
 * If `analytics` failed to initialize (e.g. no Firebase config yet),
 * every call here is a safe no-op — the app never breaks because of it.
 */

const track = (eventName: string, params?: Record<string, unknown>) => {
  if (!analytics) return
  try {
    logEvent(analytics, eventName, params)
  } catch {
    // Never let analytics failures affect the user experience
  }
}

// --- Identity ---

export const identifyUser = (uid: string, isAdmin: boolean) => {
  if (!analytics) return
  try {
    setUserId(analytics, uid)
    setUserProperties(analytics, { user_type: isAdmin ? 'admin' : 'customer' })
  } catch { /* no-op */ }
}

// --- Standard e-commerce funnel events (GA4 recommended event names) ---

export const trackViewItem = (product: Product) =>
  track('view_item', {
    currency: 'INR',
    value: product.price,
    items: [{ item_id: product.id, item_name: product.name, item_category: product.category, price: product.price }],
  })

export const trackViewItemList = (category: string, count: number) =>
  track('view_item_list', { item_list_name: category, items_count: count })

export const trackSearch = (searchTerm: string) =>
  track('search', { search_term: searchTerm })

export const trackAddToCart = (product: Product, quantity: number) =>
  track('add_to_cart', {
    currency: 'INR',
    value: product.price * quantity,
    items: [{ item_id: product.id, item_name: product.name, item_category: product.category, price: product.price, quantity }],
  })

export const trackRemoveFromCart = (product: Product, quantity: number) =>
  track('remove_from_cart', {
    currency: 'INR',
    value: product.price * quantity,
    items: [{ item_id: product.id, item_name: product.name, quantity }],
  })

export const trackAddToWishlist = (product: Product) =>
  track('add_to_wishlist', {
    currency: 'INR',
    value: product.price,
    items: [{ item_id: product.id, item_name: product.name }],
  })

export const trackViewCart = (value: number, itemCount: number) =>
  track('view_cart', { currency: 'INR', value, item_count: itemCount })

export const trackBeginCheckout = (value: number, itemCount: number) =>
  track('begin_checkout', { currency: 'INR', value, item_count: itemCount })

export const trackApplyCoupon = (coupon: Coupon, orderValue: number) =>
  track('select_promotion', {
    promotion_id: coupon.code,
    promotion_name: coupon.description,
    currency: 'INR',
    value: orderValue,
  })

export const trackPurchase = (orderId: string, value: number, deliveryFee: number, tax: number, itemCount: number) =>
  track('purchase', {
    transaction_id: orderId,
    currency: 'INR',
    value,
    shipping: deliveryFee,
    tax,
    item_count: itemCount,
  })

// --- Monetization-specific events (custom, not part of GA4 defaults) ---

/** Fired when a sponsored/featured product is shown to a user — drives ad billing */
export const trackAdImpression = (adSlotId: string, vendorName: string, refId: string) =>
  track('ad_impression', { ad_slot_id: adSlotId, vendor_name: vendorName, ref_id: refId })

/** Fired when a user taps/clicks a sponsored product or banner — drives CPC billing */
export const trackAdClick = (adSlotId: string, vendorName: string, refId: string) =>
  track('ad_click', { ad_slot_id: adSlotId, vendor_name: vendorName, ref_id: refId })

/** Fired when a referral code is shared or successfully redeemed */
export const trackReferralShared = (code: string) =>
  track('referral_shared', { referral_code: code })

export const trackReferralRedeemed = (code: string, rewardAmount: number) =>
  track('referral_redeemed', { referral_code: code, value: rewardAmount, currency: 'INR' })

/** Fired when a vendor signs up — useful for tracking supply-side growth */
export const trackVendorOnboarded = (vendorId: string, commissionPercent: number) =>
  track('vendor_onboarded', { vendor_id: vendorId, commission_percent: commissionPercent })
