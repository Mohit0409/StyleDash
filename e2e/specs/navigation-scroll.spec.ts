import { expect, test } from '@playwright/test';

const expectPageTop = async (page: import('@playwright/test').Page) => {
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBeLessThanOrEqual(2);
};

test('normal route navigation opens at the top from a footer link', async ({ page }) => {
  await page.goto('/privacy');
  const helpLink = page.getByRole('link', { name: 'Help & Support' });
  await helpLink.scrollIntoViewIfNeeded();
  expect(await page.evaluate(() => window.scrollY)).toBeGreaterThan(0);

  await helpLink.click();

  await expect(page).toHaveURL(/\/help$/);
  await expect(page.getByRole('heading', { name: 'Help and customer support' })).toBeVisible();
  await expectPageTop(page);
});

test('product detail navigation always starts at the top', async ({ page }) => {
  await page.goto('/products');
  const productLink = page.getByRole('link', { name: 'Select Option' }).last();
  await productLink.scrollIntoViewIfNeeded();
  expect(await page.evaluate(() => window.scrollY)).toBeGreaterThan(0);

  await productLink.click();

  await expect(page).toHaveURL(/\/product\//);
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
  await expectPageTop(page);
});

test('same-page help anchors scroll to their requested content', async ({ page }) => {
  await page.goto('/help');

  await page.getByRole('link', { name: 'Payments', exact: true }).click();

  await expect(page).toHaveURL(/\/help#payments$/);
  await expect(page.locator('#payments')).toBeInViewport();
  expect(await page.evaluate(() => window.scrollY)).toBeGreaterThan(0);
});

test('back navigation preserves the browser history scroll position', async ({ page }) => {
  await page.goto('/products');
  await page.getByRole('link', { name: 'Select Option' }).last().scrollIntoViewIfNeeded();
  const previousPosition = await page.evaluate(() => window.scrollY);
  expect(previousPosition).toBeGreaterThan(0);

  await page.locator('header a[href="/"]').first().click();
  await expect(page).toHaveURL(/\/$/);
  await expectPageTop(page);

  await page.goBack();
  await expect(page).toHaveURL(/\/products$/);
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThanOrEqual(Math.max(1, previousPosition - 100));
});
