import { apiFetch, apiJson } from './apiClient';
import { ServerOrder } from './paymentApi';
import { Product, UserProfile, VendorStore } from '../types';

export const orderApi = {
  async mine(): Promise<ServerOrder[]> {
    return (await apiFetch<{ success: true; orders: ServerOrder[] }>('/api/orders')).orders;
  },
  async one(id: string): Promise<ServerOrder> {
    return (await apiFetch<{ success: true; order: ServerOrder }>(`/api/orders/${encodeURIComponent(id)}`)).order;
  },
};


export type ReturnRequestType = 'SIZE_EXCHANGE' | 'ISSUE_RETURN';
export type ReturnRequestStatus = 'REQUESTED' | 'UNDER_REVIEW' | 'APPROVED' | 'REJECTED' | 'PICKUP_PENDING' | 'RECEIVED' | 'REFUND_PENDING' | 'REFUNDED' | 'EXCHANGED' | 'CANCELLED';
export interface ReturnRequest {
  id: string; orderId: string; shopName: string; productId: string; productName: string; variantId: string;
  requestType: ReturnRequestType; reason: string; details?: string | null; quantity: number; unitPrice: number;
  itemSubtotal: number; status: ReturnRequestStatus; sellerNote?: string | null; adminNote?: string | null;
  createdAt: string; updatedAt: string; reviewedAt?: string; resolvedAt?: string;
}

export const returnApi = {
  async mine(): Promise<ReturnRequest[]> {
    return (await apiFetch<{ success: true; requests: ReturnRequest[] }>('/api/return-requests')).requests;
  },
  async create(orderId: string, payload: { productId: string; variantId: string; requestType: ReturnRequestType; reason: string; details?: string; quantity?: number }): Promise<ReturnRequest> {
    return (await apiJson<{ success: true; request: ReturnRequest }>(`/api/orders/${encodeURIComponent(orderId)}/return-requests`, 'POST', payload)).request;
  },
  async requestCancellation(orderId: string, payload: { reason: 'CUSTOMER_REQUEST' | 'ORDERED_BY_MISTAKE'; details?: string }): Promise<NonNullable<ServerOrder['cancellationRequest']>> {
    return (await apiJson<{ success: true; cancellationRequest: NonNullable<ServerOrder['cancellationRequest']> }>(`/api/orders/${encodeURIComponent(orderId)}/cancellation-request`, 'POST', payload)).cancellationRequest;
  },
};

export type ShopApplicationStatus =
  | 'DRAFT'
  | 'SUBMITTED'
  | 'UNDER_REVIEW'
  | 'APPROVED'
  | 'REJECTED'
  | 'ACTIVE'
  | 'SUSPENDED';

export interface ShopApplication {
  id: string;
  status: ShopApplicationStatus;
  shopName: string;
  ownerName: string;
  registeredMobile?: string | null;
  registeredEmail?: string | null;
  category: string;
  description: string;
  address: string;
  city: string;
  state: string;
  pincode: string;
  businessInformation?: string | null;
  rejectionReason?: string | null;
  createdAt: string;
  updatedAt: string;
  submittedAt?: string | null;
}

export type ShopApplicationDraft = Pick<
  ShopApplication,
  'shopName' | 'ownerName' | 'category' | 'description' | 'address' | 'city' | 'state' | 'pincode'
> & { businessInformation?: string };

export const vendorApplicationApi = {
  async mine(): Promise<ShopApplication | null> {
    return (await apiFetch<{ success: true; application: ShopApplication | null }>('/api/vendor-applications/me')).application;
  },
  async createDraft(payload: ShopApplicationDraft): Promise<ShopApplication> {
    return (await apiJson<{ success: true; application: ShopApplication }>('/api/vendor-applications', 'POST', payload)).application;
  },
  async updateDraft(payload: ShopApplicationDraft): Promise<ShopApplication> {
    return (await apiJson<{ success: true; application: ShopApplication }>('/api/vendor-applications/me', 'PATCH', payload)).application;
  },
  async submit(): Promise<ShopApplication> {
    return (await apiJson<{ success: true; application: ShopApplication }>('/api/vendor-applications/me/submit', 'POST', {})).application;
  },
};

export const publicStoreApi = {
  async active(): Promise<VendorStore[]> {
    return (await apiFetch<{ success: true; stores: VendorStore[] }>('/api/stores/active')).stores;
  },
};

export const shopProductApi = {
  async published(): Promise<Product[]> {
    return (await apiFetch<{ success: true; products: Product[] }>('/api/shop-products/published')).products;
  },
  async mine(): Promise<SellerProduct[]> {
    return (await apiFetch<{ success: true; products: SellerProduct[] }>('/api/shop-products')).products;
  },
  async createDraft(payload: SellerProductDraft): Promise<SellerProduct> {
    return (await apiJson<{ success: true; product: SellerProduct }>('/api/shop-products', 'POST', payload)).product;
  },
  async updateDraft(id: string, payload: SellerProductDraft): Promise<SellerProduct> {
    return (await apiJson<{ success: true; product: SellerProduct }>(`/api/shop-products/${encodeURIComponent(id)}`, 'PATCH', payload)).product;
  },
  async submit(id: string): Promise<SellerProduct> {
    return (await apiJson<{ success: true; product: SellerProduct }>(`/api/shop-products/${encodeURIComponent(id)}/submit`, 'POST', {})).product;
  },
};

export type SellerProductStatus = 'DRAFT' | 'SUBMITTED' | 'UNDER_REVIEW' | 'APPROVED' | 'PUBLISHED' | 'REJECTED';

export interface SellerProductDraft {
  name: string;
  description: string;
  brand?: string;
  department: Product['department'];
  category: string;
  pricePaise: number;
  originalPricePaise: number;
  inventory: number;
  size: string;
  colourName: string;
  colourHex?: string;
  imageUrls: string[];
  attributes: Record<string, string>;
}

export interface SellerProduct extends SellerProductDraft {
  id: string;
  slug: string;
  applicationId: string;
  status: SellerProductStatus;
  rejectionReason?: string | null;
  createdAt: string;
  updatedAt: string;
  submittedAt?: string | null;
  publishedAt?: string | null;
}

export interface SellerOrderItem {
  productId: string; productName?: string; productSlug?: string; variantId?: string; sku?: string;
  size?: string; colourName?: string; quantity: number; unitPrice: number; lineTotal: number;
}

export type SellerFulfillmentStatus = 'NEW' | 'PROCESSING' | 'READY' | 'SHIPPED' | 'DELIVERED';

export interface SellerFulfillment {
  status: SellerFulfillmentStatus;
  updatedAt?: string | null;
  allowedNextStatuses: SellerFulfillmentStatus[];
  shipping?: { carrier: string; trackingNumber: string } | null;
}

export interface SellerOrder {
  id: string; status?: string; paymentStatus?: string; paymentMethod?: string; deliveryMethod?: string;
  createdAt?: string; updatedAt?: string; sellerSubtotal: number; items: SellerOrderItem[];
  fulfillment: SellerFulfillment;
  cancellationRequest?: ServerOrder['cancellationRequest'];
  address: { name?: string; phone?: string; street?: string; city?: string; state?: string; pincode?: string };
}

export const sellerOrderApi = {
  async mine(): Promise<SellerOrder[]> {
    return (await apiFetch<{ success: true; orders: SellerOrder[] }>('/api/seller-orders')).orders;
  },
  async updateFulfillment(id: string, status: SellerFulfillmentStatus, shipping?: { carrier: string; trackingNumber: string }): Promise<SellerFulfillment> {
    const payload = shipping ? { status, ...shipping } : { status };
    return (await apiJson<{ success: true; fulfillment: SellerFulfillment }>(`/api/seller-orders/${encodeURIComponent(id)}/fulfillment`, 'PATCH', payload)).fulfillment;
  },
};

export const sellerReturnApi = {
  async mine(): Promise<ReturnRequest[]> {
    return (await apiFetch<{ success: true; requests: ReturnRequest[] }>('/api/seller-return-requests')).requests;
  },
  async addNote(id: string, note: string): Promise<ReturnRequest> {
    return (await apiJson<{ success: true; request: ReturnRequest }>(`/api/seller-return-requests/${encodeURIComponent(id)}`, 'PATCH', { note })).request;
  },
};

export const profileApi = {
  async get(): Promise<UserProfile> {
    return (await apiFetch<{ success: true; profile: UserProfile }>('/api/profile')).profile;
  },
  async update(payload: Record<string, unknown>): Promise<UserProfile> {
    return (await apiJson<{ success: true; profile: UserProfile }>('/api/profile', 'PATCH', payload)).profile;
  },
};
