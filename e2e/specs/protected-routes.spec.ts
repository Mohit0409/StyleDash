import { expect, test } from '@playwright/test';

const protectedRoutes = [
  '/checkout',
  '/orders',
  '/profile',
  '/partner',
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
  await page.getByRole('button', { name: 'Login' }).click();

  await expect(page).toHaveURL(/\/partner\?entry=header$/);
  await expect(page.getByRole('heading', { name: 'Start Shop Application' })).toBeVisible();
});
