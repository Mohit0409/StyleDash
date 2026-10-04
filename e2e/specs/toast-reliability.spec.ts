import { expect, test } from '@playwright/test';

test('a failed public review request displays one error without retrying in a toast loop', async ({ page }) => {
  let requests = 0;
  await page.route('**/api/reviews?*', async route => {
    requests += 1;
    await route.fulfill({
      status: 401,
      contentType: 'application/json',
      body: JSON.stringify({ error: 'Authentication required.', code: 'authentication_required' }),
    });
  });

  await page.goto('/product/pure-cotton-oversized-graphic-tee-sd-prod-001');
  await expect(page.getByRole('heading', { name: 'Customer Reviews' })).toBeVisible();
  await expect(page.getByText('Authentication required.')).toHaveCount(1);

  // This interval is intentionally long enough for a render-triggered retry to occur.
  await page.waitForTimeout(250);
  expect(requests).toBe(1);
});
