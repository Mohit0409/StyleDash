import { afterEach, describe, expect, it, vi } from 'vitest';
import { productRepository } from '../repositories/productRepository';
import { canAddVariantToCart, canIncreaseCartQuantity, inventoryRepository } from '../repositories/inventoryRepository';

const response = (availability: unknown, status = 200) => new Response(JSON.stringify({ success: true, availability }), {
  status,
  headers: { 'Content-Type': 'application/json' },
});

const productsResponse = (products: unknown[] = []) => new Response(JSON.stringify({ success: true, products }), {
  status: 200,
  headers: { 'Content-Type': 'application/json' },
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('authoritative inventory repository', () => {
  it('uses the constrained availability endpoint without requesting stock quantities', async () => {
    const fetcher = vi.fn<typeof fetch>(async () => response([]));
    await expect(inventoryRepository.getAvailability('sd-prod-001-var-2', fetcher)).resolves.toEqual({
      success: true,
      availability: [],
    });
    expect(fetcher).toHaveBeenCalledWith('/api/inventory/availability?variantId=sd-prod-001-var-2', expect.any(Object));
  });

  it('batches homepage availability by product id without requesting the full inventory payload', async () => {
    vi.spyOn(Date, 'now').mockReturnValue(0);
    const fetcher = vi.fn<typeof fetch>(async input => String(input) === '/api/shop-products/published'
      ? productsResponse()
      : response([]));
    vi.stubGlobal('fetch', fetcher);

    const products = await productRepository.getHomepageProducts();
    const inventoryCall = fetcher.mock.calls.find(([input]) => String(input).startsWith('/api/inventory/availability?productId='));
    expect(inventoryCall).toBeDefined();
    const requestUrl = new URL(String(inventoryCall?.[0]), 'https://styledash.test');
    const requestedProductIds = requestUrl.searchParams.getAll('productId');
    expect(requestedProductIds.length).toBe(products.length);
    expect(new Set(requestedProductIds).size).toBe(requestedProductIds.length);
    expect(requestedProductIds.length).toBeLessThanOrEqual(32);
    expect(fetcher.mock.calls.some(([input]) => String(input) === '/api/inventory/availability')).toBe(false);
  });

  it('deduplicates concurrent public catalogue and availability requests', async () => {
    const fetcher = vi.fn<typeof fetch>(async input => String(input) === '/api/shop-products/published'
      ? productsResponse()
      : response([]));
    vi.stubGlobal('fetch', fetcher);

    await Promise.all([productRepository.getAllProducts(), productRepository.getAllProducts()]);

    expect(fetcher.mock.calls.filter(([input]) => String(input) === '/api/shop-products/published')).toHaveLength(1);
    expect(fetcher.mock.calls.filter(([input]) => String(input) === '/api/inventory/availability')).toHaveLength(1);
  });

  it('refreshes displayed availability when server stock changes', async () => {
    let availabilityRequest = 0;
    const fetcher = vi.fn<typeof fetch>(async input => {
      if (String(input) === '/api/shop-products/published') return productsResponse();
      availabilityRequest += 1;
      return response([{ productId: 'sd-prod-001', variantId: 'sd-prod-001-var-2', available: availabilityRequest === 1 }]);
    });
    vi.stubGlobal('fetch', fetcher);

    const first = await productRepository.getProductBySlug('sd-prod-001');
    const second = await productRepository.getProductBySlug('sd-prod-001');
    expect(first?.variants.find(variant => variant.id === 'sd-prod-001-var-2')?.available).toBe(true);
    expect(second?.variants.find(variant => variant.id === 'sd-prod-001-var-2')?.available).toBe(false);
  });

  it('merges public shop products and applies authoritative variant availability', async () => {
    const now = Date.now();
    vi.spyOn(Date, 'now').mockReturnValue(now + 20_000);
    const publishedProduct = {
      id: 'shopprod_1', slug: 'active-local-shop-product', name: 'Local Shop Product', brand: 'Test Shop',
      department: 'women', category: 'Fashion', shortDescription: 'Local product', description: 'Local product',
      material: 'Cotton', careInstructions: [], price: 500, originalPrice: 500, discount: 0,
      images: ['https://example.test/product.jpg'], thumbnail: 'https://example.test/product.jpg', rating: 0, reviewCount: 0,
      variants: [{ id: 'shopprod_1-var-1', sku: 'SHOP-1', size: 'M', colourName: 'Black', stock: 1, available: false }],
      tags: ['local-shop'], badge: 'Local Shop', active: true, returnWindowDays: 0, exchangeAvailable: false,
      vendorId: 'shop-1', storeName: 'Test Shop', storeSlug: 'test-shop',
    };
    const fetcher = vi.fn<typeof fetch>(async input => String(input) === '/api/shop-products/published'
      ? productsResponse([publishedProduct])
      : response([{ productId: 'shopprod_1', variantId: 'shopprod_1-var-1', available: true }]));
    vi.stubGlobal('fetch', fetcher);

    const product = await productRepository.getProductBySlug('active-local-shop-product');

    expect(product?.id).toBe('shopprod_1');
    expect(product?.variants[0].available).toBe(true);
    expect(fetcher).toHaveBeenCalledWith('/api/shop-products/published', expect.objectContaining({ credentials: 'include' }));
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
