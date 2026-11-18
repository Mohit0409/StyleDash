import { expect, test } from '@playwright/test';

const drawerViewports = [
  { width: 390, height: 844 },
  { width: 768, height: 1024 },
];

test('mobile filter drawer closes on outside click without closing for filter interactions', async ({ page }) => {
  for (const viewport of drawerViewports) {
    await page.setViewportSize(viewport);
    await page.goto('/products');

    await page.getByRole('button', { name: 'Filter & Sort', exact: true }).click();
    const dialog = page.getByRole('dialog', { name: 'Filter & Sort' });
    await expect(dialog).toBeVisible();
    await expect(page.getByTestId('mobile-filter-backdrop')).toBeVisible();
    expect(await page.evaluate(() => document.body.style.overflow)).toBe('hidden');

    const apply = dialog.getByRole('button', { name: 'Apply Filters', exact: true });
    await expect(apply).toBeVisible();
    const applyBox = await apply.boundingBox();
    expect(applyBox).not.toBeNull();
    expect(applyBox!.y + applyBox!.height).toBeLessThanOrEqual(viewport.height);

    await dialog.getByRole('button', { name: 'men', exact: true }).click();
    await expect(dialog).toBeVisible();
    await expect(apply).toBeVisible();

    await page.mouse.click(viewport.width - 8, Math.min(300, viewport.height - 8));
    await expect(dialog).toHaveCount(0);
    expect(await page.evaluate(() => document.body.style.overflow)).toBe('');
  }
});
