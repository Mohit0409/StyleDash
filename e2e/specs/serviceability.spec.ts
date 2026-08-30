import { expect, test } from '@playwright/test';

test('serviceability API remains authoritative for Neemuch and unsupported pincodes', async ({ request }) => {
  const neemuch = await request.get('/api/serviceability?pincode=458441');
  expect(neemuch.status()).toBe(200);
  expect(await neemuch.json()).toMatchObject({
    success: true,
    pincode: '458441',
    serviceable: true,
    city: 'Neemuch',
  });

  const unsupported = await request.get('/api/serviceability?pincode=458440');
  expect(unsupported.status()).toBe(200);
  expect(await unsupported.json()).toMatchObject({
    success: true,
    pincode: '458440',
    serviceable: false,
  });
});

test('shopping header no longer depends on the delivery checker UI', async ({ page }) => {
  await page.route('**/api/serviceability*', route => route.abort());
  await page.goto('/');

  await expect(page.getByRole('heading', { name: /Your look/i })).toBeVisible();
  await expect(page.getByRole('button', { name: /Deliver to:/ })).toHaveCount(0);
  await expect(page.getByRole('button', { name: /Check delivery availability/ })).toHaveCount(0);
  await expect(page.getByText(/Deliver to Neemuch \(458441\).*Check area/i)).toHaveCount(0);
});
