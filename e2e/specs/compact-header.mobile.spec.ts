import { expect, test } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: /Your look/i })).toBeVisible();
  const consent = page.getByRole('button', { name: 'Only necessary', exact: true });
  if (await consent.isVisible()) await consent.click();
});

test('compact photo categories fit mobile widths and retain their routes', async ({ page }) => {
  const header = page.locator('header');
  const categories = header.getByRole('navigation', { name: 'Browse departments' });
  await expect(categories.getByRole('link')).toHaveCount(6);
  await expect(categories.getByRole('link', { name: 'Women', exact: true })).toHaveAttribute('href', '/products?dept=women');
  await expect(categories.getByRole('link', { name: 'Kids', exact: true })).toHaveAttribute('href', '/products?dept=kids');
  await expect(categories.getByRole('link', { name: 'Beauty', exact: true })).toHaveAttribute('href', '/products?category=Beauty%20%26%20Personal%20Care');

  const artwork = await categories.locator('a span[aria-hidden]').first().evaluate(el => getComputedStyle(el).backgroundImage);
  const artworkUrl = artwork.match(/url\("?([^ ")]+)"?\)/)?.[1];
  expect(artworkUrl).toBeTruthy();
  expect((await page.request.get(artworkUrl!)).ok()).toBeTruthy();
  await expect(categories.locator('svg')).toHaveCount(0);

  for (const width of [320, 390, 430, 767]) {
    await page.setViewportSize({ width, height: 844 });
    expect((await header.boundingBox())?.height).toBe(154);
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(width);
    for (const name of ['Search products', 'Open menu']) {
      const bounds = await header.getByRole('button', { name, exact: true }).boundingBox();
      expect(bounds?.width).toBeGreaterThanOrEqual(44);
      expect(bounds?.height).toBeGreaterThanOrEqual(44);
      expect((bounds?.x ?? 0) + (bounds?.width ?? 0)).toBeLessThanOrEqual(width);
    }
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: 'test-results/compact-header-expanded.png' });
  await page.locator('.mobile-header-shell').screenshot({ path: 'test-results/compact-header-preview.png', scale: 'css' });
  await categories.getByRole('link', { name: 'Women', exact: true }).click();
  await expect(page).toHaveURL(/\/products\?dept=women$/);
});

test('collapse animates without shifting content or bouncing at the threshold', async ({ page }) => {
  const header = page.locator('header');
  const samples = await page.evaluate(async () => {
    const shell = document.querySelector('.mobile-header-shell')!;
    const main = document.querySelector('main')!;
    const originalMainTop = main.getBoundingClientRect().top + window.scrollY;
    window.scrollTo({ top: 112, behavior: 'instant' });
    const frames: { scroll: number; mainTop: number; height: number }[] = [];
    const start = performance.now();
    await new Promise<void>(resolve => {
      const sample = () => {
        frames.push({ scroll: window.scrollY, mainTop: main.getBoundingClientRect().top + window.scrollY, height: shell.getBoundingClientRect().height });
        if (performance.now() - start >= 400) resolve();
        else requestAnimationFrame(sample);
      };
      requestAnimationFrame(sample);
    });
    return { frames, originalMainTop };
  });
  await expect(header).toHaveAttribute('data-mobile-header-collapsed', 'true');
  expect(samples.frames.every(frame => Math.abs(frame.scroll - 112) <= 1)).toBeTruthy();
  expect(samples.frames.every(frame => Math.abs(frame.mainTop - samples.originalMainTop) <= 1)).toBeTruthy();
  expect(new Set(samples.frames.map(frame => Math.round(frame.height))).size).toBeGreaterThan(2);
  expect(samples.frames.at(-1)?.height).toBeLessThanOrEqual(54);
  await expect(header.getByRole('navigation', { name: 'Browse departments' })).toBeHidden();
  await expect(header.getByRole('button', { name: 'vibe4you home' })).toBeHidden();
  await expect(header.locator('.mobile-header-shell button:visible')).toHaveCount(2);
  await page.screenshot({ path: 'test-results/compact-header-collapsed.png' });
  await page.locator('.mobile-header-shell').screenshot({ path: 'test-results/compact-header-collapsed-preview.png', scale: 'css' });

  for (const y of [103, 106, 95, 64, 33]) {
    await page.evaluate(async top => {
      window.scrollTo({ top, behavior: 'instant' });
      await new Promise(requestAnimationFrame);
      await new Promise(requestAnimationFrame);
    }, y);
    await expect(header).toHaveAttribute('data-mobile-header-collapsed', 'true');
  }
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }));
  await expect(header).toHaveAttribute('data-mobile-header-collapsed', 'false');
  await expect(header.getByRole('button', { name: 'vibe4you home' })).toBeVisible();
  await expect.poll(() => page.evaluate(() => scrollY)).toBe(0);
});

test('collapsed controls work, reduced motion is instant, and desktop restores', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.evaluate(() => window.scrollTo({ top: 500, behavior: 'instant' }));
  const header = page.locator('header');
  await expect(header).toHaveAttribute('data-mobile-header-collapsed', 'true');
  expect(await page.locator('.mobile-header-chrome').evaluate(el => getComputedStyle(el).transitionDuration)).toBe('0s');
  await header.getByRole('button', { name: 'Open menu', exact: true }).click();
  await expect(page.getByRole('navigation', { name: 'Mobile menu', exact: true })).toBeVisible();
  await header.getByRole('button', { name: 'Search products', exact: true }).click();
  await expect(page.getByRole('navigation', { name: 'Mobile menu', exact: true })).toBeHidden();
  const search = header.getByRole('combobox', { name: 'Search products, brands, or local Neemuch stores' });
  await search.fill('shirt');
  await search.press('Enter');
  await expect(page).toHaveURL(/\/products\?search=shirt$/);
  await expect(page.locator('#mobile-header-search')).toBeHidden();
  await expect.poll(async () => {
    const heading = await page.getByRole('heading', { level: 1 }).boundingBox();
    const shell = await page.locator('.mobile-header-shell').boundingBox();
    return (heading?.y ?? 0) - ((shell?.y ?? 0) + (shell?.height ?? 0));
  }).toBeGreaterThanOrEqual(0);

  await page.setViewportSize({ width: 1280, height: 900 });
  await expect(header).toHaveAttribute('data-mobile-header-collapsed', 'false');
  await expect(header.getByRole('navigation', { name: 'Shop navigation' })).toBeVisible();
  await expect(page.locator('.mobile-header-shell')).toBeHidden();
  await expect(page.locator('[data-mobile-bottom-nav]')).toBeHidden();
});

test('bottom navigation closes header overlays even when returning to the same route', async ({ page }) => {
  const header = page.locator('header');
  const bottom = page.locator('[data-mobile-bottom-nav]');
  await header.getByRole('button', { name: 'Search products', exact: true }).click();
  await expect(page.locator('#mobile-header-search')).toBeVisible();
  await bottom.getByRole('link', { name: 'Home', exact: true }).click();
  await expect(page.locator('#mobile-header-search')).toBeHidden();
  await header.getByRole('button', { name: 'Open menu', exact: true }).click();
  await expect(page.locator('#mobile-header-menu')).toBeVisible();
  await bottom.getByRole('link', { name: /^Wishlist/ }).click();
  await expect(page).toHaveURL(/\/wishlist$/);
  await expect(page.locator('#mobile-header-menu')).toBeHidden();
});
