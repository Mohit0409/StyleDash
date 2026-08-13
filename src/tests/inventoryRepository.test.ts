import { afterEach, describe, expect, it, vi } from 'vitest';
import { productRepository } from '../repositories/productRepository';
import { canAddVariantToCart, canIncreaseCartQuantity, inventoryRepository } from '../repositories/inventoryRepository';

const response = (availability: unknown, status = 200) => new Response(JSON.stringify({ success: true, availability }), {
  status,
  headers: { 'Content-Type': 'application/json' },
});

afterEach(() => vi.unstubAllGlobals());

describe('authoritative inventory repository', () => {
  it('uses the constrained availability endpoint without requesting stock quantities', async () => {
    const fetcher = vi.fn<typeof fetch>(async () => response([]));
    await expect(inventoryRepository.getAvailability('sd-prod-001-var-2', fetcher)).resolves.toEqual({
      success: true,
      availability: [],
    });
    expect(fetcher).toHaveBeenCalledWith('/api/inventory/availability?variantId=sd-prod-001-var-2', expect.any(Object));
  });

  it('refreshes displayed availability when server stock changes', async () => {
    const fetcher = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(response([{ productId: 'sd-prod-001', variantId: 'sd-prod-001-var-2', available: true }]))
      .mockResolvedValueOnce(response([{ productId: 'sd-prod-001', variantId: 'sd-prod-001-var-2', available: false }]));
    vi.stubGlobal('fetch', fetcher);

    const first = await productRepository.getProductBySlug('sd-prod-001');
    const second = await productRepository.getProductBySlug('sd-prod-001');
    expect(first?.variants.find(variant => variant.id === 'sd-prod-001-var-2')?.available).toBe(true);
    expect(second?.variants.find(variant => variant.id === 'sd-prod-001-var-2')?.available).toBe(false);
  });

  it('fails closed when the availability server cannot be reached', async () => {
    vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockRejectedValue(new TypeError('offline')));
    const product = await productRepository.getProductBySlug('sd-prod-001');
    expect(product?.variants.every(variant => variant.available === false)).toBe(true);
  });

  it('prevents new cart lines for unavailable variants or an unavailable server', async () => {
    const unavailable = vi.fn<typeof fetch>(async () => response([
      { productId: 'sd-prod-001', variantId: 'sd-prod-001-var-2', available: false },
    ]));
    const offline = vi.fn<typeof fetch>().mockRejectedValue(new TypeError('offline'));

    await expect(canAddVariantToCart('sd-prod-001-var-2', unavailable)).resolves.toBe(false);
    await expect(canAddVariantToCart('sd-prod-001-var-2', offline)).resolves.toBe(false);
  });

  it('prevents cart quantity increases for unavailable variants or an unavailable server', async () => {
    const unavailable = vi.fn<typeof fetch>(async () => response([
      { productId: 'sd-prod-001', variantId: 'sd-prod-001-var-2', available: false },
    ]));
    const offline = vi.fn<typeof fetch>().mockRejectedValue(new TypeError('offline'));

    await expect(canIncreaseCartQuantity('sd-prod-001-var-2', unavailable)).resolves.toBe(false);
    await expect(canIncreaseCartQuantity('sd-prod-001-var-2', offline)).resolves.toBe(false);
  });
});
