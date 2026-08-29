import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it, vi } from 'vitest';
import { createPaymentTestOrder, getPaymentTestProduct } from '../services/paymentTestApi';

const source = (path: string) => readFileSync(resolve(path), 'utf8');
const jsonResponse = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
  status,
  headers: { 'Content-Type': 'application/json' },
});

describe('controlled payment test API', () => {
  it('loads the server-authorized virtual item without a browser identity claim', async () => {
    const product = {
      id: 'styledash-payment-test-item',
      slug: 'styledash-payment-test-item',
      name: 'Vibe4You Payment Test Item',
      price: 10,
      amount: 1000,
      currency: 'INR' as const,
      fulfillmentRequired: false as const,
    };
    const fetcher = vi.fn<typeof fetch>(async () => jsonResponse({ success: true, product }));

    await expect(getPaymentTestProduct(fetcher)).resolves.toEqual(product);

    const [endpoint, request] = fetcher.mock.calls[0] as Parameters<typeof fetch>;
    expect(endpoint).toBe('/api/payment-test-product/styledash-payment-test-item');
    expect(request?.body).toBeUndefined();
    expect(request?.credentials).toBe('include');
  });

  it('creates only a Razorpay-method intent without browser totals or authorization fields', async () => {
    const created = {
      success: true,
      styleDashOrderId: 'SD-TEST-VALIDATION',
      razorpayOrderId: 'order_test_validation',
      keyId: 'rzp_test_placeholder',
      amount: 1000,
      currency: 'INR',
      receipt: 'SD-TEST-VALIDATION',
      trustedTotals: { subtotal: 10, discount: 0, deliveryFee: 0, taxes: 0, grandTotal: 10 },
    } as const;
    const fetcher = vi.fn<typeof fetch>(async () => jsonResponse(created, 201));

    await expect(createPaymentTestOrder('upi', 'payment-test-idempotency', fetcher)).resolves.toEqual(created);

    const [endpoint, request] = fetcher.mock.calls[0] as Parameters<typeof fetch>;
    expect(endpoint).toBe('/api/payment-test-product/styledash-payment-test-item/create-order');
    expect(new Headers(request?.headers).get('Idempotency-Key')).toBe('payment-test-idempotency');
    const payload = JSON.parse(String(request?.body));
    expect(payload).toEqual({ paymentMethod: 'upi' });
    for (const forbidden of ['email', 'userId', 'amount', 'price', 'couponCode', 'walletAmount', 'deliveryFee', 'taxes']) {
      expect(payload).not.toHaveProperty(forbidden);
    }
  });
});

describe('controlled payment test route isolation', () => {
  it('keeps the virtual item outside every normal catalogue and discovery surface', () => {
    const hiddenIdentifier = 'styledash-payment-test-item';
    const catalogueSources = [
      'src/data/products.ts',
      'server/payment-data/catalog.json',
    ];
    const discoverySources = [
      'src/pages/Home.tsx',
      'src/pages/Products.tsx',
      'src/pages/Categories.tsx',
      'src/pages/Stores.tsx',
      'src/pages/StoreDetail.tsx',
      'src/pages/Wishlist.tsx',
      'src/pages/ProductDetail.tsx',
      'src/components/Header.tsx',
      'src/components/Footer.tsx',
      'src/repositories/productRepository.ts',
      'public/robots.txt',
    ];
    for (const path of [...catalogueSources, ...discoverySources]) {
      expect(source(path), path).not.toContain(hiddenIdentifier);
      expect(source(path), path).not.toContain('Vibe4You Payment Test Item');
    }

    const app = source('src/App.tsx');
    expect(app).toContain('path="payment-test/styledash-payment-test-item"');
    expect(app).not.toContain('to="/payment-test/');
  });

  it('uses no browser storage, query email, or automatic payment trigger', () => {
    const page = source('src/pages/PaymentTestProduct.tsx');
    const api = source('src/services/paymentTestApi.ts');
    expect(`${page}\n${api}`).not.toMatch(/localStorage|sessionStorage|URLSearchParams/);
    expect(api).not.toMatch(/email|userId/);
    expect(page).toContain('onClick={startValidation}');
    expect(page).not.toMatch(/useEffect\([\s\S]*startValidation\(\)/);
    expect(page).toContain('TEST — NO FULFILLMENT REQUIRED');
  });
});
