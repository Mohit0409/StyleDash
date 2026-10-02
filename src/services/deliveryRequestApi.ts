import { apiFetch, apiJson } from './apiClient';
import type { CreatePaymentOrderResponse } from './paymentApi';

export type OutsideDeliveryRequestStatus =
  | 'requested'
  | 'quoted'
  | 'payment_pending'
  | 'paid'
  | 'cancelled'
  | 'rejected';

export interface OutsideDeliveryAddress {
  name: string;
  phone: string;
  street: string;
  city: string;
  state: string;
  pincode: string;
}

export interface OutsideDeliveryQuote {
  unitPrice: number;
  productSubtotal: number;
  deliveryFee: number;
  grandTotal: number;
  note?: string;
  estimatedDelivery?: string;
}
export interface OutsideDeliveryRequest {
  id: string;
  productId: string;
  productName: string;
  productSlug: string;
  variantId: string;
  size: string;
  colourName: string;
  quantity: number;
  unitPrice: number;
  productSubtotal: number;
  storeId?: string;
  storeName?: string;
  storeSlug?: string;
  address: OutsideDeliveryAddress;
  status: OutsideDeliveryRequestStatus;
  quote?: OutsideDeliveryQuote;
  createdAt: string;
  updatedAt: string;
  quotedAt?: string;
  paymentRequestedAt?: string;
  paidAt?: string;
  cancelledAt?: string;
  rejectedAt?: string;
  rejectionReason?: string;
  orderId?: string;
}
export const deliveryRequestApi = {
  async list(): Promise<OutsideDeliveryRequest[]> {
    const result = await apiFetch<{ requests: OutsideDeliveryRequest[] }>('/api/outside-delivery-requests');
    return result.requests;
  },

  async create(payload: {
    productId: string;
    variantId: string;
    quantity: number;
    address: OutsideDeliveryAddress;
  }): Promise<{ idempotent: boolean; request: OutsideDeliveryRequest }> {
    return apiJson('/api/outside-delivery-requests', 'POST', payload);
  },

  async cancel(id: string): Promise<OutsideDeliveryRequest> {
    const result = await apiJson<{ request: OutsideDeliveryRequest }>(
      `/api/outside-delivery-requests/${encodeURIComponent(id)}/cancel`,
      'POST',
      {},
    );
    return result.request;
  },

  async createPaymentOrder(
    id: string,
    paymentMethod: 'upi' | 'card',
    idempotencyKey: string,
  ): Promise<CreatePaymentOrderResponse> {
    return apiFetch<CreatePaymentOrderResponse>(
      `/api/outside-delivery-requests/${encodeURIComponent(id)}/create-order`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Idempotency-Key': idempotencyKey },
        body: JSON.stringify({ paymentMethod }),
      },
    );
  },
};
