import { afterEach, describe, expect, it, vi } from 'vitest';
import { productRepository } from '../repositories/productRepository';
import { canAddVariantsToCart, canAddVariantToCart, canIncreaseCartQuantity, inventoryRepository } from '../repositories/inventoryRepository';

const response = (availability: unknown, status = 200) => new Response(JSON.stringify({ success: true, availability }), {
  status,
  headers: { 'Content-Type': 'application/json' },
});

const productsResponse = (products: unknown[] = []) => new Response(JSON.stringify({ success: true, products }), {
  status: 200,
  headers: { 'Content-Type': 'application/json' },
});

const reviewResponse = (summaries: Record<string, unknown> = {}) => new Response(JSON.stringify({ success: true, summaries }), {
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
    vi.stubGlobal('window', { location: { hostname: 'vibe4you.in' } });
    const publishedProduct = {
      id: 'shopprod_home', slug: 'homepage-local-product', name: 'Homepage Local Product', brand: 'Test Shop',
      department: 'women', category: 'Fashion', shortDescription: 'Local product', description: 'Local product',
      material: 'Cotton', careInstructions: [], price: 450, originalPrice: 500, discount: 10,
      images: ['/media/product-images/home.jpg'], thumbnail: '/media/product-images/home.jpg', rating: 0, reviewCount: 0,
      variants: [{ id: 'shopprod_home-var-1', sku: 'SHOP-HOME', size: 'M', colourName: 'Black', stock: 1, available: false }],
      tags: ['local-shop'], badge: 'Local Shop', active: true, newArrival: true, returnWindowDays: 0, exchangeAvailable: false,
      vendorId: 'shop-home', storeName: 'Test Shop', storeSlug: 'test-shop',
    };
    const fetcher = vi.fn<typeof fetch>(async input => {
      const url = String(input);
      if (url === '/api/shop-products/homepage') return productsResponse([publishedProduct]);
      if (url === '/api/shop-products/published') return productsResponse([publishedProduct]);
      if (url.startsWith('/api/reviews/summaries?')) return reviewResponse();
      return response([{ productId: 'shopprod_home', variantId: 'shopprod_home-var-1', available: true }]);
    });
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
  }, 10_000);

  it('deduplicates concurrent public catalogue and availability requests', async () => {
    const fetcher = vi.fn<typeof fetch>(async input => String(input) === '/api/shop-products/published'
      ? productsResponse()
      : response([]));
    vi.stubGlobal('fetch', fetcher);

    await Promise.all([productRepository.getAllProducts(), productRepository.getAllProducts()]);

    expect(fetcher.mock.calls.filter(([input]) => String(input) === '/api/shop-products/published')).toHaveLength(1);
    expect(fetcher.mock.calls.filter(([input]) => String(input) === '/api/inventory/availability')).toHaveLength(1);
  });

  it('batches review summaries so every catalogue product is covered without exceeding 64 ids', async () => {
    const fetcher = vi.fn<typeof fetch>(async input => {
      const url = String(input);
      if (url === '/api/shop-products/published') return productsResponse();
      if (url.startsWith('/api/reviews/summaries?')) return reviewResponse();
      return response([]);
    });
    vi.stubGlobal('fetch', fetcher);

    const products = await productRepository.getAllProducts();
    const reviewCalls = fetcher.mock.calls.filter(([input]) => String(input).startsWith('/api/reviews/summaries?'));
    expect(products.length).toBeGreaterThan(64);
    expect(reviewCalls.length).toBeGreaterThan(1);
    const requestedIds = reviewCalls.flatMap(([input]) =>
      new URL(String(input), 'https://styledash.test').searchParams.getAll('productId'));
    for (const [input] of reviewCalls) {
      const ids = new URL(String(input), 'https://styledash.test').searchParams.getAll('productId');
      expect(ids.length).toBeLessThanOrEqual(64);
    }
    expect(new Set(requestedIds)).toEqual(new Set(products.map(product => product.id)));
  });

  it('refreshes displayed availability when server stock changes', async () => {
    let availabilityRequest = 0;
    const fetcher = vi.fn<typeof fetch>(async input => {
      const url = String(input);
      if (url === '/api/shop-products/published') return productsResponse();
      if (url.startsWith('/api/shop-products/')) {
        return new Response(JSON.stringify({ success: false, error: 'Not found.', code: 'product_not_found' }), {
          status: 404, headers: { 'Content-Type': 'application/json' },
        });
      }
      availabilityRequest += 1;
      return response([{ productId: 'sd-prod-001', variantId: 'sd-prod-001-var-2', available: availabilityRequest === 1 }]);
    });
    vi.stubGlobal('fetch', fetcher);

    const first = await productRepository.getProductBySlug('sd-prod-001');
    const second = await productRepository.getProductBySlug('sd-prod-001');
    expect(first?.variants.find(variant => variant.id === 'sd-prod-001-var-2')?.available).toBe(true);
    expect(second?.variants.find(variant => variant.id === 'sd-prod-001-var-2')?.available).toBe(false);
  });

  it('merges public shop products and retries a transient authoritative availability failure', async () => {
    const now = Date.now();
    vi.spyOn(Date, 'now').mockReturnValue(now + 20_000);
    const publishedProduct = {
      id: 'shopprod_1', slug: 'active-local-shop-product', name: 'Local Shop Product', brand: 'Test Shop',
      department: 'women', category: 'Fashion', shortDescription: 'Local product', description: 'Local product',
      material: 'Cotton', careInstructions: [], price: 500, originalPrice: 500, discount: 0,
      images: ['https://example.test/product.html'], thumbnail: 'https://example.test/product.html', rating: 0, reviewCount: 0,
      variants: [{ id: 'shopprod_1-var-1', sku: 'SHOP-1', size: 'M', colourName: 'Black', stock: 1, available: false, images: ['https://example.test/product.html'] }],
      tags: ['local-shop'], badge: 'Local Shop', active: true, returnWindowDays: 0, exchangeAvailable: false,
      vendorId: 'shop-1', storeName: 'Test Shop', storeSlug: 'test-shop',
    };
    let inventoryCalls = 0;
    const fetcher = vi.fn<typeof fetch>(async input => {
      const url = String(input);
      if (url === '/api/shop-products/published') return productsResponse([publishedProduct]);
      if (url.startsWith('/api/reviews/summaries?')) return reviewResponse();
      inventoryCalls += 1;
      if (inventoryCalls === 1) throw new TypeError('temporary inventory outage');
      return response([{ productId: 'shopprod_1', variantId: 'shopprod_1-var-1', available: true }]);
    });
    vi.stubGlobal('fetch', fetcher);

    const product = await productRepository.getProductBySlug('active-local-shop-product');

    expect(product?.id).toBe('shopprod_1');
    expect(product?.images).toEqual(['/product-placeholder.svg']);
    expect(product?.thumbnail).toBe('/product-placeholder.svg');
    expect(product?.variants[0].images).toBeUndefined();
    expect(product?.variants[0].available).toBe(true);
    expect(inventoryCalls).toBe(2);
    expect(fetcher).toHaveBeenCalledWith('/api/shop-products/published', expect.objectContaining({ credentials: 'include' }));
  });

  it('excludes the demo catalogue on the real Vibe4You hostname', async () => {
    const now = Date.now();
    vi.spyOn(Date, 'now').mockReturnValue(now + 40_000);
    vi.stubGlobal('window', { location: { hostname: 'vibe4you.in' } });
    const publishedProduct = {
      id: 'shopprod_live', slug: 'goutam-live-shoe', name: 'Goutam Live Shoe', brand: 'Goutam Shoes',
      department: 'footwear', category: 'Sneakers', shortDescription: 'Live seller product', description: 'Live seller product',
      material: 'Not specified', careInstructions: [], price: 999, originalPrice: 999, discount: 0,
      images: ['/media/product-images/0123456789abcdef0123456789abcdef.jpg'], thumbnail: '/media/product-images/0123456789abcdef0123456789abcdef.jpg', rating: 0, reviewCount: 0,
      variants: [{ id: 'shopprod_live-var-1', sku: 'SHOP-LIVE', size: '6', colourName: 'As shown', stock: 0, available: false }],
      tags: ['local-shop'], badge: 'Local Shop', active: true, returnWindowDays: 0, exchangeAvailable: false,
      vendorId: 'vendor_goutam', storeName: 'Goutam Shoes', storeSlug: 'goutam-shoes',
    };
    const fetcher = vi.fn<typeof fetch>(async input => {
      const url = String(input);
      if (url === '/api/shop-products/published') return productsResponse([publishedProduct]);
      if (url.startsWith('/api/reviews/summaries?')) return reviewResponse();
      return response([]);
    });
    vi.stubGlobal('fetch', fetcher);

    const products = await productRepository.getAllProducts();

    expect(products.map(product => product.id)).toEqual(['shopprod_live']);
    expect(products.some(product => product.id.startsWith('sd-prod-'))).toBe(false);
    expect(products[0].variants[0].available).toBeUndefined();
  });

  it('hydrates cart metadata without waiting for inventory or review requests', async () => {
    vi.spyOn(Date, 'now').mockReturnValue(Date.now() + 60_000);
    vi.stubGlobal('window', { location: { hostname: 'vibe4you.in' } });
    const publishedProduct = {
      id: 'shopprod_cart', slug: 'cart-local-product', name: 'Cart Local Product', brand: 'Test Shop',
      department: 'women', category: 'Fashion', shortDescription: 'Local product', description: 'Local product',
      material: 'Cotton', careInstructions: [], price: 450, originalPrice: 500, discount: 10,
      images: ['/media/product-images/cart.jpg'], thumbnail: '/media/product-images/cart.jpg', rating: 0, reviewCount: 0,
      variants: [{ id: 'shopprod_cart-var-1', sku: 'SHOP-CART', size: 'M', colourName: 'Black', stock: 1, available: false }],
      tags: ['local-shop'], badge: 'Local Shop', active: true, newArrival: true, returnWindowDays: 0, exchangeAvailable: false,
      vendorId: 'shop-cart', storeName: 'Test Shop', storeSlug: 'test-shop',
    };
    const fetcher = vi.fn<typeof fetch>(async input => {
      const url = String(input);
      if (url === '/api/shop-products/published') return productsResponse([publishedProduct]);
      throw new Error(`cart hydration requested unrelated endpoint: ${url}`);
    });
    vi.stubGlobal('fetch', fetcher);

    const products = await productRepository.getCartProducts();

    expect(products.map(product => product.id)).toEqual(['shopprod_cart']);
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(fetcher).toHaveBeenCalledWith(
      '/api/shop-products/published',
      expect.objectContaining({ credentials: 'include' }),
    );
  });

  it('keeps display availability unresolved when the availability server cannot be reached', async () => {
    vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockRejectedValue(new TypeError('offline')));
    const product = await productRepository.getProductBySlug('sd-prod-001');
    expect(product?.variants.every(variant => variant.available === undefined)).toBe(true);
  });

  it('prevents new cart lines for unavailable variants or an unavailable server', async () => {
    const unavailable = vi.fn<typeof fetch>(async () => response([
      { productId: 'sd-prod-001', variantId: 'sd-prod-001-var-2', available: false },
    ]));
    const offline = vi.fn<typeof fetch>().mockRejectedValue(new TypeError('offline'));

    await expect(canAddVariantToCart('sd-prod-001-var-2', unavailable)).resolves.toBe(false);
    await expect(canAddVariantToCart('sd-prod-001-var-2', offline)).resolves.toBe(false);
  });

  it('checks multiple try-at-home variants in one batched request', async () => {
    const fetcher = vi.fn<typeof fetch>(async () => response([
      { productId: 'sd-prod-001', variantId: 'sd-prod-001-var-1', available: true },
      { productId: 'sd-prod-001', variantId: 'sd-prod-001-var-2', available: false },
    ]));
    await expect(canAddVariantsToCart('sd-prod-001', ['sd-prod-001-var-1', 'sd-prod-001-var-2'], fetcher)).resolves.toBe(false);
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(String(fetcher.mock.calls[0][0])).toBe('/api/inventory/availability?productId=sd-prod-001');
    const allAvailable = vi.fn<typeof fetch>(async () => response([
      { productId: 'sd-prod-001', variantId: 'sd-prod-001-var-1', available: true },
      { productId: 'sd-prod-001', variantId: 'sd-prod-001-var-2', available: true },
    ]));
    await expect(canAddVariantsToCart('sd-prod-001', ['sd-prod-001-var-1', 'sd-prod-001-var-2'], allAvailable)).resolves.toBe(true);
    const offline = vi.fn<typeof fetch>().mockRejectedValue(new TypeError('offline'));
    await expect(canAddVariantsToCart('sd-prod-001', ['sd-prod-001-var-1'], offline)).resolves.toBe(false);
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
