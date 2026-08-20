import { expect, test } from '@playwright/test';

const PRODUCT_IMAGE_FALLBACK = '/product-placeholder.svg';

test('a failed product image keeps one local fallback across hover rerenders', async ({ page }) => {
  let fallbackRequests = 0;
  await page.route('https://images.unsplash.com/**', route => route.fulfill({
    status: 200,
    contentType: 'image/svg+xml',
    body: '<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"/>',
  }));
  await page.route('**/product-placeholder.svg', async route => {
    fallbackRequests += 1;
    await route.abort('failed');
  });
  await page.route('**/deliberately-missing-product-image.jpg', route => route.abort('failed'));

  await page.goto('/products');
  const productImage = page.locator('a[href^="/product/"] img').first();
  await productImage.scrollIntoViewIfNeeded();
  await productImage.evaluate(image => {
    (image as HTMLImageElement).src = '/deliberately-missing-product-image.jpg';
  });

  await expect(productImage).toHaveAttribute('src', PRODUCT_IMAGE_FALLBACK);
  await expect.poll(() => fallbackRequests).toBe(1);
  await productImage.hover();
  await expect(productImage).toHaveAttribute('src', PRODUCT_IMAGE_FALLBACK);
  await page.mouse.move(0, 0);
  await productImage.hover();
  await expect(productImage).toHaveAttribute('src', PRODUCT_IMAGE_FALLBACK);
  expect(fallbackRequests).toBe(1);
});
