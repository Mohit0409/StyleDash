import { expect, test } from '@playwright/test';

const PRODUCT_PATH = '/product/pure-cotton-oversized-graphic-tee-sd-prod-001';

test('product detail provides real marketplace SEO and useful specifications', async ({ page }) => {
  await page.goto(PRODUCT_PATH);
  await expect(page.getByRole('heading', { level: 1, name: 'Pure Cotton Oversized Graphic Tee' })).toBeVisible();
  await expect(page).toHaveTitle(/Buy Pure Cotton Oversized Graphic Tee in Neemuch/);
  await expect(page.getByRole('heading', { level: 2, name: 'Product information' })).toBeVisible();
  await expect(page.getByText('Available through Vibe4You in Neemuch')).toBeVisible();
  await expect(page.getByText('Dispatched from Neemuch Partner Boutique')).toHaveCount(0);
  await expect(page.locator('link[rel="canonical"]')).toHaveAttribute(
    'href', 'https://vibe4you.in' + PRODUCT_PATH,
  );
  const schema = await page.locator('#styledash-seo-jsonld').textContent();
  expect(schema).toBeTruthy();
  const product = JSON.parse(schema!);
  expect(product['@type']).toBe('Product');
  expect(product.url).toBe('https://vibe4you.in' + PRODUCT_PATH);
  expect(product.offers.url).toBe(product.url);
  expect(product.offers.seller).toEqual({ '@type': 'Organization', name: 'Vibe4You' });
  expect(product.offers.priceCurrency).toBe('INR');
});

test('missing products use generic catalogue language and are marked noindex', async ({ page }) => {
  await page.goto('/product/not-a-real-vibe4you-item-404');
  await expect(page.getByRole('heading', { name: 'Product Not Found' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Browse All Products' })).toBeVisible();
  await expect(page.locator('meta[name="robots"]')).toHaveAttribute('content', 'noindex,nofollow');
  await expect(page.getByText('fashion item', { exact: false })).toHaveCount(0);
});
