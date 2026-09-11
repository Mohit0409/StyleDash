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


test('mobile same account cart and wishlist sync across isolated browser contexts', async ({ browser, request }) => {
  const email = 'e2e-mobile-account-sync@example.test';
  const password = 'E2E-mobile-account-sync-2026!';
  const registered = await request.post('/api/auth/register', { data: {
    name: 'E2E Mobile Sync Customer', email, phone: '9876543499', password,
    termsAccepted: true, termsVersion: '2026-08-14',
  }});
  expect(registered.status()).toBe(201);

  const contextA = await browser.newContext();
  const contextB = await browser.newContext();
  const pageA = await contextA.newPage();
  const pageB = await contextB.newPage();
  const login = async (page: typeof pageA) => {
    await page.goto('/login');
    await page.getByPlaceholder('Email').fill(email);
    await page.getByPlaceholder('Password (8+ characters)').fill(password);
    await page.getByRole('checkbox', { name: /agree to the terms/i }).check();
    await page.getByRole('button', { name: 'Login' }).click();
    await expect(page).toHaveURL(/\/profile$/);
  };
  try {
    await login(pageA);
    await pageA.goto('/product/pure-cotton-oversized-graphic-tee-sd-prod-001');
    const cartSaved = pageA.waitForResponse(r => r.url().endsWith('/api/account-state/cart') && r.request().method() === 'PATCH' && r.status() === 200);
    await pageA.getByRole('button', { name: /Add to Cart/ }).click();
    await cartSaved;
    const wishlistSaved = pageA.waitForResponse(r => r.url().endsWith('/api/account-state/wishlist') && r.request().method() === 'PATCH' && r.status() === 200);
    await pageA.locator('div.flex.gap-4.pt-4').getByRole('button').last().click();
    await wishlistSaved;

    await login(pageB);
    await pageB.goto('/wishlist');
    await expect(pageB.getByRole('heading', { name: 'Saved Wishlist (1)' })).toBeVisible();
    await expect(pageB.getByText('Pure Cotton Oversized Graphic Tee', { exact: true })).toBeVisible();
    await pageB.goto('/product/pure-cotton-oversized-graphic-tee-sd-prod-001');
    await expect(pageB.getByRole('button', { name: /^Cart\s+\d+$/ })).toContainText('1');
    await pageB.getByRole('button', { name: /^Cart\s+\d+$/ }).click();
    await expect(pageB.getByRole('dialog', { name: 'Your Cart' }).getByText('Pure Cotton Oversized Graphic Tee', { exact: true })).toBeVisible();
  } finally {
    await contextA.close();
    await contextB.close();
  }
});
