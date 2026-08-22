import { afterEach, describe, expect, it, vi } from 'vitest';
import { clearCsrfToken, setCsrfToken } from '../services/apiClient';
import { publicStoreApi, shopProductApi, vendorApplicationApi } from '../services/businessApi';

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
