import { describe, expect, it, vi } from 'vitest';
import {
  CheckoutIntent,
  CreatePaymentOrderResponse,
  createPaymentOrder,
  openRazorpayCheckout,
  PaymentApiError,
  placeCodOrder,
  RazorpayConstructor,
  RazorpaySuccessResponse,
  verifyPayment,
} from '../services/paymentApi';

const intent: CheckoutIntent = {
  items: [{ productId: 'sd-prod-001', variantId: 'sd-prod-001-var-2', quantity: 2 }],
  address: {
    name: 'Test Customer',
    phone: '9999999999',
    street: '123 Test Street',
    city: 'Neemuch',
    pincode: '458441',
  },
  deliveryMethod: 'express',
  couponCode: null,
  paymentMethod: 'upi',
};

const createdOrder: CreatePaymentOrderResponse = {
  success: true,
  styleDashOrderId: 'SD-TEST-001',
  razorpayOrderId: 'order_test_001',
  keyId: 'rzp_test_placeholder',
  amount: 107200,
  currency: 'INR',
  receipt: 'SD-TEST-001',
  trustedTotals: { subtotal: 946, discount: 0, deliveryFee: 79, taxes: 47, grandTotal: 1072 },
};

const jsonResponse = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

describe('payment API', () => {
  it('creates an order from IDs and quantities without browser-calculated totals', async () => {
    const fetcher = vi.fn<typeof fetch>(async () => jsonResponse(createdOrder, 201));

    await expect(createPaymentOrder(intent, 'checkout-test-001', fetcher)).resolves.toEqual(createdOrder);

    expect(fetcher).toHaveBeenCalledOnce();
    const [endpoint, request] = fetcher.mock.calls[0] as Parameters<typeof fetch>;
    expect(endpoint).toBe('/api/create-order');
    expect(new Headers(request?.headers).get('Idempotency-Key')).toBe('checkout-test-001');
    const sent = JSON.parse(String(request?.body));
    expect(sent).toEqual(intent);
    expect(sent).not.toHaveProperty('amount');
    expect(sent).not.toHaveProperty('grandTotal');
    expect(sent).not.toHaveProperty('walletAmount');
    expect(sent.items[0]).not.toHaveProperty('unitPrice');
  });

  it('surfaces a safe server validation error', async () => {
    const fetcher = vi.fn<typeof fetch>(async () => jsonResponse({
      success: false,
      code: 'unsupported_pincode',
      error: 'Delivery is not available for this pincode.',
    }, 422));

    await expect(createPaymentOrder(intent, 'checkout-test-002', fetcher)).rejects.toMatchObject({
      name: 'PaymentApiError',
      code: 'unsupported_pincode',
      status: 422,
    });
  });

  it('places COD through the authoritative backend endpoint', async () => {
    const order = { id: 'SD-COD-001', paymentMethod: 'cod', paymentStatus: 'pending' };
    const fetcher = vi.fn<typeof fetch>(async () => jsonResponse({ success: true, idempotent: false, order }, 201));

    await placeCodOrder({ ...intent, paymentMethod: 'cod' }, 'checkout-cod-001', fetcher);

    const [endpoint, request] = fetcher.mock.calls[0] as Parameters<typeof fetch>;
    expect(endpoint).toBe('/api/place-cod-order');
    expect(new Headers(request?.headers).get('Idempotency-Key')).toBe('checkout-cod-001');
    expect(JSON.parse(String(request?.body))).not.toHaveProperty('grandTotal');
  });

  it('posts all Razorpay fields for server verification', async () => {
    const fetcher = vi.fn<typeof fetch>(async () => jsonResponse({ success: true, idempotent: false, order: {} }));
    const payment: RazorpaySuccessResponse = {
      razorpay_order_id: 'order_test_001',
      razorpay_payment_id: 'pay_test_001',
      razorpay_signature: 'signature-test',
    };

    await verifyPayment(payment, 'SD-TEST-001', fetcher);

    const [endpoint, request] = fetcher.mock.calls[0] as Parameters<typeof fetch>;
    expect(endpoint).toBe('/api/verify-payment');
    expect(JSON.parse(String(request?.body))).toEqual({ ...payment, styleDashOrderId: 'SD-TEST-001' });
  });

  it('rejects a failed server-side signature verification', async () => {
    const fetcher = vi.fn<typeof fetch>(async () => jsonResponse({
      success: false,
      code: 'signature_mismatch',
      error: 'Payment verification failed.',
    }, 400));

    await expect(verifyPayment({
      razorpay_order_id: 'order_test_001',
      razorpay_payment_id: 'pay_test_001',
      razorpay_signature: 'invalid',
    }, 'SD-TEST-001', fetcher)).rejects.toMatchObject({ code: 'signature_mismatch', status: 400 });
  });
});

describe('Razorpay Checkout modal', () => {
  const customer = { name: 'Test Customer', phone: '9999999999', email: 'test@example.com' };

  const fakeConstructor = (
    trigger: (options: Record<string, unknown>, events: Record<string, (value: unknown) => void>) => void,
  ): RazorpayConstructor => {
    return class FakeRazorpay {
      private options: Record<string, unknown>;
      private events: Record<string, (value: unknown) => void> = {};

      constructor(options: Record<string, unknown>) {
        this.options = options;
      }

      on(event: string, handler: (value: unknown) => void) {
        this.events[event] = handler;
      }

      open() {
        trigger(this.options, this.events);
      }
    } as unknown as RazorpayConstructor;
  };

  it('resolves a successful modal response and limits the chosen payment method', async () => {
    const payment: RazorpaySuccessResponse = {
      razorpay_order_id: 'order_test_001',
      razorpay_payment_id: 'pay_test_001',
      razorpay_signature: 'signature-test',
    };
    const Constructor = fakeConstructor((options) => {
      expect(options.method).toEqual({ upi: true, card: false, netbanking: false, wallet: false });
      (options.handler as (value: RazorpaySuccessResponse) => void)(payment);
    });

    await expect(openRazorpayCheckout(createdOrder, customer, 'upi', Constructor)).resolves.toEqual(payment);
  });

  it('rejects when the customer dismisses the modal', async () => {
    const Constructor = fakeConstructor((options) => {
      (options.modal as { ondismiss: () => void }).ondismiss();
    });

    await expect(openRazorpayCheckout(createdOrder, customer, 'card', Constructor)).rejects.toMatchObject({
      code: 'payment_cancelled',
    });
  });

  it('rejects payment.failed without resolving a late success handler', async () => {
    const Constructor = fakeConstructor((options, events) => {
      events['payment.failed']({ error: { description: 'Card declined.' } });
      (options.handler as (value: RazorpaySuccessResponse) => void)({
        razorpay_order_id: 'late',
        razorpay_payment_id: 'late',
        razorpay_signature: 'late',
      });
    });

    const result = openRazorpayCheckout(createdOrder, customer, 'card', Constructor);
    await expect(result).rejects.toEqual(expect.objectContaining<Partial<PaymentApiError>>({
      code: 'payment_failed',
      message: 'Card declined.',
    }));
  });
});
