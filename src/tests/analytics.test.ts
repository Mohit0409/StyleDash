import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { ServerOrder } from '../services/paymentApi';

const analyticsMocks = vi.hoisted(() => ({
  analyticsClient: { name: 'analytics-client' },
  initializeAnalytics: vi.fn(),
  isSupported: vi.fn(),
  logEvent: vi.fn(),
}));

vi.mock('firebase/analytics', () => ({
  initializeAnalytics: analyticsMocks.initializeAnalytics,
  isSupported: analyticsMocks.isSupported,
  logEvent: analyticsMocks.logEvent,
}));

vi.mock('../services/firebaseClient', () => ({
  getFirebaseApp: vi.fn(() => ({ name: 'firebase-app' })),
}));

const makeOrder = (overrides: Partial<ServerOrder> = {}): ServerOrder => ({
  id: 'order-1', userId: 'user-1', items: [],
  address: { id: 'address-1', name: 'Customer', phone: '9999999999', street: 'Street', city: 'Neemuch', state: 'Madhya Pradesh', pincode: '458441' },
  paymentMethod: 'card', paymentStatus: 'paid', subtotal: 499, discount: 0, walletAmount: 0,
  deliveryFee: 0, taxes: 0, grandTotal: 499, deliveryMethod: 'standard', estimatedDelivery: 'Today',
  status: 'confirmed', statusHistory: [], createdAt: '2026-09-17T00:00:00Z', updatedAt: '2026-09-17T00:00:00Z',
  ...overrides,
});

const installBrowser = (hostname = 'vibe4you.in', pathname = '/') => {
  Object.defineProperty(globalThis, 'window', {
    value: {
      location: { hostname, origin: `https://${hostname}`, pathname },
      localStorage: { getItem: vi.fn(() => null), setItem: vi.fn() },
    },
    configurable: true,
  });
  Object.defineProperty(globalThis, 'document', {
    value: { title: 'Vibe4You Test Page' },
    configurable: true,
  });
};

describe('GA4 analytics integration', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
    analyticsMocks.isSupported.mockResolvedValue(true);
    analyticsMocks.initializeAnalytics.mockReturnValue(analyticsMocks.analyticsClient);
    installBrowser();
  });

  it('sends sanitized events without customer account fields', async () => {
    const { trackEvent } = await import('../services/analytics');

    await expect(trackEvent('test_event', {
      email: 'customer@example.com',
      phone: '9999999999',
      address: 'Private address',
      page_path: '/products',
      items: [{
        item_id: 'product-1',
        item_name: 'Test Product',
        email: 'seller@example.com',
        price: 499,
        quantity: 1,
      }],
    })).resolves.toBe(true);

    expect(analyticsMocks.logEvent).toHaveBeenCalledTimes(1);
    const params = analyticsMocks.logEvent.mock.calls[0][2] as Record<string, unknown>;
    expect(params).toMatchObject({ page_path: '/products' });    expect(params).not.toHaveProperty('email');
    expect(params).not.toHaveProperty('phone');
    expect(params).not.toHaveProperty('address');
    expect(params.items).toEqual([{
      item_id: 'product-1',
      item_name: 'Test Product',
      price: 499,
      quantity: 1,
    }]);
  });

  it('counts site searches without sending the customer-entered search text', async () => {
    const { trackEvent } = await import('../services/analytics');

    await expect(trackEvent('search', { search_term: 'customer@example.com 9999999999' })).resolves.toBe(true);

    const params = analyticsMocks.logEvent.mock.calls[0][2] as Record<string, unknown>;
    expect(params.search_term).toBe('site_search');
    expect(JSON.stringify(params)).not.toContain('customer@example.com');
    expect(JSON.stringify(params)).not.toContain('9999999999');
  });

  it('does not initialize analytics on password reset URLs that can contain secrets', async () => {
    installBrowser('vibe4you.in', '/reset-password');
    const { trackPageView } = await import('../services/analytics');

    await expect(trackPageView('/reset-password?token=secret&email=customer@example.com')).resolves.toBe(false);

    expect(analyticsMocks.initializeAnalytics).not.toHaveBeenCalled();
    expect(analyticsMocks.logEvent).not.toHaveBeenCalled();
  });

  it('does not count pending or failed online orders as purchases', async () => {
    const { trackPurchase } = await import('../services/analytics');

    await expect(trackPurchase(makeOrder({ paymentMethod: 'card', paymentStatus: 'pending' }))).resolves.toBe(false);
    await expect(trackPurchase(makeOrder({ paymentMethod: 'upi', paymentStatus: 'failed' }))).resolves.toBe(false);
    expect(analyticsMocks.logEvent).not.toHaveBeenCalled();
  });

  it('still counts a placed COD order but rejects cancelled orders', async () => {
    const { trackPurchase } = await import('../services/analytics');

    await expect(trackPurchase(makeOrder({ paymentMethod: 'cod', paymentStatus: 'pending', status: 'placed' }))).resolves.toBe(true);
    expect(analyticsMocks.logEvent).toHaveBeenCalledTimes(1);
    analyticsMocks.logEvent.mockClear();
    await expect(trackPurchase(makeOrder({ id: 'order-2', paymentMethod: 'cod', paymentStatus: 'pending', status: 'cancelled' }))).resolves.toBe(false);
    expect(analyticsMocks.logEvent).not.toHaveBeenCalled();
  });

  it('does not send GA4 traffic from localhost or staging hosts', async () => {
    installBrowser('localhost');
    const { trackEvent } = await import('../services/analytics');

    await expect(trackEvent('view_item', { item_id: 'product-1' })).resolves.toBe(false);
    expect(analyticsMocks.initializeAnalytics).not.toHaveBeenCalled();
    expect(analyticsMocks.logEvent).not.toHaveBeenCalled();
  });
});
