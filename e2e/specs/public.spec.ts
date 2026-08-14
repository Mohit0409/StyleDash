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

test('customer policy pages publish launch contacts without pre-live warnings', async ({
  page,
}) => {
  const warningPhrases = [
    'Support contact pending',
    'Policy decision required',
    'Business details required',
    'Legal review required',
    'before Live Mode',
  ];

  for (const route of ['/help', '/returns', '/privacy', '/terms']) {
    await page.goto(route);

    const main = page.locator('main');
    await expect(main).toContainText('styledashsupport@gmail.com');

    for (const warning of warningPhrases) {
      await expect(main).not.toContainText(warning);
    }
  }

  await page.goto('/help');
  await expect(page.locator('main')).toContainText('+91 8963942394');
  await expect(page.locator('main')).toContainText('Grievance officer: Swapnil');

  await page.goto('/returns');
  await expect(page.locator('main')).toContainText('7-day size exchange');
  await expect(page.locator('main')).toContainText('INR 50');

  await page.goto('/privacy');
  await expect(page.locator('main')).toContainText('Mohit Jangd');
});

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
