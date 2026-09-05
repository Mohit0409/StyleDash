import { expect, test } from '@playwright/test';

const stores = Array.from({ length: 10 }, (_, index) => ({
  id: `issue7-store-${index + 1}`,
  slug: `issue7-store-${index + 1}`,
  storeName: index === 0
    ? 'Goutam Shoes'
    : index === 1
      ? 'Nakoda Imitation Jewellery With A Deliberately Long Store Name'
      : `Neemuch Local Store ${index + 1}`,
  category: index % 2 === 0 ? 'Footwear' : 'Clothing & Fashion',
  address: `${index + 1} Market Road`,
  pincode: '458441',
  city: 'Neemuch',
  rating: 5 - (index * 0.05),
  reviewCount: 100 - index,
  deliveryMinutes: 60 + index,
  bannerImage: '/product-placeholder.svg',
  description: index === 1
    ? 'A deliberately long store description that must be clamped and must never change the fixed geometry of this horizontally scrolling card.'
    : `Verified neighbourhood store ${index + 1} serving Neemuch customers.`,
  active: true,
  approved: true,
  createdAt: '2026-09-05T00:00:00Z',
}));

const viewports = [
  { width: 390, height: 844 },
  { width: 1366, height: 768 },
  { width: 1920, height: 1080 },
  { width: 2560, height: 1440 },
] as const;

test('Local Stores uses equal cards in a horizontal-only responsive rail', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop-chromium', 'One Chromium viewport matrix is sufficient.');

  await page.route('**/api/stores/active', async route => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, stores }),
    });
  });

  for (const viewport of viewports) {
    await page.setViewportSize(viewport);
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const rail = page.getByTestId('local-stores-rail');
    await expect(rail).toBeVisible();
    const cards = rail.locator('[data-store-card]');
    await expect(cards).toHaveCount(10);

    const geometry = await cards.evaluateAll(nodes => nodes.map(node => {
      const rect = node.getBoundingClientRect();
      return { width: rect.width, height: rect.height };
    }));
    const widths = geometry.map(item => item.width);
    const heights = geometry.map(item => item.height);
    expect(Math.max(...widths) - Math.min(...widths)).toBeLessThanOrEqual(1);
    expect(Math.max(...heights) - Math.min(...heights)).toBeLessThanOrEqual(1);

    const metrics = await rail.evaluate(element => ({
      clientWidth: element.clientWidth,
      scrollWidth: element.scrollWidth,
      overflowX: getComputedStyle(element).overflowX,
    }));
    expect(metrics.scrollWidth).toBeGreaterThan(metrics.clientWidth + 20);
    expect(['auto', 'scroll']).toContain(metrics.overflowX);

    const ratio = widths[0] / metrics.clientWidth;
    if (viewport.width === 390) {
      expect(ratio).toBeGreaterThan(0.78);
      expect(ratio).toBeLessThan(0.86);
      await expect(page.getByRole('button', { name: 'Previous local stores' })).toBeHidden();
    } else {
      expect(ratio).toBeGreaterThan(0.22);
      expect(ratio).toBeLessThan(0.33);
      await expect(page.getByRole('button', { name: 'Previous local stores' })).toBeVisible();
    }

    const pageOverflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(pageOverflow).toBeLessThanOrEqual(1);

    await expect(cards.nth(0).getByRole('heading', { name: 'Goutam Shoes' })).toBeVisible();
    await expect(cards.nth(1).getByRole('heading', { name: /Nakoda Imitation Jewellery/ })).toBeVisible();
    await expect(page.locator('a[href="/stores"]').filter({ hasText: 'View All' })).toBeVisible();

    if (viewport.width === 1366) {
      const before = await rail.evaluate(element => element.scrollLeft);
      await page.getByRole('button', { name: 'Next local stores' }).click();
      await expect.poll(() => rail.evaluate(element => element.scrollLeft)).toBeGreaterThan(before + 10);
    }
  }
});
