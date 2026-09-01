import { afterEach, describe, expect, it, vi } from 'vitest';
import { clearCsrfToken, setCsrfToken } from '../services/apiClient';
import { reviewApi } from '../services/reviewApi';

const jsonResponse = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
  status,
  headers: { 'Content-Type': 'application/json' },
});

describe('verified customer review API', () => {
  afterEach(() => {
    clearCsrfToken();
    vi.restoreAllMocks();
  });

  it('loads public reviews and batched rating summaries', async () => {
    const review = {
      id: 'rev_1', userName: 'Customer R.', rating: 5, title: 'Great', comment: 'Great product',
      createdAt: '2026-09-01T00:00:00Z', verifiedPurchase: true,
    };
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation(async input => {
      const url = String(input);
      if (url.startsWith('/api/reviews/summaries')) {
        return jsonResponse({ success: true, summaries: { 'sd-prod-001': { rating: 5, reviewCount: 1 } } });
      }
      return jsonResponse({ success: true, productId: 'sd-prod-001', rating: 5, reviewCount: 1,
        distribution: { '5': 1 }, reviews: [review] });
    });

    await expect(reviewApi.list('sd-prod-001')).resolves.toMatchObject({ rating: 5, reviewCount: 1 });
    await expect(reviewApi.summaries(['sd-prod-001'])).resolves.toEqual({ 'sd-prod-001': { rating: 5, reviewCount: 1 } });
    expect(String(fetchSpy.mock.calls[1][0])).toContain('productId=sd-prod-001');
  });

  it('uses authenticated CSRF-protected create, edit, and delete actions', async () => {
    setCsrfToken('csrf-review-test');
    const review = {
      id: 'rev_1', userName: 'Customer R.', rating: 4, comment: 'Updated review',
      createdAt: '2026-09-01T00:00:00Z', verifiedPurchase: true,
    };
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation(async input => {
      if (String(input).includes('/eligibility')) {
        return jsonResponse({ success: true, eligible: true, orderId: 'order-1', existingReview: null, reason: null });
      }
      return jsonResponse({ success: true, review });
    });

    await expect(reviewApi.eligibility('sd-prod-001')).resolves.toMatchObject({ eligible: true });
    await reviewApi.create('sd-prod-001', { rating: 5, comment: 'Verified review' });
    await reviewApi.edit('rev_1', { rating: 4, comment: 'Updated review' });
    await reviewApi.delete('rev_1');

    const writes = fetchSpy.mock.calls.slice(1) as Array<[RequestInfo | URL, RequestInit]>;
    expect(writes.map(([endpoint]) => String(endpoint))).toEqual([
      '/api/reviews', '/api/reviews/rev_1/edit', '/api/reviews/rev_1/delete',
    ]);
    for (const [, init] of writes) {
      expect(init.method).toBe('POST');
      expect(new Headers(init.headers).get('X-CSRF-Token')).toBe('csrf-review-test');
      expect(init.credentials).toBe('include');
    }
  });
});
