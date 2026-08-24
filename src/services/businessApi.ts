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
  async requests(): Promise<SellerProductChangeRequest[]> {
    return (await apiFetch<{ success: true; requests: SellerProductChangeRequest[] }>('/api/shop-product-requests')).requests;
  },
  async requestEdit(id: string, payload: SellerProductChangeDraft): Promise<SellerProductChangeRequest> {
    return (await apiJson<{ success: true; request: SellerProductChangeRequest }>(`/api/shop-products/${encodeURIComponent(id)}/edit-request`, 'POST', payload)).request;
  },
  async requestUnpublish(id: string): Promise<SellerProductChangeRequest> {
    return (await apiJson<{ success: true; request: SellerProductChangeRequest }>(`/api/shop-products/${encodeURIComponent(id)}/unpublish-request`, 'POST', {})).request;
  },
  async setStock(id: string, stock: number): Promise<SellerInventoryUpdate> {
    return (await apiJson<{ success: true; inventory: SellerInventoryUpdate }>(`/api/shop-products/${encodeURIComponent(id)}/stock`, 'PATCH', { stock })).inventory;
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

export type SellerProductChangeDraft = Omit<SellerProductDraft, 'inventory'>;
export type SellerProductChangeAction = 'EDIT' | 'UNPUBLISH';
export type SellerProductChangeStatus = 'SUBMITTED' | 'UNDER_REVIEW' | 'APPROVED' | 'REJECTED';

export interface SellerProductChangeRequest {
  id: string;
  productId: string;
  applicationId: string;
  productName?: string;
  action: SellerProductChangeAction;
  status: SellerProductChangeStatus;
  proposedProduct?: SellerProductChangeDraft | null;
  rejectionReason?: string | null;
  createdAt: string;
  updatedAt: string;
  submittedAt: string;
  reviewedAt?: string | null;
}

export interface SellerInventoryUpdate {
  productId: string;
  variantId: string;
  before: number;
  stock: number;
}

export const profileApi = {
  async get(): Promise<UserProfile> {
    return (await apiFetch<{ success: true; profile: UserProfile }>('/api/profile')).profile;
  },
  async update(payload: Record<string, unknown>): Promise<UserProfile> {
    return (await apiJson<{ success: true; profile: UserProfile }>('/api/profile', 'PATCH', payload)).profile;
  },
};
