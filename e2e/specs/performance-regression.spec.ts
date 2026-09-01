import { expect, test } from '@playwright/test';

test('products prioritizes only the first visible catalogue image', async ({ page }) => {
  await page.goto('/products');

  const productImages = page.locator('a[href^="/product/"] img');
  await expect(productImages.first()).toBeVisible();
  expect(await productImages.count()).toBeGreaterThan(1);

  await expect(productImages.first()).toHaveAttribute('loading', 'eager');
  await expect(productImages.first()).toHaveAttribute('fetchpriority', 'high');
  await expect(productImages.nth(1)).toHaveAttribute('loading', 'lazy');
  await expect(productImages.nth(1)).toHaveAttribute('fetchpriority', 'auto');
});

test('stores reserves loading space and rejects obvious HTML image pages', async ({ page }) => {
  let releaseStores: (() => void) | undefined;
  const storesGate = new Promise<void>(resolve => { releaseStores = resolve; });
  let invalidImageRequests = 0;

  page.on('request', request => {
    if (request.url().includes('stacked-jeans_3160982.html')) invalidImageRequests += 1;
  });
  await page.route('**/api/stores/active', async route => {
    await storesGate;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        stores: [{
          id: 'legacy-html-store', slug: 'legacy-html-store', storeName: 'Legacy HTML Store',
          category: 'Clothing & Fashion', address: 'Neemuch', pincode: '458441', city: 'Neemuch',
          deliveryMinutes: 60, description: 'Legacy store image test', active: true, approved: true,
          bannerImage: 'https://pngtree.com/freepng/stacked-jeans_3160982.html', logoImage: null,
          createdAt: '2026-01-01T00:00:00Z',
        }],
      }),
    });
  });

  await page.goto('/stores');
  const skeletons = page.getByTestId('stores-loading-skeleton');
  await expect(skeletons).toHaveCount(3);
  await expect(skeletons.first()).toBeVisible();
  expect(await skeletons.first().evaluate(el => el.getBoundingClientRect().height)).toBeGreaterThanOrEqual(350);

  releaseStores?.();

  await expect(page.getByRole('heading', { name: 'Legacy HTML Store' })).toBeVisible();
  await expect(page.getByLabel('Legacy HTML Store cover placeholder')).toBeVisible();
  await expect(page.getByLabel('Legacy HTML Store logo placeholder')).toBeVisible();
  await expect(page.locator('img[src*="stacked-jeans_3160982.html"]')).toHaveCount(0);
  expect(invalidImageRequests).toBe(0);
});
