export interface Product {
  id: string
  name: string
  category: string
  subcategory?: string
  price: number
  originalPrice: number
  discount: number
  weight: string
  unit: string
  image: string
  rating: number
  reviewCount: number
  description: string
  inStock: boolean
  badge?: string
  nutrition?: Record<string, string>
  tags?: string[]
  // --- Monetization fields ---
  vendorId?: string          // which local shop/brand supplies this product
  commissionPercent?: number // % platform earns per sale of this item
  sponsored?: boolean        // true if vendor paid to feature this product
}

export interface Category {
  id: string
  name: string
  icon: string
  image: string
  color: string
  productCount: number
  slug: string
}

export interface CartItem {
  product: Product
  quantity: number
}

export interface Address {
  id: string
  label: string
  fullAddress: string
  city: string
  pincode: string
  isDefault: boolean
}

export interface Order {
  id: string
  items: CartItem[]
  total: number
  status: 'placed' | 'packed' | 'out_for_delivery' | 'delivered' | 'cancelled'
  address: Address
  paymentMethod: string
  createdAt: Date
  estimatedDelivery?: string
}

export interface User {
  uid: string
  name: string
  email: string
  phone?: string
  photoURL?: string
  addresses?: Address[]
}

export interface Coupon {
  id: string
  code: string
  discount: number
  type: 'flat' | 'percent'
  minOrder: number
  maxDiscount?: number
  description: string
  validTill: string
}

export interface Banner {
  id: string
  image: string
  title: string
  subtitle: string
  link: string
  bgColor: string
  // --- Monetization fields ---
  sponsoredBy?: string   // vendor/brand name paying for this banner slot
  pricePaid?: number     // how much the vendor paid for this placement (admin-only view)
  expiresAt?: string     // ISO date — when the paid placement ends
}

// A local shop, brand, or seller onboarded onto the platform.
// Each sale of their product earns the platform `commissionPercent`.
export interface Vendor {
  id: string
  name: string
  contactPhone: string
  city: string
  commissionPercent: number
  totalSales: number
  totalCommissionEarned: number
  joinedAt: string
  active: boolean
}

// Paid placement: a vendor pays to have a product/banner shown prominently.
export interface AdSlot {
  id: string
  type: 'banner' | 'featured_product' | 'category_top'
  vendorId: string
  vendorName: string
  refId: string        // bannerId or productId being promoted
  price: number         // amount paid for this slot
  startDate: string
  endDate: string
  impressions: number
  clicks: number
  status: 'active' | 'scheduled' | 'expired'
}

// Referral program — "Give ₹50, Get ₹50" style growth + retention lever
export interface Referral {
  code: string
  referrerUid: string
  refereeUid?: string
  rewardForReferrer: number
  rewardForReferee: number
  status: 'pending' | 'completed'
  createdAt: string
}

// Aggregated revenue figures shown on the admin dashboard
export interface RevenueSummary {
  grossOrderValue: number
  deliveryFeeRevenue: number
  vendorCommissionRevenue: number
  adRevenue: number
  totalRevenue: number
}

export interface Toast {
  id: string
  message: string
  type: 'success' | 'error' | 'info' | 'warning'
}
