import { expect, test } from '@playwright/test';

const protectedRoutes = [
  '/checkout',
  '/orders',
  '/orders/SD-E2E-PROTECTED/track',
  '/profile',
  '/partner',
  '/delivery-requests',
];

for (const route of protectedRoutes) {
  test(`${route} requires authentication`, async ({ page }) => {
    await page.goto(route);

    await expect(page).toHaveURL(/\/login$/);

    await expect(
      page.getByRole('heading', { name: 'Welcome back' }),
    ).toBeVisible();
  });
}

test('List Your Shop returns to the complete intended route after login', async ({ page }) => {
  const email = 'e2e-partner-return@example.test';
  const password = 'E2E-only-password-2026!';

  await page.route('**/api/auth/me', route => route.fulfill({
    status: 401,
    contentType: 'application/json',
    body: JSON.stringify({ success: false, error: 'Authentication is required.', code: 'authentication_required' }),
  }));
  await page.route('**/api/auth/login', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      success: true,
      csrfToken: 'csrf-partner-return-e2e',
      user: { uid: 'partner-return-e2e', name: 'Partner Return E2E', email, role: 'customer' },
    }),
  }));
  await page.route('**/api/vendor-applications/me', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ success: true, application: null }),
  }));

  await page.goto('/partner?entry=header');
  await expect(page).toHaveURL(/\/login$/);
  await page.getByPlaceholder('Email').fill(email);
  await page.getByPlaceholder('Password (8+ characters)').fill(password);
  await page.getByRole('checkbox', { name: /agree to the terms/i }).check();
  await page.getByRole('button', { name: 'Login' }).click();

  await expect(page).toHaveURL(/\/partner\?entry=header$/);
  await expect(page.getByRole('heading', { name: 'Start Shop Application' })).toBeVisible();
});


test('delivery request keeps product and variant selection after sign-in', async ({ page }) => {
  const email = 'e2e-delivery-return@example.test';
  const password = 'Testing12345!';
  const intendedPath = '/delivery-requests?product=casio-f-91w-blue&variant=v-silver%2Fblue&qty=2';

  await page.route('**/api/auth/me', route => route.fulfill({
    status: 401,
    contentType: 'application/json',
    body: JSON.stringify({ success: false, error: 'Authentication required', code: 'authentication_required' }),
  }));
  await page.route('**/api/auth/login', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      success: true,
      csrfToken: 'e2e-test-token',
      user: { uid: 'delivery-return-e2e', name: 'Delivery Return E2E', email, role: 'customer' },
    }),
  }));

  await page.goto(intendedPath);
  await expect(page).toHaveURL(/\/login$/);
  await page.getByPlaceholder('Email').fill(email);
  await page.getByPlaceholder('Password (8+ characters)').fill(password);
  await page.getByRole('checkbox', { name: /agree to the terms/i }).check();
  await page.getByRole('button', { name: 'Login' }).click();

  await expect(page).toHaveURL(new RegExp('\\/delivery-requests\\?product=casio-f-91w-blue&variant=v-silver%2Fblue&qty=2$'));
  await expect(page.getByRole('heading', { name: 'Request delivery to your city' })).toBeVisible();
});
