import { expect, test } from '@playwright/test';

test('approved shop owner can draft and submit but cannot publish a product', async ({ page }) => {
  let product: Record<string, unknown> | null = null;
  let createPayload: Record<string, unknown> | null = null;

  await page.route('**/api/**', async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const method = request.method();
    const json = (body: unknown, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });

    if (path === '/api/auth/me') {
      await json({ success: true, csrfToken: 'csrf-e2e', user: { uid: 'seller-1', name: 'Seller E2E', email: 'seller@example.test', role: 'customer' } });
      return;
    }
    if (path === '/api/vendor-applications/me' && method === 'GET') {
      await json({ success: true, application: {
        id: 'shop-1', status: 'ACTIVE', shopName: 'E2E Active Shop', ownerName: 'Seller E2E',
        registeredEmail: 'seller@example.test', category: 'Clothing & Fashion', description: 'Active test shop',
        address: 'Main market', city: 'Neemuch', state: 'Madhya Pradesh', pincode: '458441',
        createdAt: '2026-08-20T00:00:00Z', updatedAt: '2026-08-20T00:00:00Z',
      } });
      return;
    }
    if (path === '/api/shop-products' && method === 'GET') {
      await json({ success: true, products: product ? [product] : [] });
      return;
    }
    if (path === '/api/shop-products' && method === 'POST') {
      createPayload = request.postDataJSON() as Record<string, unknown>;
      product = {
        ...createPayload, id: 'shopprod_1', slug: 'local-product-shopprod-1', applicationId: 'shop-1',
        status: 'DRAFT', createdAt: '2026-08-20T00:00:00Z', updatedAt: '2026-08-20T00:00:00Z',
      };
      await json({ success: true, product }, 201);
      return;
    }
    if (path === '/api/shop-products/shopprod_1/submit' && method === 'POST') {
      product = { ...(product || {}), status: 'SUBMITTED', submittedAt: '2026-08-20T00:01:00Z' };
      await json({ success: true, product });
      return;
    }
    await json({ success: false, error: 'Unexpected mocked API request.' }, 500);
  });

  await page.goto('/partner');
  await expect(page.getByRole('heading', { name: 'Shop Active', exact: true }).first()).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Product submissions' })).toBeVisible();

  await page.getByRole('button', { name: 'New Product Draft' }).click();
  await page.getByLabel('Product name').fill('Local Product');
  await page.getByLabel('Description').fill('A locally submitted product for private review.');
  await page.getByLabel('Price (INR)', { exact: true }).fill('500');
  await page.getByLabel('Original price (INR)').fill('600');
  await page.getByLabel('Inventory').fill('2');
  await page.getByLabel('Size').fill('M');
  await page.getByLabel('Colour name').fill('Black');
  await page.getByLabel(/HTTPS image URLs/).fill('https://example.test/product.jpg');
  await page.getByRole('button', { name: 'Save Product Draft' }).click();

  await expect(page.getByRole('heading', { name: 'Local Product' })).toBeVisible();
  await expect(page.getByText('DRAFT', { exact: true })).toBeVisible();
  expect(createPayload).not.toHaveProperty('status');
  expect(createPayload).not.toHaveProperty('applicationId');

  await page.getByRole('button', { name: 'Submit', exact: true }).click();
  await expect(page.getByText('SUBMITTED', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: /publish/i })).toHaveCount(0);
});
