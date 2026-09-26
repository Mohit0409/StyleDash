import { expect, test } from '@playwright/test';

const application = (status: string, overrides: Record<string, unknown> = {}) => ({
  id: 'shop-onboarding-1',
  status,
  shopName: 'Neemuch Style Hub',
  ownerName: 'Seller E2E',
  registeredEmail: 'seller@example.test',
  category: 'Clothing & Fashion',
  description: 'A complete local fashion shop for onboarding coverage.',
  address: '12 Main Market Road',
  city: 'Neemuch',
  state: 'Madhya Pradesh',
  pincode: '458441',
  businessInformation: 'Local fashion retailer.',
  createdAt: '2026-08-20T00:00:00Z',
  updatedAt: '2026-08-20T00:00:00Z',
  ...overrides,
});

const authResponse = {
  success: true,
  csrfToken: 'csrf-onboarding',
  user: { uid: 'seller-1', name: 'Seller E2E', email: 'seller@example.test', role: 'customer' },
};
test('rejected shop owner can correct and resubmit the application', async ({ page }) => {
  let current = application('REJECTED', { rejectionReason: 'Please correct the shop address.' });
  let patchPayload: Record<string, unknown> | null = null;

  await page.route('**/api/**', async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const method = request.method();
    const json = (body: unknown, status = 200) => route.fulfill({
      status, contentType: 'application/json', body: JSON.stringify(body),
    });

    if (path === '/api/auth/me') return void await json(authResponse);
    if (path === '/api/account-state') return void await json({ success: true, cart: [], wishlist: [] });
    if (path === '/api/vendor-applications/me' && method === 'GET') {
      return void await json({ success: true, application: current });
    }
    if (path === '/api/vendor-applications/me' && method === 'PATCH') {
      patchPayload = request.postDataJSON() as Record<string, unknown>;
      current = application('DRAFT', { ...patchPayload, rejectionReason: null });
      return void await json({ success: true, application: current });
    }
    if (path === '/api/vendor-applications/me/submit' && method === 'POST') {
      current = application('SUBMITTED', { ...patchPayload, rejectionReason: null });
      return void await json({ success: true, application: current });
    }    return void await json({ success: false, error: `Unexpected ${method} ${path}` }, 500);
  });

  await page.goto('/partner');
  await expect(page.getByRole('heading', { name: 'Changes Requested', exact: true }).first()).toBeVisible();
  await expect(page.getByText('Please correct the shop address.')).toBeVisible();
  await expect(page.getByRole('navigation', { name: 'Shop onboarding progress' })).toBeVisible();

  await page.getByLabel('Shop address').fill('14 Corrected Main Market Road');
  await page.getByRole('button', { name: 'Submit for Review' }).click();

  await expect(page.getByRole('heading', { name: 'Application Submitted', exact: true }).first()).toBeVisible();
  await expect(page.getByText('Status: SUBMITTED')).toBeVisible();
  expect(patchPayload?.address).toBe('14 Corrected Main Market Road');
  await expect(page.getByRole('navigation', { name: 'Shop onboarding progress' })
    .locator('[aria-current="step"]')).toContainText('Submitted');
});

test('partner form exposes every canonical store category and preserves legacy draft values', async ({ page }) => {
  let current: Record<string, unknown> | null = application('DRAFT', { category: 'Beauty & Personal Care' });
  let patchPayload: Record<string, unknown> | null = null;

  await page.route('**/api/**', async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const method = request.method();
    const json = (body: unknown, status = 200) => route.fulfill({
      status, contentType: 'application/json', body: JSON.stringify(body),
    });
    if (path === '/api/auth/me') return void await json(authResponse);
    if (path === '/api/account-state') return void await json({ success: true, cart: [], wishlist: [] });
    if (path === '/api/vendor-applications/me' && method === 'GET') return void await json({ success: true, application: current });
    if (path === '/api/vendor-applications/me' && method === 'PATCH') {
      patchPayload = request.postDataJSON() as Record<string, unknown>;
      current = application('DRAFT', { ...patchPayload });
      return void await json({ success: true, application: current });
    }
    return void await json({ success: false, error: `Unexpected ${method} ${path}` }, 500);
  });

  await page.goto('/partner');
  await expect(page.getByRole('heading', { name: 'Continue Application', exact: true }).first()).toBeVisible();
  const categorySelect = page.getByLabel('Category');
  await expect(categorySelect.locator('option').first()).toBeAttached();
  const options = await categorySelect.locator('option').allTextContents();
  expect(options).toEqual([
    'Clothing & Fashion',
    'Footwear',
    'Accessories',
    'Beauty & Personal Care',
    'Electronics',
    'Gifts',
    'Home & Living',
  ]);
  await expect(categorySelect).toHaveValue('Beauty & Personal Care');
  await categorySelect.selectOption('Gifts');
  await page.getByRole('button', { name: 'Save Draft' }).click();
  expect(patchPayload?.category).toBe('Gifts');
});

test('partner form keeps a legacy draft category selectable instead of resetting it', async ({ page }) => {
  await page.route('**/api/**', async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const json = (body: unknown) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
    if (path === '/api/auth/me') return void await json(authResponse);
    if (path === '/api/account-state') return void await json({ success: true, cart: [], wishlist: [] });
    if (path === '/api/vendor-applications/me') {
      return void await json({ success: true, application: application('DRAFT', { category: 'General Store' }) });
    }
    return void await json({ success: false, error: `Unexpected ${request.method()} ${path}` }, 500);
  });

  await page.goto('/partner');
  await expect(page.getByRole('heading', { name: 'Continue Application', exact: true }).first()).toBeVisible();
  const categorySelect = page.getByLabel('Category');
  await expect(categorySelect.locator('option').first()).toBeAttached();
  const options = await categorySelect.locator('option').allTextContents();
  expect(options[0]).toBe('General Store');
  expect(options).toContain('Gifts');
  expect(options).toHaveLength(8);
  await expect(categorySelect).toHaveValue('General Store');
});

test('active shop progress points the seller to products', async ({ page }) => {
  await page.route('**/api/**', async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const json = (body: unknown) => route.fulfill({
      status: 200, contentType: 'application/json', body: JSON.stringify(body),
    });
    if (path === '/api/auth/me') return void await json(authResponse);
    if (path === '/api/account-state') return void await json({ success: true, cart: [], wishlist: [] });
    if (path === '/api/vendor-applications/me') {
      return void await json({ success: true, application: application('ACTIVE') });
    }
    if (path === '/api/shop-products') return void await json({ success: true, products: [] });
    if (path === '/api/shop-product-requests') return void await json({ success: true, requests: [] });
    return void await json({ success: false, error: `Unexpected ${request.method()} ${path}` });
  });

  await page.goto('/partner');
  const progress = page.getByRole('navigation', { name: 'Shop onboarding progress' });
  await expect(page.getByRole('heading', { name: 'Shop Active', exact: true }).first()).toBeVisible();
  await expect(progress.locator('[aria-current="step"]')).toContainText('Products');
  await expect(page.getByText('Your shop is active. Add products below and submit them for administrator review.')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Product submissions' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'New Product Draft' })).toBeVisible();
});
