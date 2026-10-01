import { expect, test } from '@playwright/test';

const authResponse = {
  success: true,
  csrfToken: 'csrf-all-india-e2e',
  user: {
    uid: 'all-india-e2e-user',
    name: 'All India E2E Customer',
    email: 'all-india-e2e@example.test',
    phone: '9876543210',
    role: 'customer',
    addresses: [{
      id: 'addr-aio-1',
      name: 'All India E2E Customer',
      phone: '9876543210',
      street: '12 Test Street',
      city: 'Jaipur',
      state: 'Rajasthan',
      pincode: '302001',
      isDefault: true,
    }],
  },
};

const activeApplication = (overrides: Record<string, unknown> = {}) => ({
  id: 'shop-aio-1',
  status: 'ACTIVE',
  shopName: 'All India Test Shop',
  ownerName: 'Seller E2E',
  registeredEmail: 'seller@example.test',
  registeredMobile: '9876500000',
  category: 'Clothing & Fashion',
  description: 'A test shop for All India mediator ordering.',
  address: '1 Market Road',
  city: 'Neemuch',
  state: 'Madhya Pradesh',
  pincode: '458441',
  businessInformation: '',
  bannerImage: null,
  logoImage: null,
  allIndiaDeliveryEnabled: false,
  allIndiaShippingPayer: 'customer',
  rejectionReason: null,
  createdAt: '2026-10-01T00:00:00Z',
  updatedAt: '2026-10-01T00:00:00Z',
  submittedAt: '2026-10-01T00:00:00Z',
  approvedAt: '2026-10-01T00:00:00Z',
  activatedAt: '2026-10-01T00:00:00Z',
  ...overrides,
});

const allIndiaProduct = {
  id: 'aio-product-1',
  slug: 'all-india-test-shirt',
  name: 'All India Test Shirt',
  brand: 'Vibe4You Test',
  department: 'men',
  category: 'Clothing & Fashion',
  subcategory: 'Shirts',
  deliveryType: 'normal',
  shortDescription: 'A browser-test product.',
  description: 'A browser-test product for the All India mediator flow.',
  material: 'Cotton',
  careInstructions: [],
  price: 599,
  originalPrice: 699,
  discount: 14,
  images: ['/product-placeholder.svg'],
  thumbnail: '/product-placeholder.svg',
  rating: 0,
  reviewCount: 0,
  variants: [{
    id: 'aio-variant-1',
    sku: 'AIO-E2E-1',
    size: 'M',
    colourName: 'Black',
    stock: 2,
    available: true,
    price: 599,
  }],
  tags: ['test'],
  returnWindowDays: 0,
  exchangeAvailable: false,
  vendorId: 'shop-aio-1',
  storeName: 'All India Test Shop',
  storeSlug: 'all-india-test-shop',
  active: true,
  allIndiaDeliveryAvailable: true,
  allIndiaShippingPayer: 'customer',
};

const mediatorOrder = {
  id: 'AIO-E2E-0001',
  shopId: 'shop-aio-1',
  shopName: 'All India Test Shop',
  items: [{
    productId: 'aio-product-1',
    productName: 'All India Test Shirt',
    productSlug: 'all-india-test-shirt',
    variantId: 'aio-variant-1',
    sku: 'AIO-E2E-1',
    size: 'M',
    colourName: 'Black',
    quantity: 1,
    unitPrice: 599,
    lineTotal: 599,
    storeId: 'shop-aio-1',
    storeName: 'All India Test Shop',
    storeSlug: 'all-india-test-shop',
  }],
  address: {
    name: 'All India E2E Customer',
    phone: '9876543210',
    street: '12 Test Street',
    city: 'Jaipur',
    state: 'Rajasthan',
    pincode: '302001',
  },
  merchandiseTotal: 599,
  shippingPayer: 'customer',
  status: 'NEW',
  createdAt: '2026-10-01T00:00:00Z',
  updatedAt: '2026-10-01T00:00:00Z',
};

test('seller opt-in keeps mediator inbox hidden until All India delivery is enabled', async ({ page }) => {
  let application = activeApplication();
  let settingsPayload: Record<string, unknown> | null = null;
  let mediatorListCalls = 0;

  await page.route('**/api/**', async route => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();
    const json = (body: unknown, status = 200) => route.fulfill({
      status,
      contentType: 'application/json',
      body: JSON.stringify(body),
    });

    if (path === '/api/auth/me') return void await json(authResponse);
    if (path === '/api/account-state') return void await json({ success: true, cart: [], wishlist: [] });
    if (path === '/api/vendor-applications/me' && method === 'GET') {
      return void await json({ success: true, application });
    }
    if (path === '/api/vendor-applications/me/delivery-settings' && method === 'PATCH') {
      settingsPayload = request.postDataJSON() as Record<string, unknown>;
      application = activeApplication({
        allIndiaDeliveryEnabled: settingsPayload.allIndiaDeliveryEnabled,
        allIndiaShippingPayer: settingsPayload.allIndiaShippingPayer,
      });
      return void await json({ success: true, application });
    }
    if (path === '/api/shop-products') return void await json({ success: true, products: [] });
    if (path === '/api/shop-product-requests') return void await json({ success: true, requests: [] });
    if (path === '/api/shop-mediator-orders') {
      mediatorListCalls += 1;
      return void await json({ success: true, orders: [] });
    }
    return void await json({ success: false, error: `Unexpected mocked API request: ${method} ${path}` }, 500);
  });

  await page.goto('/partner');

  await expect(page.getByRole('heading', { name: 'All India delivery' })).toBeVisible();
  await expect(page.getByLabel('Accept All India order requests')).not.toBeChecked();
  await expect(page.getByRole('heading', { name: 'All India order requests' })).toHaveCount(0);
  expect(mediatorListCalls).toBe(0);

  await page.getByLabel('Accept All India order requests').check();
  await page.getByRole('radio', { name: /Shop pays/ }).check();
  await page.getByRole('button', { name: 'Save delivery settings' }).click();

  await expect.poll(() => settingsPayload).toMatchObject({
    allIndiaDeliveryEnabled: true,
    allIndiaShippingPayer: 'shop',
  });
  await expect(page.getByRole('heading', { name: 'All India order requests' })).toBeVisible();
  await expect.poll(() => mediatorListCalls).toBe(1);
});

test('All India checkout posts only the mediator order and never calls local payment endpoints', async ({ page }) => {
  const calls: Array<{ method: string; path: string }> = [];
  let mediatorPayload: Record<string, unknown> | null = null;

  await page.route('**/api/**', async route => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();
    calls.push({ method, path });

    const json = (body: unknown, status = 200) => route.fulfill({
      status,
      contentType: 'application/json',
      body: JSON.stringify(body),
    });

    if (path === '/api/auth/me') return void await json(authResponse);
    if (path === '/api/account-state' && method === 'GET') {
      return void await json({
        success: true,
        cart: [{ productId: 'aio-product-1', variantId: 'aio-variant-1', quantity: 1 }],
        wishlist: [],
      });
    }
    if (path === '/api/account-state/cart' && method === 'PATCH') {
      return void await json({ success: true, cart: [] });
    }
    if (path === '/api/shop-products/published' && method === 'GET') {
      return void await json({ success: true, products: [allIndiaProduct] });
    }
    if (path === '/api/serviceability' && method === 'GET') {
      return void await json({
        success: true,
        pincode: '458441',
        serviceable: true,
        enforcementMode: 'pincode',
      });
    }
    if (path === '/api/mediator-orders' && method === 'POST') {
      mediatorPayload = request.postDataJSON() as Record<string, unknown>;
      return void await json({ success: true, idempotent: false, order: mediatorOrder }, 201);
    }
    if (path === '/api/mediator-orders/AIO-E2E-0001' && method === 'GET') {
      return void await json({ success: true, order: mediatorOrder });
    }

    return void await json({ success: false, error: `Unexpected mocked API request: ${method} ${path}` }, 500);
  });

  await page.goto('/checkout');

  await expect(page.getByRole('heading', { name: 'Secure Checkout' })).toBeVisible();
  await expect(page.getByRole('radio', { name: /All India/ })).toBeVisible();
  await page.getByRole('radio', { name: /All India/ }).check();

  await expect(page.getByRole('heading', { name: 'All India Order Request' })).toBeVisible();
  await expect(page.getByText('Vibe4You is the mediator only for this All India order.')).toBeVisible();
  await expect(page.getByText('You will pay the courier / delivery charge.', { exact: false })).toBeVisible();

  await page.getByLabel('Full Name').fill('All India E2E Customer');
  await page.getByLabel('Phone Number').fill('9876543210');
  await page.getByLabel('Street Address & Landmark').fill('12 Test Street');
  await page.getByLabel('City').fill('Jaipur');
  await page.getByLabel('State').fill('Rajasthan');
  await page.getByLabel('Pincode').fill('302001');

  await expect(page.getByRole('radio', { name: /Cash \/ Pay on Delivery/ })).toHaveCount(0);
  await expect(page.getByRole('radio', { name: /UPI with Razorpay/ })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Send Order Request to Shop' })).toBeEnabled();

  await page.getByRole('button', { name: 'Send Order Request to Shop' }).click();

  await expect(page).toHaveURL(/\/mediator-order-success\/AIO-E2E-0001$/);
  await expect(page.getByRole('heading', { name: 'Order request sent to the shop' })).toBeVisible();

  await expect.poll(() => mediatorPayload).toMatchObject({
    items: [{ productId: 'aio-product-1', variantId: 'aio-variant-1', quantity: 1 }],
    address: {
      name: 'All India E2E Customer',
      phone: '9876543210',
      street: '12 Test Street',
      city: 'Jaipur',
      state: 'Rajasthan',
      pincode: '302001',
    },
  });

  const forbiddenPosts = calls.filter(call =>
    call.method === 'POST'
    && ['/api/create-order', '/api/place-cod-order', '/api/verify-payment'].includes(call.path),
  );
  expect(forbiddenPosts).toEqual([]);
});
