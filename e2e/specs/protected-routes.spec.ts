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
