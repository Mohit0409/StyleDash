import { expect, test } from '@playwright/test';

const routes = [
  '/',
  '/products',
  '/categories',
  '/stores',
  '/wishlist',
  '/help',
  '/returns',
  '/privacy',
  '/terms',
];

for (const route of routes) {
  test(`public route ${route} renders`, async ({ page }) => {
    const response = await page.goto(route);

    expect(response?.ok()).toBeTruthy();

    await expect(page.locator('main')).toBeVisible();
    await expect(
      page.getByRole('heading', { name: 'Page Not Found' }),
    ).toHaveCount(0);
  });
}

test('unknown route renders StyleDash 404', async ({ page }) => {
  await page.goto('/this-route-must-not-exist-e2e');

  await expect(
    page.getByRole('heading', { name: '404', exact: true }),
  ).toBeVisible();

  await expect(
    page.getByRole('heading', { name: 'Page Not Found' }),
  ).toBeVisible();
});

test('restricted payment product fails closed for anonymous visitor', async ({
  page,
}) => {
  const response = await page.goto(
    '/payment-test/styledash-payment-test-item',
  );

  expect(response).not.toBeNull();
  expect(response!.status()).toBe(404);

  const payload = await response!.json();

  expect(payload).toEqual({
    success: false,
    error: 'Not found.',
    code: 'not_found',
  });

  // The denial must not reveal the hidden product or authorization rules.
  await expect(page.locator('body')).not.toContainText(
    'StyleDash Payment Test Item',
  );
  await expect(page.locator('body')).not.toContainText(
    'e2e-owner@example.test',
  );
  await expect(page.locator('body')).not.toContainText(
    'mailbox',
  );
});
