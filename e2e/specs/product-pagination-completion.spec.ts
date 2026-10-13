import { expect, test } from '@playwright/test';
import { PRODUCTS } from '../../src/data/products';

test('homepage product rows gain numbered page navigation without losing horizontal swipe', async ({ page }) => {
  await page.goto('/');
  const rail = page.getByTestId('top-picks-rail');
  const buttons = page.getByTestId('top-picks-rail-pagination');
  await expect(rail).toBeVisible();
  await expect(buttons).toBeVisible();
  const cards = rail.locator('[data-home-product-card]');
  const originalCount = await cards.count();
  expect(originalCount).toBeGreaterThan(5);
  const before = await rail.evaluate(element => element.scrollLeft);

  await buttons.getByRole('button', { name: 'Top Picks page 2' }).click();
  await expect.poll(() => rail.evaluate(element => element.scrollLeft)).toBeGreaterThan(before + 10);
  await expect(buttons.getByRole('button', { name: 'Top Picks page 2' })).toHaveAttribute('aria-current', 'page');
  expect(await cards.count()).toBe(originalCount);
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
