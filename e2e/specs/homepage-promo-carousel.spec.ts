import { expect, test } from '@playwright/test';

test('replaces the large black hero with horizontal promotional cards', async ({ page }) => {
  await page.goto('/');
  const carousel = page.getByTestId('homepage-promo-carousel');
  const rail = page.getByTestId('homepage-promo-rail');

  await expect(carousel).toBeVisible();
  await expect(page.getByTestId('homepage-promo-slide')).toHaveCount(6);
  await expect(page.getByText('Your look,', { exact: true })).toHaveCount(0);
  await expect(carousel.getByRole('link', { name: 'Explore Your city. Your style.' })).toHaveAttribute('href', '/stores');

  const geometry = await rail.evaluate(element => ({
    scrollWidth: element.scrollWidth,
    clientWidth: element.clientWidth,
    viewportOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
  }));
  expect(geometry.scrollWidth).toBeGreaterThan(geometry.clientWidth);
  expect(geometry.viewportOverflow).toBe(false);
});

test('pagination moves cards and updates the active indicator', async ({ page }) => {
  await page.goto('/');
  const controls = page.getByRole('button', { name: /Show promotion 4: / });
  await controls.click();
  await expect(controls).toHaveAttribute('aria-current', 'true');
  await expect.poll(async () => page.getByTestId('homepage-promo-rail').evaluate(element => element.scrollLeft)).toBeGreaterThan(0);
});

test('carousel advances automatically when motion is allowed', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  await page.goto('/');
  await expect(page.getByRole('button', { name: /Show promotion 1: / })).toHaveAttribute('aria-current', 'true');
  await expect(page.getByRole('button', { name: /Show promotion 2: / })).toHaveAttribute('aria-current', 'true', { timeout: 8000 });
});

test('respects the reduced-motion setting', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/');
  await expect(page.getByRole('button', { name: /Show promotion 1: / })).toHaveAttribute('aria-current', 'true');
  await page.waitForTimeout(4800);
  await expect(page.getByRole('button', { name: /Show promotion 1: / })).toHaveAttribute('aria-current', 'true');
});
