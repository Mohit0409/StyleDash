import { expect, test } from '@playwright/test';

test('mobile homepage and search work', async ({ page }) => {
  await page.goto('/');

  await expect(
    page.getByRole('heading', { name: /Your look/i }),
  ).toBeVisible();

  const search = page.getByPlaceholder('Search products and brands');

  await search.fill('shirt');
  await search.press('Enter');

  await expect(page).toHaveURL(/\/products\?search=shirt$/);

  await expect(page.locator('main')).toBeVisible();
});

test('mobile legal and support routes render without 404', async ({
  page,
}) => {
  for (const route of ['/help', '/privacy', '/terms', '/returns']) {
    await page.goto(route);

    await expect(
      page.getByRole('heading', { name: 'Page Not Found' }),
    ).toHaveCount(0);
  }
});
