import { afterEach, describe, expect, it, vi } from 'vitest';
import { clearCsrfToken, setCsrfToken } from '../services/apiClient';
import { publicStoreApi, returnApi, sellerOrderApi, sellerReturnApi, sellerSettlementApi, shopProductApi, vendorApplicationApi } from '../services/businessApi';

const application = {
  id: 'shop-1',
  status: 'DRAFT',
  shopName: 'Test Shop',
  ownerName: 'Test Owner',
  category: 'Clothing & Fashion',
  description: '',
  address: '',
  city: 'Neemuch',
  state: 'Madhya Pradesh',
  pincode: '458441',
  createdAt: '2026-08-20T00:00:00Z',
  updatedAt: '2026-08-20T00:00:00Z',
} as const;

const jsonResponse = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
  status,
  headers: { 'Content-Type': 'application/json' },
});

describe('public store API', () => {
  afterEach(() => { vi.restoreAllMocks(); });

  it('loads active public stores from the server feed', async () => {
    const store = { id: 'shop-live-1', slug: 'local-shop-shop-live-1', storeName: 'Live Shop', category: 'Clothing & Fashion', description: 'Live local shop', address: 'Main market', city: 'Neemuch', pincode: '458441', deliveryMinutes: 60, active: true, approved: true, createdAt: '2026-08-22T00:00:00Z' };
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(jsonResponse({ success: true, stores: [store] }));
    await expect(publicStoreApi.active()).resolves.toEqual([store]);
    expect(fetchSpy).toHaveBeenCalledWith('/api/stores/active', expect.objectContaining({ credentials: 'include' }));
  });
});

describe('seller order API', () => {
  afterEach(() => { clearCsrfToken(); vi.restoreAllMocks(); });

  it('loads the authenticated seller order projection', async () => {
    const order = { id: 'SD-SELLER-1', sellerSubtotal: 800, items: [], address: {} };
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(jsonResponse({ success: true, orders: [order] }));
    await expect(sellerOrderApi.mine()).resolves.toEqual([order]);
    expect(fetchSpy).toHaveBeenCalledWith('/api/seller-orders', expect.objectContaining({ credentials: 'include' }));
  });

  it('updates only the seller fulfillment segment with CSRF protection', async () => {
    setCsrfToken('csrf-fulfillment-test');
    const fulfillment = { status: 'PROCESSING', updatedAt: '2026-08-26T00:00:00Z', allowedNextStatuses: ['READY'] };
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(jsonResponse({ success: true, fulfillment }));
    await expect(sellerOrderApi.updateFulfillment('SD-SELLER-1', 'PROCESSING')).resolves.toEqual(fulfillment);
    const [endpoint, init] = fetchSpy.mock.calls[0] as [RequestInfo | URL, RequestInit];
    expect(endpoint).toBe('/api/seller-orders/SD-SELLER-1/fulfillment');
    expect(init.method).toBe('PATCH');
    expect(new Headers(init.headers).get('X-CSRF-Token')).toBe('csrf-fulfillment-test');
    expect(JSON.parse(String(init.body))).toEqual({ status: 'PROCESSING' });
  });

  it('sends optional shipping details for a shipped seller segment', async () => {
    setCsrfToken('csrf-shipping-test');
    const fulfillment = {
      status: 'SHIPPED', updatedAt: '2026-08-27T08:00:00Z', allowedNextStatuses: ['DELIVERED'],
      shipping: { carrier: 'Delhivery', trackingNumber: 'DLV-123456' },
    };
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(jsonResponse({ success: true, fulfillment }));
    await expect(sellerOrderApi.updateFulfillment(
      'SD-SELLER-1', 'SHIPPED', { carrier: 'Delhivery', trackingNumber: 'DLV-123456' },
    )).resolves.toEqual(fulfillment);
    const [, init] = fetchSpy.mock.calls[0] as [RequestInfo | URL, RequestInit];
    expect(new Headers(init.headers).get('X-CSRF-Token')).toBe('csrf-shipping-test');
    expect(JSON.parse(String(init.body))).toEqual({
      status: 'SHIPPED', carrier: 'Delhivery', trackingNumber: 'DLV-123456',
    });
  });
});
describe('seller product submission API', () => {
  afterEach(() => {
    clearCsrfToken();
    vi.restoreAllMocks();
  });

  it('keeps seller submission transitions separate from the public published feed', async () => {
    setCsrfToken('csrf-product-test');
    const product = { id: 'shopprod_1', status: 'DRAFT' };
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation(async () => jsonResponse({ success: true, product, products: [] }));
    const draft = {
      name: 'Local Product', description: 'Local product description', department: 'women' as const,
      category: 'Clothing & Fashion', pricePaise: 50000, originalPricePaise: 60000,
      inventory: 2, size: 'M', colourName: 'Black', imageUrls: ['https://example.test/product.jpg'], attributes: {},
    };

    await shopProductApi.mine();
    await shopProductApi.createDraft(draft);
    await shopProductApi.updateDraft('shopprod_1', draft);
    await shopProductApi.submit('shopprod_1');
    await shopProductApi.published();

    expect(fetchSpy.mock.calls.map(([endpoint]) => endpoint)).toEqual([
      '/api/shop-products',
      '/api/shop-products',
      '/api/shop-products/shopprod_1',
      '/api/shop-products/shopprod_1/submit',
      '/api/shop-products/published',
    ]);
    for (const [endpoint, init] of fetchSpy.mock.calls as Array<[RequestInfo | URL, RequestInit]>) {
      if (['POST', 'PATCH'].includes(init.method || '')) {
        expect(new Headers(init.headers).get('X-CSRF-Token')).toBe('csrf-product-test');
      }
      if (String(endpoint) !== '/api/shop-products/published') expect(init.credentials).toBe('include');
    }
    expect(String((fetchSpy.mock.calls[1][1] as RequestInit).body)).not.toContain('status');
  });
});

describe('shop application API', () => {
  afterEach(() => {
    clearCsrfToken();
    vi.restoreAllMocks();
  });

  it('loads only the current authenticated customer application', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation(async () => jsonResponse({ success: true, application }));

    await expect(vendorApplicationApi.mine()).resolves.toEqual(application);
    expect(fetchSpy).toHaveBeenCalledWith('/api/vendor-applications/me', expect.objectContaining({
      credentials: 'include',
    }));
  });

  it('creates a draft without sending identity or status fields', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(jsonResponse({ success: true, application }, 201));
    const draft = {
      shopName: '', ownerName: '', category: 'Clothing & Fashion', description: '', address: '',
      city: 'Neemuch', state: 'Madhya Pradesh', pincode: '', businessInformation: '',
    };

    await vendorApplicationApi.createDraft(draft);

    const [endpoint, init] = fetchSpy.mock.calls[0] as [RequestInfo | URL, RequestInit];
    expect(endpoint).toBe('/api/vendor-applications');
    expect(init.method).toBe('POST');
    expect(JSON.parse(String(init.body))).toEqual(draft);
    expect(String(init.body)).not.toContain('status');
    expect(String(init.body)).not.toContain('registeredEmail');
    expect(String(init.body)).not.toContain('registeredMobile');
  });

  it('uses authenticated CSRF-protected transition endpoints for update and submit', async () => {
    setCsrfToken('csrf-shop-test');
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation(async () => jsonResponse({ success: true, application }));
    const draft = {
      shopName: 'Test Shop', ownerName: 'Test Owner', category: 'Clothing & Fashion', description: 'Description',
      address: 'Main market', city: 'Neemuch', state: 'Madhya Pradesh', pincode: '458441',
    };

    await vendorApplicationApi.updateDraft(draft);
    await vendorApplicationApi.submit();

    expect(fetchSpy.mock.calls.map(([endpoint]) => endpoint)).toEqual([
      '/api/vendor-applications/me',
      '/api/vendor-applications/me/submit',
    ]);
    for (const [, init] of fetchSpy.mock.calls as Array<[RequestInfo | URL, RequestInit]>) {
      expect(new Headers(init.headers).get('X-CSRF-Token')).toBe('csrf-shop-test');
      expect(init.credentials).toBe('include');
    }
  });
});


describe('returns API', () => {
  afterEach(() => { clearCsrfToken(); vi.restoreAllMocks(); });

  it('loads customer and seller return projections', async () => {
    const request = { id: 'ret-1', orderId: 'SD-1', requestType: 'ISSUE_RETURN', status: 'REQUESTED' };
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation(async () => jsonResponse({ success: true, requests: [request] }));
    await expect(returnApi.mine()).resolves.toEqual([request]);
    await expect(sellerReturnApi.mine()).resolves.toEqual([request]);
    expect(fetchSpy.mock.calls.map(([endpoint]) => endpoint)).toEqual(['/api/return-requests', '/api/seller-return-requests']);
  });

  it('creates an item request with CSRF and trusted identifiers only', async () => {
    setCsrfToken('csrf-return-test');
    const request = { id: 'ret-1', orderId: 'SD-1', requestType: 'ISSUE_RETURN', status: 'REQUESTED' };
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(jsonResponse({ success: true, request }, 201));
    await returnApi.create('SD-1', { productId: 'prod-1', variantId: 'var-1', requestType: 'ISSUE_RETURN', reason: 'DAMAGED', quantity: 1, details: 'Package was damaged' });
    const [endpoint, init] = fetchSpy.mock.calls[0] as [RequestInfo | URL, RequestInit];
    expect(endpoint).toBe('/api/orders/SD-1/return-requests');
    expect(init.method).toBe('POST');
    expect(new Headers(init.headers).get('X-CSRF-Token')).toBe('csrf-return-test');
    expect(JSON.parse(String(init.body))).toEqual({ productId: 'prod-1', variantId: 'var-1', requestType: 'ISSUE_RETURN', reason: 'DAMAGED', quantity: 1, details: 'Package was damaged' });
  });

  it('submits cancellation and seller notes through CSRF-protected endpoints', async () => {
    setCsrfToken('csrf-return-mutations');
    const cancellationRequest = { status: 'REQUESTED', reason: 'ORDERED_BY_MISTAKE', createdAt: '2026-08-27T00:00:00Z', updatedAt: '2026-08-27T00:00:00Z' };
    const sellerRequest = { id: 'ret-2', orderId: 'SD-2', requestType: 'SIZE_EXCHANGE', status: 'REQUESTED' };
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation(async endpoint => {
      if (String(endpoint).includes('cancellation-request')) return jsonResponse({ success: true, cancellationRequest }, 201);
      return jsonResponse({ success: true, request: sellerRequest });
    });
    await returnApi.requestCancellation('SD-2', { reason: 'ORDERED_BY_MISTAKE', details: 'Selected the wrong item' });
    await sellerReturnApi.addNote('ret-2', 'Replacement size available');
    const [cancelEndpoint, cancelInit] = fetchSpy.mock.calls[0] as [RequestInfo | URL, RequestInit];
    expect(cancelEndpoint).toBe('/api/orders/SD-2/cancellation-request');
    expect(new Headers(cancelInit.headers).get('X-CSRF-Token')).toBe('csrf-return-mutations');
    expect(JSON.parse(String(cancelInit.body))).toEqual({ reason: 'ORDERED_BY_MISTAKE', details: 'Selected the wrong item' });
    const [noteEndpoint, noteInit] = fetchSpy.mock.calls[1] as [RequestInfo | URL, RequestInit];
    expect(noteEndpoint).toBe('/api/seller-return-requests/ret-2');
    expect(noteInit.method).toBe('PATCH');
    expect(new Headers(noteInit.headers).get('X-CSRF-Token')).toBe('csrf-return-mutations');
    expect(JSON.parse(String(noteInit.body))).toEqual({ note: 'Replacement size available' });
  });
});


describe('seller settlements API', () => {
  afterEach(() => { clearCsrfToken(); vi.restoreAllMocks(); });

  it('loads the authenticated seller settlement projection read-only', async () => {
    const settlement = {
      id: 'set-1', orderId: 'SD-1', shopName: 'Seller Shop', grossAmountPaise: 159900,
      commissionPercent: 12, commissionAmountPaise: 19188, netAmountPaise: 140712,
      paymentMethod: 'cod', status: 'AWAITING_COLLECTION', deliveredAt: '2026-08-27T12:00:00Z',
      clearanceUntil: '2026-09-03T12:00:00Z', createdAt: '2026-08-27T12:00:00Z', updatedAt: '2026-08-27T12:00:00Z',
    };
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(jsonResponse({ success: true, settlements: [settlement] }));
    await expect(sellerSettlementApi.mine()).resolves.toEqual([settlement]);
    expect(fetchSpy).toHaveBeenCalledWith('/api/seller-settlements', expect.objectContaining({ credentials: 'include' }));
    const [, init] = fetchSpy.mock.calls[0] as [RequestInfo | URL, RequestInit];
    expect((init.method || 'GET').toUpperCase()).toBe('GET');
  });
});
