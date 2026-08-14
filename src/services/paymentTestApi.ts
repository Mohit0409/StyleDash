import { apiFetch } from './apiClient';
import { CreatePaymentOrderResponse } from './paymentApi';

const PRODUCT_ENDPOINT = '/api/payment-test-product/styledash-payment-test-item';

export interface PaymentTestProduct {
  id: string;
  slug: string;
  name: string;
  price: number;
  amount: number;
  currency: 'INR';
  fulfillmentRequired: false;
}

export async function getPaymentTestProduct(fetcher: typeof fetch = fetch): Promise<PaymentTestProduct> {
  const response = await apiFetch<{ success: true; product: PaymentTestProduct }>(PRODUCT_ENDPOINT, {}, fetcher);
  return response.product;
}

export function createPaymentTestOrder(
  paymentMethod: 'upi' | 'card',
  idempotencyKey: string,
  fetcher: typeof fetch = fetch,
): Promise<CreatePaymentOrderResponse> {
  return apiFetch<CreatePaymentOrderResponse>(`${PRODUCT_ENDPOINT}/create-order`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Idempotency-Key': idempotencyKey,
    },
    body: JSON.stringify({ paymentMethod }),
  }, fetcher);
}
