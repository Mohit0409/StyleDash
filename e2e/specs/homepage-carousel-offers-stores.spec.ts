import { expect, test } from '@playwright/test';

test('new promotional cards replace the men, women and footwear banners', async ({ page }) => {
  await page.goto('/');
  const rail = page.getByTestId('homepage-promo-rail');
  const cards = rail.getByTestId('homepage-promo-slide');
  await expect(cards).toHaveCount(6);

  const destinations = [
    '/stores',
    '/categories',
    '/offers',
    '/stores?sort=newest',
    '/products?category=Beauty%20%26%20Personal%20Care',
    '/products?maxPrice=499',
  ];
  for (let index = 0; index < destinations.length; index += 1) {
    await expect(cards.nth(index)).toHaveAttribute('href', destinations[index]);
  }
  await expect(rail.getByText("MEN'S FASHION")).toHaveCount(0);
  await expect(rail.getByText("WOMEN'S FASHION")).toHaveCount(0);
  await expect(rail.getByText('FOOTWEAR PICKS')).toHaveCount(0);

  const controls = page.locator('[aria-label="Carousel navigation"]');
  await expect(controls).toBeHidden();
});

test('offers card opens the three independent discount selections', async ({ page }) => {
  await page.goto('/');
  const offersCard = page.getByTestId('homepage-promo-slide').nth(2);
  await offersCard.click();
  await expect(page).toHaveURL(/\/offers$/);
  await expect(page.getByTestId('offers-page')).toBeVisible();
  await expect(page.getByRole('heading', { level: 2, name: "Today's Top Offers" })).toBeVisible();
  await expect(page.getByRole('heading', { level: 2, name: 'Weekly Top Offers' })).toBeVisible();
  await expect(page.getByRole('heading', { level: 2, name: 'Monthly Top Offers' })).toBeVisible();
  await expect(page.getByText(/not time-limited promotions/i)).toBeVisible();
  await expect(page.getByRole('link', { name: 'View all products' })).toHaveAttribute('href', '/products');
});

test('newly added shops card orders approved active stores newest first', async ({ page }) => {
  const store = (slug: string, date: string, approved = true, active = true) => ({
    id: slug,
    slug,
    storeName: slug,
    category: 'Fashion',
    address: 'Neemuch',
    pincode: '458441',
    city: 'Neemuch',
    deliveryMinutes: 60,
    description: 'Local store in Neemuch',
    approved,
    active,
    createdAt: date,
    productCount: slug === 'Old Store' ? 200 : 1,
  });
  await page.route('**/api/stores/active', async route => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        stores: [
          store('Old Store', '2026-09-01T00:00:00Z'),
          store('Newest Store', '2026-10-12T10:00:00Z'),
          store('Middle Store', '2026-10-10T10:00:00Z'),
          store('Unapproved Store', '2026-10-12T12:00:00Z', false),
          store('Inactive Store', '2026-10-12T13:00:00Z', true, false),
        ],
      }),
    });
  });

  await page.goto('/');
  await page.getByTestId('homepage-promo-slide').nth(3).click();
  await expect(page).toHaveURL(/\/stores\?sort=newest$/);
  await expect(page.getByRole('heading', { level: 1, name: /Newly Added Shops in Neemuch/ })).toBeVisible();
  const names = page.locator('.grid h3');
  await expect(names).toHaveCount(3);
  await expect(names.nth(0)).toHaveText('Newest Store');
  await expect(names.nth(1)).toHaveText('Middle Store');
  await expect(names.nth(2)).toHaveText('Old Store');

  await page.getByRole('link', { name: 'Popular stores' }).click();
  await expect(page).toHaveURL(/\/stores$/);
  await expect(names.nth(0)).toHaveText('Old Store');
});
