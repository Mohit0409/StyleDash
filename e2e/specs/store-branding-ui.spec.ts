import { expect, test } from '@playwright/test';

const ONE_PIXEL_PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=',
  'base64',
);

const application = (status: string, overrides: Record<string, unknown> = {}) => ({
  id: 'shop-branding-1',
  status,
  shopName: 'E2E Branding Shop',
  ownerName: 'Seller E2E',
  registeredEmail: 'seller@example.test',
  category: 'Clothing & Fashion',
  description: 'An active local shop used for store branding coverage.',
  address: '12 Main Market Road',
  city: 'Neemuch',
  state: 'Madhya Pradesh',
  pincode: '458441',
  createdAt: '2026-08-20T00:00:00Z',
  updatedAt: '2026-08-20T00:00:00Z',
  bannerImage: null,
  logoImage: null,
  ...overrides,
});

const authResponse = {
  success: true,
  csrfToken: 'csrf-branding-e2e',
  user: { uid: 'seller-1', name: 'Seller E2E', email: 'seller@example.test', role: 'customer' },
};

test('active owner uploads, saves, reloads, and removes store branding', async ({ page }) => {
  let current = application('ACTIVE');
  const savedPayloads: Array<Record<string, unknown>> = [];
  const uploads: Array<Record<string, unknown>> = [];
  const media = new Map<string, Buffer>();

  await page.route('**/media/product-images/**', async route => {
    const path = new URL(route.request().url()).pathname;
    const body = media.get(path);
    if (!body) return void await route.fulfill({ status: 404, body: 'missing' });
    await route.fulfill({ status: 200, contentType: 'image/webp', body });
  });

  await page.route('**/api/**', async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const method = request.method();
    const json = (body: unknown, status = 200) => route.fulfill({
      status,
      contentType: 'application/json',
      body: JSON.stringify(body),
    });

    if (path === '/api/auth/me') return void await json(authResponse);
    if (path === '/api/vendor-applications/me' && method === 'GET') {
      return void await json({ success: true, application: current });
    }
    if (path === '/api/shop-products' && method === 'GET') {
      return void await json({ success: true, products: [] });
    }
    if (path === '/api/shop-product-requests' && method === 'GET') {
      return void await json({ success: true, requests: [] });
    }
    if (path === '/api/shop-branding-images' && method === 'POST') {
      expect(request.headers()['x-csrf-token']).toBe('csrf-branding-e2e');
      const upload = request.postDataJSON() as Record<string, unknown>;
      uploads.push(upload);
      const body = Buffer.from(String(upload.dataBase64), 'base64');
      const hash = uploads.length === 1 ? '1'.repeat(32) : '2'.repeat(32);
      const url = `/media/product-images/${hash}.webp`;
      media.set(url, body);
      return void await json({
        success: true,
        image: { url, bytes: body.length, contentType: 'image/webp' },
      }, 201);
    }
    if (path === '/api/vendor-applications/me/branding' && method === 'PATCH') {
      expect(request.headers()['x-csrf-token']).toBe('csrf-branding-e2e');
      const payload = request.postDataJSON() as Record<string, unknown>;
      savedPayloads.push(payload);
      current = application('ACTIVE', payload);
      return void await json({ success: true, application: current });
    }
    return void await json({ success: false, error: `Unexpected ${method} ${path}` }, 500);
  });

  await page.goto('/partner');
  const branding = page.getByRole('region', { name: 'Store branding' });
  await expect(branding).toBeVisible();
  await expect(branding.getByRole('heading', { name: 'Store Cover' })).toBeVisible();
  await expect(branding.getByText('ideally around 21:9')).toBeVisible();
  await expect(branding.getByRole('heading', { name: 'Store Logo' })).toBeVisible();
  await expect(branding.getByText('Choose a square image')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Product submissions' })).toBeVisible();

  await branding.getByLabel('Upload store cover image').setInputFiles({
    name: 'cover.png', mimeType: 'image/png', buffer: ONE_PIXEL_PNG,
  });
  await expect(branding.getByAltText('Store cover preview')).toBeVisible();
  await branding.getByLabel('Upload store logo image').setInputFiles({
    name: 'logo.png', mimeType: 'image/png', buffer: ONE_PIXEL_PNG,
  });
  await expect(branding.getByAltText('Store logo preview')).toBeVisible();

  expect(uploads).toHaveLength(2);
  for (const upload of uploads) {
    expect(upload.contentType).toBe('image/webp');
    expect(String(upload.fileName)).toMatch(/\.webp$/);
    const body = Buffer.from(String(upload.dataBase64), 'base64');
    expect(body.subarray(0, 4).toString('ascii')).toBe('RIFF');
    expect(body.subarray(8, 12).toString('ascii')).toBe('WEBP');
    expect(body.length).toBeLessThanOrEqual(500 * 1024);
  }

  await branding.getByRole('button', { name: 'Save Store Branding' }).click();
  await expect(branding.getByRole('status')).toContainText('Store branding saved');
  expect(savedPayloads[0]).toEqual({
    bannerImage: `/media/product-images/${'1'.repeat(32)}.webp`,
    logoImage: `/media/product-images/${'2'.repeat(32)}.webp`,
  });

  await page.reload();
  const reopened = page.getByRole('region', { name: 'Store branding' });
  await expect(reopened.getByAltText('Store cover preview')).toBeVisible();
  await expect(reopened.getByAltText('Store logo preview')).toBeVisible();
  await reopened.getByRole('button', { name: 'Remove store logo' }).click();
  await reopened.getByRole('button', { name: 'Save Store Branding' }).click();
  await expect(reopened.getByRole('status')).toContainText('Store branding saved');
  expect(savedPayloads[1]).toEqual({
    bannerImage: `/media/product-images/${'1'.repeat(32)}.webp`,
    logoImage: null,
  });
  await expect(reopened.getByAltText('Store cover preview')).toBeVisible();
  await expect(reopened.getByAltText('Store logo preview')).toHaveCount(0);
});

test('branding UI fails safely for unapproved owners and invalid or failed uploads', async ({ page, request }) => {
  const anonymous = await request.post('/api/shop-branding-images', {
    data: {
      fileName: 'anonymous.png',
      contentType: 'image/png',
      dataBase64: ONE_PIXEL_PNG.toString('base64'),
    },
  });
  expect(anonymous.status()).toBe(401);
  await expect(anonymous.json()).resolves.toMatchObject({ code: 'authentication_required' });

  let current = application('SUBMITTED');
  let uploadAttempts = 0;
  await page.route('**/api/**', async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const method = request.method();
    const json = (body: unknown, status = 200) => route.fulfill({
      status, contentType: 'application/json', body: JSON.stringify(body),
    });
    if (path === '/api/auth/me') return void await json(authResponse);
    if (path === '/api/vendor-applications/me' && method === 'GET') {
      return void await json({ success: true, application: current });
    }
    if (path === '/api/shop-products' || path === '/api/shop-product-requests') {
      return void await json({ success: true, products: [], requests: [] });
    }
    if (path === '/api/shop-branding-images' && method === 'POST') {
      uploadAttempts += 1;
      return void await json({
        success: false,
        error: 'Store image upload failed. Please try a smaller image.',
        code: 'product_image_too_large',
      }, 413);
    }
    if (path === '/api/vendor-applications/me/branding' && method === 'PATCH') {
      const payload = request.postDataJSON() as Record<string, unknown>;
      if (String(payload.bannerImage || '').startsWith('https://')) {
        return void await json({ success: false, error: 'Upload a valid store cover image.', code: 'invalid_store_branding' }, 400);
      }
      return void await json({ success: false, error: 'Store branding can be changed after shop approval.', code: 'approved_shop_required' }, 409);
    }
    return void await json({ success: false, error: `Unexpected ${method} ${path}` }, 500);
  });

  await page.goto('/partner');
  await expect(page.getByRole('region', { name: 'Store branding' })).toHaveCount(0);
  await expect(page.getByRole('heading', { name: 'Product submissions' })).toHaveCount(0);

  const bypass = await page.evaluate(async csrfToken => {
    const response = await fetch('/api/vendor-applications/me/branding', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken },
      body: JSON.stringify({ bannerImage: 'https://example.test/external.webp' }),
    });
    return { status: response.status, body: await response.json() };
  }, authResponse.csrfToken);
  expect(bypass).toMatchObject({ status: 400, body: { code: 'invalid_store_branding' } });

  current = application('ACTIVE');
  await page.reload();
  const branding = page.getByRole('region', { name: 'Store branding' });
  await branding.getByLabel('Upload store cover image').setInputFiles({
    name: 'notes.txt', mimeType: 'text/plain', buffer: Buffer.from('not an image'),
  });
  await expect(branding.getByRole('alert')).toContainText('Choose a JPEG, PNG or WebP image.');
  expect(uploadAttempts).toBe(0);

  await branding.getByLabel('Upload store cover image').setInputFiles({
    name: 'cover.png', mimeType: 'image/png', buffer: ONE_PIXEL_PNG,
  });
  await expect(branding.getByRole('alert')).toContainText('Store image upload failed. Please try a smaller image.');
  expect(uploadAttempts).toBe(1);
  await expect(page.getByRole('heading', { name: 'Product submissions' })).toBeVisible();
});

test('public stores, storefront, product search, and royals search use safe branding fallbacks', async ({ page }) => {
  const stores = [
    {
      id: 'store-royals', slug: 'royals', storeName: 'royals', category: 'Clothing & Fashion',
      address: 'Neemuch', pincode: '458441', city: 'Neemuch', deliveryMinutes: 60,
      description: 'Local fashion store', active: true, approved: true,
      bannerImage: '/media/product-images/custom-cover.webp',
      logoImage: '/media/product-images/custom-logo.webp',
      createdAt: '2026-01-01T00:00:00Z',
    },
    {
      id: 'store-legacy', slug: 'legacy-store', storeName: 'Legacy Store', category: 'Clothing & Fashion',
      address: 'Neemuch', pincode: '458441', city: 'Neemuch', deliveryMinutes: 60,
      description: 'Store using a historical product-image fallback', active: true, approved: true,
      bannerImage: '/media/product-images/missing-product-cover.webp',
      logoImage: '/media/product-images/missing-product-logo.webp',
      createdAt: '2026-01-01T00:00:00Z',
    },
  ];

  await page.route('**/api/stores/active', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ success: true, stores }),
  }));
  await page.route('**/media/product-images/custom-*.webp', route => route.fulfill({
    status: 200, contentType: 'image/png', body: ONE_PIXEL_PNG,
  }));
  await page.route('**/media/product-images/missing-product-*.webp', route => route.abort('failed'));

  await page.goto('/stores');
  await expect(page.getByAltText('royals', { exact: true })).toBeVisible();
  await expect(page.getByAltText('royals logo')).toBeVisible();
  await expect(page.getByLabel('Legacy Store cover placeholder')).toBeVisible();
  await expect(page.getByLabel('Legacy Store logo placeholder')).toBeVisible();
  await expect(page.locator('img[src*="missing-product-"]')).toHaveCount(0);

  await page.goto('/store/royals');
  await expect(page.getByAltText('royals', { exact: true })).toBeVisible();
  await expect(page.getByAltText('royals logo')).toBeVisible();
  await expect(page.locator('[data-store-image-fallback]')).toHaveCount(0);

  await page.goto('/store/legacy-store');
  await expect(page.getByLabel('Legacy Store cover placeholder')).toBeVisible();
  await expect(page.getByLabel('Legacy Store logo placeholder')).toBeVisible();
  await expect(page.locator('img[src*="missing-product-"]')).toHaveCount(0);

  await page.goto('/');
  const search = page.locator('header input[aria-label="Search products, brands, or local Neemuch stores"]:visible');
  await search.fill('royals');
  await search.press('Enter');
  await expect(page).toHaveURL(/products\?search=royals/);
  await expect(page.getByRole('heading', { name: 'Matching Local Stores' })).toBeVisible();
  const royalsResult = page.getByRole('link', { name: 'Visit royals storefront' });
  await expect(royalsResult).toBeVisible();
  await expect(royalsResult.locator('img')).toHaveAttribute('src', '/media/product-images/custom-logo.webp');

  await page.goto('/products?search=shirt');
  await expect(page.getByRole('heading', { name: /Search results for "shirt"/ })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Textured Linen Spread Collar Shirt' })).toBeVisible();
});


test('obvious product page URLs fall back before the browser requests them', async ({ page }) => {
  const badUrl = 'https://pngtree.com/freepng/stacked-jeans_3160982.html';
  const product = {
    id: 'shopprod-bad-page-url', slug: 'legacy-page-image-product', name: 'Legacy Page Image Product', brand: 'Royals',
    department: 'unisex', category: 'Clothing & Fashion', shortDescription: 'Legacy image data', description: 'Legacy image data',
    material: 'Cotton', careInstructions: [], price: 30, originalPrice: 50, discount: 40,
    images: [badUrl], thumbnail: badUrl, rating: 0, reviewCount: 0,
    variants: [{ id: 'shopprod-bad-page-url-var-1', sku: 'BAD-PAGE-1', size: 'M', colourName: 'Blue', stock: 20, available: true, images: [badUrl] }],
    tags: ['local-shop'], badge: 'Local Shop', active: true, returnWindowDays: 0, exchangeAvailable: false,
    vendorId: 'store-royals', storeName: 'royals', storeSlug: 'royals',
  };
  let badRequests = 0;
  page.on('request', request => { if (request.url() === badUrl) badRequests += 1; });
  await page.route('**/api/shop-products/published', route => route.fulfill({
    status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, products: [product] }),
  }));

  await page.goto('/products?search=Legacy%20Page%20Image%20Product');
  await expect(page.getByRole('heading', { name: 'Legacy Page Image Product', exact: true })).toBeVisible();
  const cardImage = page.getByAltText('Legacy Page Image Product', { exact: true });
  await expect(cardImage).toHaveAttribute('src', '/product-placeholder.svg');
  expect(badRequests).toBe(0);

  await page.goto('/product/legacy-page-image-product');
  await expect(page.getByRole('heading', { name: 'Legacy Page Image Product', exact: true })).toBeVisible();
  await expect(page.getByAltText('Legacy Page Image Product', { exact: true })).toHaveAttribute('src', '/product-placeholder.svg');
  await expect(page.getByRole('heading', { name: 'Customer Reviews' })).toBeVisible();
  expect(badRequests).toBe(0);
});
