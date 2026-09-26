import type { STORE_CATEGORIES } from '../data/categories';

export type Department = 'men' | 'women' | 'kids' | 'unisex' | 'footwear' | 'accessories';

/** Canonical store categories; the validated list comes from src/data/categories.ts. */
export type StoreCategory = (typeof STORE_CATEGORIES)[number];

export interface ProductVariant {
  id: string;
  sku: string;
  size: string;
  colourName: string;
  colourHex?: string;
  stock: number;
  /** Customer-facing availability is refreshed from the server; static stock is not authoritative. */
  available?: boolean;
  price?: number;
  originalPrice?: number;
  images?: string[];
}

export interface Review {
  id: string;
  userName: string;
  rating: number;
  title?: string | null;
  comment: string;
  createdAt: string;
  updatedAt?: string;
  verifiedPurchase: boolean;
  /** Store-review moderation state; public review lists contain approved reviews only. */
  status?: 'published' | 'pending' | 'approved' | 'rejected' | 'hidden';
}

export interface Product {
  id: string;
  slug: string;
  name: string;
  brand: string;
  department: Department;
  category: string;
  subcategory?: string;
  deliveryType?: 'normal' | 'express' | 'both';
  collection?: string;

  shortDescription: string;
  description: string;
  material: string;
  fit?: string;
  pattern?: string;
  occasion?: string[];
  careInstructions: string[];

  price: number;
  originalPrice: number;
  discount: number;

  images: string[];
  thumbnail: string;

  rating: number;
  reviewCount: number;
  reviews?: Review[];

  variants: ProductVariant[];

  tags: string[];
  badge?: string;
  newArrival?: boolean;
  trending?: boolean;
  featured?: boolean;
  expressDelivery?: boolean;

  estimatedDeliveryMinutes?: number;
  returnWindowDays: number;
  exchangeAvailable: boolean;
  /** Opt-in store-controlled offer; pricing/eligibility are always verified by the server. */
  tryAtHomeAvailable?: boolean;

  // Multi-Store & Vendor Fields
  vendorId: string;
  storeName?: string;
  storeSlug?: string;
  sponsored?: boolean;

  active: boolean;
  createdAt?: string;
  updatedAt?: string;
}

export interface VendorStore {
  id: string;
  slug: string;
  storeName: string;
  ownerName?: string;
  email?: string;
  phone?: string;
  category: StoreCategory;
  address: string;
  pincode: string;
  city: string;
  rating?: number;
  reviewCount?: number;
  deliveryMinutes: number;
  bannerImage?: string;
  logoImage?: string;
  description: string;
  totalSales?: number;
  productCount?: number;
  active: boolean;
  approved: boolean;
  createdAt: string;
}

export interface CartItem {
  lineId: string;
  productId: string;
  product: Product;
  variantId: string;
  selectedSize: string;
  selectedColour: string;
  sku: string;
  quantity: number;
  unitPrice: number;
  tryAtHomeVariantIds?: string[];
  tryAtHomeTermsAccepted?: boolean;
}

export interface Address {
  id: string;
  name: string;
  phone: string;
  street: string;
  city: string;
  state: string;
  pincode: string;
  isDefault?: boolean;
  type?: 'home' | 'work' | 'other';
}

export type OrderStatus =
  | 'placed'
  | 'confirmed'
  | 'packed'
  | 'ready_for_pickup'
  | 'out_for_delivery'
  | 'delivered'
  | 'cancelled'
  | 'return_requested'
  | 'returned'
  | 'exchange_requested'
  | 'exchanged';

export interface OrderStatusHistory {
  status: OrderStatus;
  timestamp: string;
  note?: string;
}

export interface Order {
  id: string;
  userId: string;
  items: CartItem[];
  address: Address;
  paymentMethod: 'upi' | 'cod' | 'card' | 'wallet';
  paymentStatus: 'pending' | 'paid' | 'failed' | 'refunded';
  subtotal: number;
  discount: number;
  walletAmount: number;
  deliveryFee: number;
  taxes: number;
  grandTotal: number;
  deliveryMethod: 'express' | 'standard';
  estimatedDelivery: string;
  status: OrderStatus;
  statusHistory: OrderStatusHistory[];
  createdAt: string;
  updatedAt: string;
  razorpayOrderId?: string;
  razorpayPaymentId?: string;
  paymentVerifiedAt?: string;
}

export interface AdSlot {
  id: string;
  title: string;
  type: 'banner' | 'featured_product' | 'category_top';
  imageUrl: string;
  targetUrl: string;
  vendorId?: string;
  impressions: number;
  clicks: number;
  active: boolean;
  startDate: string;
  endDate: string;
}

export interface Coupon {
  code: string;
  discountType: 'percentage' | 'fixed';
  value: number;
  minOrderValue: number;
  maxDiscount?: number;
  active: boolean;
  expiryDate: string;
}

export interface UserProfile {
  uid: string;
  name: string;
  email?: string;
  phone?: string;
  role: 'customer';
  addresses?: Address[];
  createdAt?: string;
  emailVerified?: boolean;
  hasPassword?: boolean;
}

export type DeliveryZoneEnforcementMode = 'pincode' | 'polygon';

export interface DeliveryCoordinates {
  latitude: number;
  longitude: number;
}

export interface ServiceArea {
  pincode: string;
  city?: string;
  state?: string;
  serviceable: boolean;
  expressAvailable?: boolean;
  estimatedDeliveryMinutes?: number;
  enforcementMode?: DeliveryZoneEnforcementMode;
  locationRequired?: boolean;
  zoneId?: string;
  zoneName?: string;
  reason?: 'unsupported_pincode' | 'location_required' | 'outside_delivery_zone';
}

export interface ServiceabilityApiResponse extends ServiceArea {
  success: true;
}

export interface InventoryAvailability {
  productId: string;
  variantId: string;
  available: boolean;
}

export interface InventoryAvailabilityResponse {
  success: true;
  availability: InventoryAvailability[];
}
