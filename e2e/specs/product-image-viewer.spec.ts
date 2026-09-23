import { expect, test } from '@playwright/test';

const PRODUCT_ROUTE = '/product/pure-cotton-oversized-graphic-tee-sd-prod-001';

test('product images fill fixed cards and the detail viewer is accessible', async ({ page }) => {
  // The test validates card layout, not a third-party image CDN. Use a stable
  // valid image response so an external-image outage cannot switch the card to
  // its intentional contained placeholder before the cover assertion runs.
  await page.route('https://images.unsplash.com/**', route => route.fulfill({
    contentType: 'image/svg+xml',
    body: '<svg xmlns="http://www.w3.org/2000/svg" width="8" height="8"><rect width="8" height="8" fill="#111"/></svg>',
  }));

  // Exercise the four requested responsive viewports without creating any order,
  // payment, account, or catalogue state.
  for (const viewport of [
    { width: 1920, height: 1080 },
    { width: 1366, height: 768 },
    { width: 390, height: 844 },
    { width: 360, height: 800 },
  ]) {
    await page.setViewportSize(viewport);
    await page.goto('/');

    const cards = page.locator('[data-product-card-image]');
    await expect(cards.first()).toBeVisible();
    await expect(cards.first().locator('img')).toHaveCSS('object-fit', 'cover');

    const firstBox = await cards.nth(0).boundingBox();
    const secondBox = await cards.nth(1).boundingBox();
    expect(firstBox?.height).toBe(secondBox?.height);
    expect(firstBox?.width).toBe(secondBox?.width);
  }

  await page.goto(PRODUCT_ROUTE);
  const galleryButton = page.getByRole('button', { name: /open full screen image/i });
  await expect(galleryButton).toBeVisible();
  await expect(galleryButton.locator('img')).toHaveCSS('object-fit', 'contain');

  await galleryButton.click();
  const viewer = page.getByRole('dialog', { name: /image viewer/i });
  await expect(viewer).toBeVisible();
  await expect(viewer.locator('img')).toHaveCSS('object-fit', 'contain');
  await expect.poll(() => page.evaluate(() => document.body.style.overflow)).toBe('hidden');

  const viewerImage = viewer.locator('img');
  const firstImageUrl = await viewerImage.getAttribute('src');
  await page.keyboard.press('ArrowRight');
  await expect(viewerImage).not.toHaveAttribute('src', firstImageUrl || '');
  await page.keyboard.press('ArrowLeft');
  await expect(viewerImage).toHaveAttribute('src', firstImageUrl || '');

  await viewerImage.dispatchEvent('pointerdown', { pointerId: 1, pointerType: 'touch', clientX: 280, clientY: 300 });
  await viewerImage.dispatchEvent('pointermove', { pointerId: 1, pointerType: 'touch', clientX: 120, clientY: 300 });
  await viewerImage.dispatchEvent('pointerup', { pointerId: 1, pointerType: 'touch', clientX: 120, clientY: 300 });
  await expect(viewerImage).not.toHaveAttribute('src', firstImageUrl || '');

  await page.keyboard.press('Escape');
  await expect(viewer).toBeHidden();
  await expect(galleryButton).toBeFocused();
  await expect.poll(() => page.evaluate(() => document.body.style.overflow)).toBe('');
});
