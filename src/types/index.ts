export type Department = 'men' | 'women' | 'kids' | 'unisex' | 'footwear' | 'accessories';

export interface ProductVariant {
  id: string;
  sku: string;
  size: string;
  colourName: string;
  colourHex?: string;
  stock: number;
  price?: number;
  originalPrice?: number;
  images?: string[];
}

export interface Review {
  id: string;
  userName: string;
  rating: number;
  title?: string;
  comment: string;
  createdAt: string;
  verifiedPurchase: boolean;
}

export interface Product {
  id: string;
  slug: string;
  name: string;
  brand: string;
  department: Department;
  category: string;
  subcategory?: string;
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

  vendorId?: string;
  commissionPercent?: number;
  sponsored?: boolean;

  active: boolean;
  createdAt?: string;
  updatedAt?: string;
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
}

export interface Vendor {
  id: string;
  name: string;
  email: string;
  phone: string;
  storeName: string;
  address: string;
  commissionPercent: number;
  totalSales: number;
  totalCommissionEarned: number;
  active: boolean;
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
  email: string;
  phone?: string;
  role: 'customer' | 'admin' | 'vendor';
  addresses: Address[];
  referralCode: string;
  walletBalance: number;
  createdAt: string;
}

export interface ServiceArea {
  pincode: string;
  city: string;
  state: string;
  serviceable: boolean;
  expressAvailable: boolean;
  estimatedDeliveryMinutes: number;
}

export interface RevenueSummary {
  grossOrderValue: number;
  deliveryFeeRevenue: number;
  vendorCommissionRevenue: number;
  adRevenue: number;
  totalRevenue: number;
  totalOrders: number;
  activeProducts: number;
  lowStockSkus: number;
}
