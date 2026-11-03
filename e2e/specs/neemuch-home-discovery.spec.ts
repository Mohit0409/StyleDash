import { expect, test } from '@playwright/test';

test('homepage links all production Neemuch landing pages and opens local shops', async ({ page }) => {
  await page.goto('/');
  await expect(page).toHaveTitle(/Online Shopping in Neemuch/);
  const localLinks = page.getByRole('navigation', { name: 'Neemuch local shopping links' });
  await expect(localLinks).toBeVisible();
  await expect(localLinks.getByRole('link')).toHaveCount(20);
  await localLinks.locator('a[href="/neemuch/shops"]').click();
  await expect(page).toHaveURL(/\/neemuch\/shops$/);
  await expect(page.getByRole('heading', { level: 1 })).toContainText(/shops.*Neemuch/i);
});

test('current product-category directory retains dynamic counts with local SEO title', async ({ page }) => {
  await page.goto('/categories');
  await expect(page).toHaveTitle(/Shopping Categories in Neemuch/);
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('All Product Categories');
  const categoryLinks = page.locator('main a[href^="/products?category="]');
  await expect(categoryLinks.first()).toBeVisible();
});
