import { expect, test } from '@playwright/test';

test('replaces the large black hero with horizontal promotional cards', async ({ page }) => {
  await page.goto('/');
  const carousel = page.getByTestId('homepage-promo-carousel');
  const rail = page.getByTestId('homepage-promo-rail');

  await expect(carousel).toBeVisible();
  await expect(page.getByRole('heading', { level: 1, name: 'Featured for you' })).toBeVisible();
  await expect(page.getByTestId('homepage-promo-slide')).toHaveCount(6);
  await expect(page.getByText('Your look,', { exact: true })).toHaveCount(0);
  await expect(carousel.getByRole('link', { name: 'Explore Your city. Your style.' })).toHaveAttribute('href', '/stores');

  const geometry = await rail.evaluate(element => ({
    scrollWidth: element.scrollWidth,
    clientWidth: element.clientWidth,
    cardWidth: element.querySelector('[data-promo-slide]')?.getBoundingClientRect().width ?? 0,
    snapType: getComputedStyle(element).scrollSnapType,
    viewportOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
  }));
  expect(geometry.scrollWidth).toBeGreaterThan(geometry.clientWidth);
  expect(geometry.cardWidth / geometry.clientWidth).toBeGreaterThan(0.65);
  expect(geometry.snapType).toContain('x');
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

test('keeps all promotional buttons visible on 320px phones', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 568 });
  await page.goto('/');
  const rail = page.getByTestId('homepage-promo-rail');
  await expect(rail).toBeVisible();

  const cards = await rail.evaluate(element =>
    Array.from(element.querySelectorAll<HTMLElement>('[data-promo-slide]')).map(card => {
      const cta = card.querySelector<HTMLElement>('div:nth-of-type(2) > span:last-child');
      const heading = card.querySelector<HTMLElement>('h3');
      return {
        bottom: card.getBoundingClientRect().bottom,
        ctaBottom: cta?.getBoundingClientRect().bottom ?? Infinity,
        headingBottom: heading?.getBoundingClientRect().bottom ?? Infinity,
      };
    }),
  );

  expect(cards).toHaveLength(6);
  for (const card of cards) {
    expect(card.ctaBottom).toBeLessThanOrEqual(card.bottom - 4);
    expect(card.headingBottom).toBeLessThanOrEqual(card.bottom - 4);
  }
  const documentOverflows = await page.evaluate(
    () => document.documentElement.scrollWidth > window.innerWidth,
  );
  expect(documentOverflows).toBe(false);
});