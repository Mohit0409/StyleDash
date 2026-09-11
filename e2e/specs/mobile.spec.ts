import { expect, test } from '@playwright/test';

test('mobile homepage and search work', async ({ page }) => {
  await page.goto('/');

  await expect(
    page.getByRole('heading', { name: /Your look/i }),
  ).toBeVisible();

  const search = page.locator('header input[aria-label="Search products, brands, or local Neemuch stores"]:visible');

  await search.fill('shirt');
  await search.press('Enter');

  await expect(page).toHaveURL(/\/products\?search=shirt$/);

  await expect(page.locator('main')).toBeVisible();
});

test('mobile legal and support routes render without 404', async ({
  page,
}) => {
  for (const route of ['/help', '/privacy', '/terms', '/returns']) {
    await page.goto(route);

    await expect(
      page.getByRole('heading', { name: 'Page Not Found' }),
    ).toHaveCount(0);
  }
});


test('mobile header omits the delivery checker while Neemuch remains serviceable', async ({ page, request }) => {
  await page.goto('/');

  await expect(
    page.getByRole('button', { name: /Check delivery availability/ }),
  ).toHaveCount(0);
  await expect(
    page.getByText(/Deliver to Neemuch \(458441\).*Check area/i),
  ).toHaveCount(0);

  const response = await request.get('/api/serviceability?pincode=458441');
  expect(response.status()).toBe(200);
  await expect(response).toBeOK();
  expect(await response.json()).toMatchObject({
    success: true,
    pincode: '458441',
    serviceable: true,
    city: 'Neemuch',
  });
});
