import { expect, test } from '@playwright/test';

test('Back closes the cart drawer before leaving the current page', async ({ page }) => {
  await page.goto('/');

  await page.getByRole('button', { name: /^Cart\s+\d+$/ }).click();
  await expect(page.getByRole('dialog', { name: 'Your Cart' })).toBeVisible();

  await page.goBack();

  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole('dialog', { name: 'Your Cart' })).toHaveCount(0);
});

test('initial home Back asks for a second press before exit', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('button', { name: /^Cart\s+\d+$/ })).toBeVisible();

  await page.goBack();

  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByText('Press back again to exit')).toBeVisible();
});

test('home discovery exposes categories, budget tiers, and Top Picks', async ({ page }) => {
  await page.goto('/');

  await expect(page.getByRole('link', { name: /Categories/ }).first()).toHaveAttribute('href', '/categories');
  await expect(page.getByRole('heading', { name: 'Shop by Budget' })).toBeVisible();
  await expect(page.getByRole('link', { name: /Under\s*₹199/ })).toHaveAttribute('href', '/products?maxPrice=199');
  await expect(page.getByRole('link', { name: /Under\s*₹299/ })).toHaveAttribute('href', '/products?maxPrice=299');
  await expect(page.getByRole('link', { name: /Under\s*₹499/ }).first()).toHaveAttribute('href', '/products?maxPrice=499');
  await expect(page.getByRole('heading', { name: 'Top Picks' })).toBeVisible();
});

test('supported browsers can search by voice and retain typed search as a fallback', async ({ page }) => {
  await page.addInitScript(() => {
    class TestSpeechRecognition {
      lang = '';
      continuous = false;
      interimResults = false;
      onresult: ((event: { results: [[{ transcript: string }]] }) => void) | null = null;
      onerror: (() => void) | null = null;
      onend: (() => void) | null = null;

      start() {
        this.onresult?.({ results: [[{ transcript: 'running shoes' }]] });
        this.onend?.();
      }
    }

    Object.defineProperty(window, 'SpeechRecognition', {
      configurable: true,
      value: TestSpeechRecognition,
    });
  });

  await page.goto('/');
  await page.locator('button[aria-label="Speak to search"]:visible').click();

  await expect(page).toHaveURL(/\/products\?search=running%20shoes$/);
});
