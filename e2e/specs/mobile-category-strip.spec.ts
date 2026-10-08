import { expect, test } from '@playwright/test';

test('mobile category strip stays compact, swipes, and navigates to groceries and watches', async ({ page }, testInfo) => {
  test.skip(!testInfo.project.name.includes('mobile'), 'mobile-only category strip');
  await page.goto('/');
  const nav = page.getByRole('navigation', { name: 'Browse departments' });
  await expect(nav).toBeVisible();
  const links = nav.locator('a');
  await expect(links).toHaveCount(8);
  await expect(links.nth(6)).toHaveAttribute('href', '/products?category=Groceries');
  await expect(links.nth(7)).toHaveAttribute('href', '/products?search=watch');

  const firstCircle = links.first().locator('span').first();
  await expect(firstCircle).toBeVisible();
  const circle = await firstCircle.boundingBox();
  expect(circle?.width).toBe(40);
  expect(circle?.height).toBe(40);

  const rail = nav.locator('div').first();
  const size = await rail.evaluate(element => ({
    scrollWidth: element.scrollWidth,
    clientWidth: element.clientWidth,
  }));
  expect(size.scrollWidth).toBeGreaterThan(size.clientWidth);
  await rail.evaluate(element => { element.scrollLeft = element.scrollWidth; });
  await expect.poll(() => rail.evaluate(element => element.scrollLeft)).toBeGreaterThan(0);
  await links.nth(7).click();
  await expect(page).toHaveURL(/\/products\?search=watch$/);
});
