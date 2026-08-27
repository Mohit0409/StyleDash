import { expect, test } from '@playwright/test';

test('mobile header wordmark fits at supported widths', async ({ page }) => {
  for (const width of [360, 390, 412]) {
    await page.setViewportSize({ width, height: 844 });
    await page.goto('/');

    const logo = page.getByRole('link', { name: 'vibe4you home' });
    const firstAction = page.getByTitle('Toggle Dark Mode');
    const logoBox = await logo.boundingBox();
    const actionBox = await firstAction.boundingBox();
    const headerWidths = await page.locator('header').evaluate((header) => ({
      client: header.clientWidth,
      scroll: header.scrollWidth,
    }));

    expect(logoBox).not.toBeNull();
    expect(actionBox).not.toBeNull();
    expect(logoBox!.x + logoBox!.width).toBeLessThanOrEqual(actionBox!.x);
    expect(headerWidths.scroll).toBeLessThanOrEqual(headerWidths.client);
    await expect(logo.locator('svg[aria-label="Vibe4You"]')).toBeVisible();
  }
});

test('mobile homepage and search work', async ({ page }) => {
  await page.goto('/');

  await expect(
    page.getByRole('heading', {
      name: /Your City\.\s+Your Shops\.\s+Your Style\./i,
    }),
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
