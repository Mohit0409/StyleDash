import { apiFetch, ApiError } from './apiClient';

export interface CheckoutItemInput {
  productId: string;
  variantId: string;
  quantity: number;
}

export interface CheckoutAddressInput {
  name: string;
  phone: string;
  street: string;
  city: string;
  pincode: string;
}

export interface CheckoutIntent {
  items: CheckoutItemInput[];
  address: CheckoutAddressInput;
  deliveryMethod: 'express' | 'standard';
  couponCode: string | null;
  paymentMethod: 'cod' | 'upi' | 'card';
}

export interface TrustedOrderItem {
  productId: string;
  productName: string;
  productSlug: string;
  variantId: string;
  sku: string;
  size: string;
  colourName: string;
  quantity: number;
  unitPrice: number;
  lineTotal: number;
}

export interface ServerOrder {
  id: string;
  userId: string;
  items: TrustedOrderItem[];
  address: CheckoutAddressInput & { id: string; state: string };
  paymentMethod: 'cod' | 'upi' | 'card';
  paymentStatus: 'pending' | 'paid' | 'failed' | 'refunded';
  subtotal: number;
  discount: number;
  walletAmount: number; // Retained for historical persisted-order compatibility.
  deliveryFee: number;
  taxes: number;
  grandTotal: number;
  deliveryMethod: 'express' | 'standard' | 'none';
  estimatedDelivery: string;
  status: string;
  statusHistory: Array<{ status: string; timestamp: string; note?: string }>;
  fulfillments?: Array<{ shopName: string; status: 'NEW' | 'PROCESSING' | 'READY' | 'SHIPPED' | 'DELIVERED'; updatedAt?: string | null }>;
  createdAt: string;
  updatedAt: string;
  razorpayOrderId?: string;
  razorpayPaymentId?: string;
  paymentVerifiedAt?: string;
  isPaymentTestOrder?: boolean;
  fulfillmentRequired?: boolean;
  adminLabels?: string[];
  inventoryCommitted?: boolean;
  inventoryReleasedAt?: string;
  refundId?: string;
  refundAmount?: number;
  refundCurrency?: string;
  refundProcessedAt?: string;
}

export interface CreatePaymentOrderResponse {
  success: true;
  styleDashOrderId: string;
  razorpayOrderId: string;
  keyId: string;
  amount: number;
  currency: string;
  receipt: string;
  trustedTotals: {
    subtotal: number;
    discount: number;
    deliveryFee: number;
    taxes: number;
    grandTotal: number;
  };
}

export interface RazorpaySuccessResponse {
  razorpay_payment_id: string;
  razorpay_order_id: string;
  razorpay_signature: string;
}

interface RazorpayFailureResponse {
  error?: { description?: string };
}

interface RazorpayOptions {
  key: string;
  amount: number;
  currency: string;
  name: string;
  description: string;
  order_id: string;
  prefill: { name: string; email?: string; contact: string };
  theme: { color: string };
  modal: { ondismiss: () => void };
  method: { upi: boolean; card: boolean; netbanking: boolean; wallet: boolean };
  handler: (response: RazorpaySuccessResponse) => void;
}

export interface RazorpayInstance {
  open: () => void;
  on: (event: 'payment.failed', handler: (response: RazorpayFailureResponse) => void) => void;
}

export type RazorpayConstructor = new (options: RazorpayOptions) => RazorpayInstance;

const RAZORPAY_CHECKOUT_SRC = 'https://checkout.razorpay.com/v1/checkout.js';
let razorpayLoader: Promise<RazorpayConstructor> | null = null;

async function loadRazorpayCheckout(): Promise<RazorpayConstructor> {
  const existing = (window as unknown as { Razorpay?: RazorpayConstructor }).Razorpay;
  if (existing) return existing;
  if (!razorpayLoader) {
    razorpayLoader = new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = RAZORPAY_CHECKOUT_SRC;
      script.async = true;
      script.onload = () => {
        const Constructor = (window as unknown as { Razorpay?: RazorpayConstructor }).Razorpay;
        if (Constructor) resolve(Constructor);
        else reject(new PaymentApiError('Razorpay Checkout could not be loaded.', 'checkout_unavailable'));
      };
      script.onerror = () => reject(new PaymentApiError('Razorpay Checkout could not be loaded.', 'checkout_unavailable'));
      document.head.appendChild(script);
    });
  }
  try {
    return await razorpayLoader;
  } catch (error) {
    razorpayLoader = null;
    throw error;
  }
}

export class PaymentApiError extends Error {
  code: string;
  status: number;

  constructor(message: string, code = 'payment_request_failed', status = 0) {
    super(message);
    this.name = 'PaymentApiError';
    this.code = code;
    this.status = status;
  }
}

async function postJson<T>(
  endpoint: string,
  body: unknown,
  idempotencyKey?: string,
  fetcher: typeof fetch = fetch,
): Promise<T> {
  try {
    const headers = {
      'Content-Type': 'application/json',
      ...(idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : {}),
    };
    return await apiFetch<T>(endpoint, {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
    }, fetcher);
  } catch (error) {
    if (error instanceof ApiError) throw new PaymentApiError(error.message, error.code, error.status);
    throw new PaymentApiError('The secure checkout server is unavailable. Please try again.', 'server_unavailable');
  }
}

export function createPaymentOrder(
  intent: CheckoutIntent,
  idempotencyKey: string,
  fetcher?: typeof fetch,
): Promise<CreatePaymentOrderResponse> {
  return postJson('/api/create-order', intent, idempotencyKey, fetcher);
}

export function placeCodOrder(
  intent: CheckoutIntent,
  idempotencyKey: string,
  fetcher?: typeof fetch,
): Promise<{ success: true; idempotent: boolean; order: ServerOrder }> {
  return postJson('/api/place-cod-order', intent, idempotencyKey, fetcher);
}

export function verifyPayment(
  response: RazorpaySuccessResponse,
  styleDashOrderId: string,
  fetcher?: typeof fetch,
): Promise<{ success: true; pending?: boolean; idempotent: boolean; order: ServerOrder }> {
  return postJson('/api/verify-payment', { ...response, styleDashOrderId }, undefined, fetcher);
}

export async function openRazorpayCheckout(
  order: CreatePaymentOrderResponse,
  customer: { name: string; email?: string; phone: string },
  paymentMethod: 'upi' | 'card',
  Constructor?: RazorpayConstructor,
): Promise<RazorpaySuccessResponse> {
  const RazorpayCheckout = Constructor || await loadRazorpayCheckout();

  return new Promise((resolve, reject) => {
    let settled = false;
    const finish = (callback: () => void) => {
      if (settled) return;
      settled = true;
      callback();
    };
    const instance = new RazorpayCheckout({
      key: order.keyId,
      amount: order.amount,
      currency: order.currency,
      name: 'StyleDash',
      description: `StyleDash order ${order.styleDashOrderId}`,
      order_id: order.razorpayOrderId,
      prefill: { name: customer.name, email: customer.email, contact: customer.phone },
      theme: { color: '#84cc16' },
      method: {
        upi: paymentMethod === 'upi',
        card: paymentMethod === 'card',
        netbanking: false,
        wallet: false,
      },
      modal: {
        ondismiss: () => finish(() => reject(new PaymentApiError('Payment was cancelled.', 'payment_cancelled'))),
      },
      handler: (response) => finish(() => resolve(response)),
    });
    instance.on('payment.failed', (response) => {
      const description = response.error?.description || 'Payment failed. Please try again.';
      finish(() => reject(new PaymentApiError(description, 'payment_failed')));
    });
    instance.open();
  });
}
