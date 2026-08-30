import { expect, test } from '@playwright/test';

test('location checker uses server-authoritative serviceability', async ({
  page,
}) => {
  await page.goto('/');

  await page
    .getByRole('button', { name: /Deliver to:/ })
    .click();

  const input = page.getByPlaceholder('e.g. 458441');

  await input.fill('458441');
  await page.getByRole('button', { name: 'Check' }).click();

  await expect(
    page.getByText('Serviceable in Neemuch'),
  ).toBeVisible();

  await input.fill('458440');
  await page.getByRole('button', { name: 'Check' }).click();

  await expect(
    page.getByText('Pincode Currently Unserviceable'),
  ).toBeVisible();
});

test('location checker fails closed if API is unavailable', async ({
  page,
}) => {
  await page.route('**/api/serviceability*', route => route.abort());

  await page.goto('/');

  await page
    .getByRole('button', { name: /Deliver to:/ })
    .click();

  await page.getByPlaceholder('e.g. 458441').fill('458441');
  await page.getByRole('button', { name: 'Check' }).click();

  await expect(
    page.getByText('Could Not Check Availability'),
  ).toBeVisible();
});
