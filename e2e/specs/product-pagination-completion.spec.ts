import { expect, test } from '@playwright/test';
import { PRODUCTS } from '../../src/data/products';

test('homepage product rows keep horizontal scrolling but never render numbered pagination', async ({ page }) => {
  await page.goto('/');
  const rail = page.getByTestId('top-picks-rail');
  await expect(rail).toBeVisible();
  const cards = rail.locator('[data-home-product-card]');
  const originalCount = await cards.count();
  expect(originalCount).toBeGreaterThan(5);

  await expect(page.locator('[data-testid$="-rail-pagination"]')).toHaveCount(0);
  await expect(page.getByRole('navigation', { name: /product pages/i })).toHaveCount(0);
  const before = await rail.evaluate(element => element.scrollLeft);
  await rail.evaluate(element => { element.scrollLeft += Math.max(element.clientWidth * 0.8, 240); });
  await expect.poll(() => rail.evaluate(element => element.scrollLeft)).toBeGreaterThan(before + 10);
  expect(await cards.count()).toBe(originalCount);
  await expect(page.getByRole('link', { name: /View All/ }).first()).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});

test('related product recommendations paginate after asynchronous suggestions arrive', async ({ page }) => {
  const sourceProduct = PRODUCTS[0];
  const suggestions = PRODUCTS.slice(1, 9);
  await page.route('**/api/shop-products/similar?slug=*&limit=8', route => route.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify({ success: true, products: suggestions }),
  }));
  await page.goto('/product/' + sourceProduct.slug + '?relatedPage=2');
  const grid = page.getByTestId('related-products-grid');
  const pager = page.getByTestId('related-products-pagination');
  await expect(grid.locator('a[data-product-card-image]')).toHaveCount(4);
  await expect(pager).toBeVisible();
  await expect(pager.getByRole('button', { name: /Page 2 of 2 for related products/ }))
    .toHaveAttribute('aria-current', 'page');
  const pageTwoFirst = await grid.locator('a[data-product-card-image]').first().getAttribute('href');
  await pager.getByRole('button', { name: /Page 1 of 2 for related products/ }).click();
  await expect(page).toHaveURL(new RegExp('/product/' + sourceProduct.slug + '$'));
  await expect(grid.locator('a[data-product-card-image]').first()).not.toHaveAttribute('href', pageTwoFirst || '');
  await page.goBack();
  await expect(page).toHaveURL(/relatedPage=2/);
  await expect(grid.locator('a[data-product-card-image]').first()).toHaveAttribute('href', pageTwoFirst || '');
});
