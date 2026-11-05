import { expect, test } from '@playwright/test';

const product = {
  id: 'outside-delivery-e2e',
  slug: 'outside-delivery-e2e',
  name: 'Outside Delivery Test Watch',
  price: 1250,
  active: true,
  outsideNeemuchDeliveryAvailable: true,
  images: [],
  thumbnail: '/product-placeholder.svg',
  variants: [{
    id: 'outside-e2e-variant',
    size: 'One size',
    colourName: 'Silver',
    price: 1250,
    available: true,
  }],
};

test('eligible product opens inline request and submitted request appears in history', async ({ page }) => {
  const email = 'outside-delivery-flow@example.test';
  let postedPayload: Record<string, unknown> | null = null;
  let created = false;
  let listCount = 0;

  await page.route('**/api/auth/me', route => route.fulfill({
    status: 401,
    contentType: 'application/json',
    body: JSON.stringify({ success: false, code: 'authentication_required' }),
  }));
  await page.route('**/api/auth/login', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      success: true,
      csrfToken: 'outside-e2e-csrf',
      user: { uid: 'outside-flow-e2e', name: 'Outside E2E', email, role: 'customer' },
    }),
  }));
  await page.route('**/api/shop-products/published?slug=outside-delivery-e2e', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ success: true, product }),
  }));
  await page.route('**/api/inventory/availability?productId=*', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      success: true,
      availability: [{ variantId: 'outside-e2e-variant', available: true }],
    }),
  }));
  await page.route('**/api/outside-delivery-requests', async route => {
    if (route.request().method() === 'POST') {
      postedPayload = route.request().postDataJSON() as Record<string, unknown>;
      created = true;
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({ idempotent: false, request: { id: 'outside-e2e-request' } }),
      });
      return;
    }
    listCount++;
    const request = {
      id: 'outside-e2e-request',
      productId: product.id,
      productName: product.name,
      productSlug: product.slug,
      variantId: 'outside-e2e-variant',
      size: 'One size',
      colourName: 'Silver',
      quantity: 2,
      productSubtotal: 2500,
      address: {
        name: 'Outside E2E Customer',
        phone: '9999999999',
        street: '12 Test Colony',
        city: 'Bhopal',
        state: 'Madhya Pradesh',
        pincode: '462001',
      },
      status: 'requested',
      createdAt: '2026-11-06T00:00:00Z',
      updatedAt: '2026-11-06T00:00:00Z',
    };
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ requests: created ? [request] : [] }),
    });
  });

  await page.goto('/delivery-requests?product=outside-delivery-e2e&variant=outside-e2e-variant&qty=2');
  await expect(page).toHaveURL(/\/login$/);
  await page.getByPlaceholder('Email').fill(email);
  await page.getByPlaceholder('Password (8+ characters)').fill('Testing12345!');
  await page.getByRole('checkbox', { name: /agree to the terms/i }).check();
  await page.getByRole('button', { name: 'Login' }).click();

  await expect(page.getByRole('heading', { name: 'Request delivery to your city' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Request product delivery' })).toBeVisible();
  await expect(page.getByText('Outside Delivery Test Watch')).toBeVisible();

  await page.getByLabel('Full name').fill('Outside E2E Customer');
  await page.getByLabel('Phone number').fill('9999999999');
  await page.getByLabel('Street address & landmark').fill('12 Test Colony');
  await page.getByLabel('City', { exact: true }).fill('Bhopal');
  await page.getByLabel('State', { exact: true }).fill('Madhya Pradesh');
  await page.getByLabel('Pincode').fill('462001');
  await page.getByRole('button', { name: 'Request Delivery Quote' }).click();

  await expect(page.getByRole('status').filter({ hasText: 'Delivery request submitted successfully!' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Outside Delivery Test Watch' })).toBeVisible();
  await expect(page.getByText('12 Test Colony, Bhopal, Madhya Pradesh 462001')).toBeVisible();
  expect(listCount).toBeGreaterThanOrEqual(2);
  expect(postedPayload).toMatchObject({
    productId: product.id,
    variantId: 'outside-e2e-variant',
    quantity: 2,
    address: { city: 'Bhopal', pincode: '462001' },
  });
  expect(postedPayload).not.toHaveProperty('unitPrice');
  expect(postedPayload).not.toHaveProperty('deliveryFee');
  expect(page.url()).not.toContain('9999999999');
  expect(page.url()).not.toContain('12%20Test');
});

test('ineligible product cannot open the request form', async ({ page }) => {
  await page.route('**/api/auth/me', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      success: true,
      user: { uid: 'ineligible-flow-e2e', name: 'Test Customer', email: 'ineligible-flow@example.test', role: 'customer' },
    }),
  }));
  await page.route('**/api/shop-products/published?slug=outside-delivery-e2e', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ success: true, product: { ...product, outsideNeemuchDeliveryAvailable: false } }),
  }));
  await page.route('**/api/inventory/availability?productId=*', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ success: true, availability: [{ variantId: 'outside-e2e-variant', available: true }] }),
  }));
  await page.route('**/api/outside-delivery-requests', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ requests: [] }),
  }));
  await page.goto('/delivery-requests?product=outside-delivery-e2e&variant=outside-e2e-variant&qty=2');
  await expect(page.getByRole('alert').filter({ hasText: /not currently eligible/ })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Request Delivery Quote' })).toHaveCount(0);
});
