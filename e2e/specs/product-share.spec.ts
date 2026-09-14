import { expect, test } from '@playwright/test';

const PRODUCT_PATH = '/product/pure-cotton-oversized-graphic-tee-sd-prod-001';

test('product can be shared with the native share sheet using its direct URL', async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(navigator, 'share', {
      configurable: true,
      value: async (data: ShareData) => {
        (window as typeof window & { __vibe4youShare?: ShareData }).__vibe4youShare = data;
      },
    });
  });

  await page.goto(PRODUCT_PATH);
  const shareButton = page.getByRole('button', { name: /Share Pure Cotton Oversized Graphic Tee/i });
  await expect(shareButton).toBeVisible();
  await shareButton.click();

  const payload = await page.evaluate(() => (window as typeof window & { __vibe4youShare?: ShareData }).__vibe4youShare);
  expect(payload?.title).toContain('Vibe4You');
  expect(payload?.text).toContain('Pure Cotton Oversized Graphic Tee');
  expect(payload?.url).toContain(PRODUCT_PATH);
});
