import { expect, test } from '@playwright/test';

const routes = [
  '/',
  '/products',
  '/categories',
  '/stores',
  '/wishlist',
  '/help',
  '/returns',
  '/privacy',
  '/terms',
];

for (const route of routes) {
  test(`public route ${route} renders`, async ({ page }) => {
    const response = await page.goto(route);

    expect(response?.ok()).toBeTruthy();

    await expect(page.locator('main')).toBeVisible();
    await expect(
      page.getByRole('heading', { name: 'Page Not Found' }),
    ).toHaveCount(0);
  });
}

test('vibe4you wordmark and tagline are visible', async ({ page }) => {
  await page.goto('/');
  const homeLink = page.getByRole('link', { name: 'vibe4you home' });
  await expect(homeLink).toBeVisible();
  await expect(homeLink.locator('svg[aria-label="Vibe4You"]')).toBeVisible();
  await expect(page.getByText('Your City. Your Shops. Your Style.', { exact: true }).first()).toBeVisible();
  await expect(page.locator('header')).not.toContainText('StyleDash');
  await expect(page).not.toHaveTitle(/StyleDash/i);
});

test('favicon uses the interlocked 44 mark', async ({ request }) => {
  const response = await request.get('/favicon.svg');
  const favicon = await response.text();
  expect(response.ok()).toBeTruthy();
  expect(favicon).toContain('Vibe4You black and gray interlocked 44');
  expect(favicon).toContain('#171717');
  expect(favicon).toContain('#aaa8a5');
  expect(favicon).not.toContain('V4Y');
  expect(favicon).not.toContain('SD');
});

test('customer policy pages publish launch contacts without pre-live warnings', async ({
  page,
}) => {
  const warningPhrases = [
    'Support contact pending',
    'Policy decision required',
    'Business details required',
    'Legal review required',
    'before Live Mode',
  ];

  for (const route of ['/help', '/returns', '/privacy', '/terms']) {
    await page.goto(route);

    const main = page.locator('main');
    await expect(main).toContainText('styledashsupport@gmail.com');

    for (const warning of warningPhrases) {
      await expect(main).not.toContainText(warning);
    }
  }

  await page.goto('/help');
  await expect(page.locator('main')).toContainText('+91 8963942394');
  await expect(page.locator('main')).toContainText('Grievance officer: Mohit Jangde');

  await page.goto('/returns');
  await expect(page.locator('main')).toContainText('7-day size exchange');
  await expect(page.locator('main')).toContainText('INR 50');

  await page.goto('/privacy');
  await expect(page.locator('main')).toContainText('Mohit Jangde');
});

test('unknown route renders Vibe4You 404', async ({ page }) => {
  await page.goto('/this-route-must-not-exist-e2e');

  await expect(
    page.getByRole('heading', { name: '404', exact: true }),
  ).toBeVisible();

  await expect(
    page.getByRole('heading', { name: 'Page Not Found' }),
  ).toBeVisible();
});

test('restricted payment product fails closed for anonymous visitor', async ({
  page,
}) => {
  const response = await page.goto(
    '/payment-test/styledash-payment-test-item',
  );

  expect(response).not.toBeNull();
  expect(response!.status()).toBe(404);

  const payload = await response!.json();

  expect(payload).toEqual({
    success: false,
    error: 'Not found.',
    code: 'not_found',
  });

  // The denial must not reveal the hidden product or authorization rules.
  await expect(page.locator('body')).not.toContainText(
    'Vibe4You Payment Test Item',
  );
  await expect(page.locator('body')).not.toContainText(
    'e2e-owner@example.test',
  );
  await expect(page.locator('body')).not.toContainText(
    'mailbox',
  );
});

test('category subcategory links apply the selected filters', async ({ page }) => {
  await page.goto('/categories');
  await page.getByRole('link', { name: 'Oversized', exact: true }).click();

  await expect(page).toHaveURL(/dept=men/);
  await expect(page).toHaveURL(/category=T-Shirts/);
  await expect(page).toHaveURL(/subcategory=Oversized/);
  await expect(page.getByRole('heading', { name: 'Pure Cotton Oversized Graphic Tee' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Textured Linen Spread Collar Shirt' })).toHaveCount(0);
});

test('header uses category queries for Footwear and Accessories', async ({ page }) => {
  await page.goto('/');
  const header = page.locator('header');
  await expect(header.getByRole('link', { name: 'FOOTWEAR', exact: true })).toHaveAttribute('href', '/products?category=Footwear');
  await expect(header.getByRole('link', { name: 'ACCESSORIES', exact: true })).toHaveAttribute('href', '/products?category=Accessories');
});

test('weekday Weekend Express request keeps normal catalogue visible', async ({ page }) => {
  await page.clock.setFixedTime(new Date('2026-08-31T06:00:00Z'));
  await page.goto('/products?filter=express');
  await expect(page.getByText('Weekend Express is available Saturday and Sunday.')).toBeVisible();
  await expect(page.getByText('No matching products found')).toHaveCount(0);
  await expect(page.locator('main').getByRole('heading', { level: 3 }).first()).toBeVisible();
});

test('weekend Weekend Express request applies express product filtering', async ({ page }) => {
  await page.clock.setFixedTime(new Date('2026-08-29T06:00:00Z'));
  await page.goto('/products?filter=express');
  await expect(page.getByText('Weekend Express is available Saturday and Sunday.')).toHaveCount(0);
  await expect(page.getByRole('heading', { name: 'Pure Cotton Oversized Graphic Tee' })).toBeVisible();
});

test('global search returns matching local stores', async ({ page }) => {
  await page.route('**/api/stores/active', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ success: true, stores: [
      {
        id: 'store-royals', slug: 'royals', storeName: 'royals', category: 'Clothing & Fashion',
        address: 'Neemuch', pincode: '458441', city: 'Neemuch', deliveryMinutes: 60,
        description: 'Local fashion store', active: true, approved: true, createdAt: '2026-01-01T00:00:00Z'
      },
      {
        id: 'store-inactive', slug: 'inactive-royals', storeName: 'Inactive Royals', category: 'Clothing & Fashion',
        address: 'Neemuch', pincode: '458441', city: 'Neemuch', deliveryMinutes: 60,
        description: 'Inactive local fashion store', active: false, approved: true, createdAt: '2026-01-01T00:00:00Z'
      },
      {
        id: 'store-unapproved', slug: 'unapproved-royals', storeName: 'Unapproved Royals', category: 'Clothing & Fashion',
        address: 'Neemuch', pincode: '458441', city: 'Neemuch', deliveryMinutes: 60,
        description: 'Unapproved local fashion store', active: true, approved: false, createdAt: '2026-01-01T00:00:00Z'
      },
    ] }),
  }));

  await page.goto('/');
  const search = page.locator('header input[aria-label="Search products, brands, or local Neemuch stores"]:visible');
  await search.fill('royals');
  await search.press('Enter');

  await expect(page).toHaveURL(/products\?search=royals/);
  await expect(page.getByRole('heading', { name: 'Matching Local Stores' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'royals', exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Visit royals storefront' })).toHaveAttribute('href', '/store/royals');
  await expect(page.getByRole('heading', { name: 'Inactive Royals', exact: true })).toHaveCount(0);
  await expect(page.getByRole('heading', { name: 'Unapproved Royals', exact: true })).toHaveCount(0);
});

test('catalogue browsing does not fetch active stores without search', async ({ page }) => {
  let activeStoreRequests = 0;
  page.on('request', request => {
    if (new URL(request.url()).pathname === '/api/stores/active') {
      activeStoreRequests += 1;
    }
  });

  await page.goto('/products?dept=men&sort=price-asc');
  await page.waitForLoadState('networkidle');

  expect(activeStoreRequests).toBe(0);
});

test('wishlist icon buttons expose accessible names', async ({ page }) => {
  await page.goto('/');

  await expect(
    page.getByRole('button', { name: 'Add Pure Cotton Oversized Graphic Tee to wishlist' }).first(),
  ).toBeVisible();
});

test('public SEO exposes canonical and social metadata without query duplication', async ({ page }) => {
  await page.goto('/products?dept=men&sort=price-asc');

  await expect(page.locator('link[rel="canonical"]')).toHaveAttribute('href', 'https://vibe4you.in/products');
  await expect(page.locator('meta[property="og:url"]')).toHaveAttribute('content', 'https://vibe4you.in/products');
  await expect(page.locator('meta[property="og:title"]')).toHaveAttribute('content', /Vibe4You/);
  await expect(page.locator('meta[name="twitter:card"]')).toHaveAttribute('content', 'summary');
});

test('product detail exposes product social metadata and structured data', async ({ page }) => {
  await page.goto('/product/pure-cotton-oversized-graphic-tee-sd-prod-001');

  await expect(page.locator('meta[property="og:type"]')).toHaveAttribute('content', 'product');
  await expect(page.locator('meta[property="og:image"]')).toHaveAttribute('content', /^https:\/\//);
  const jsonLd = JSON.parse(await page.locator('#styledash-seo-jsonld').textContent() || '{}');
  expect(jsonLd['@type']).toBe('Product');
  expect(jsonLd.name).toBe('Pure Cotton Oversized Graphic Tee');
  expect(jsonLd.offers.priceCurrency).toBe('INR');
  expect(jsonLd.aggregateRating).toBeUndefined();
});

test('robots and sitemap expose only intended public discovery metadata', async ({ request }) => {
  const robots = await request.get('/robots.txt');
  expect(robots.ok()).toBeTruthy();
  expect(await robots.text()).toContain('Sitemap:');

  const sitemap = await request.get('/sitemap.xml');
  expect(sitemap.ok()).toBeTruthy();
  const xml = await sitemap.text();
  expect(xml).toContain('/product/pure-cotton-oversized-graphic-tee-sd-prod-001');
  expect(xml).not.toContain('/admin');
  expect(xml).not.toContain('/api/');
  expect(xml).not.toContain('/profile');
  expect(xml).not.toContain('/checkout');
});

test('header omits delivery-area controls while Neemuch serviceability remains available', async ({ page, request }) => {
  await page.goto('/');

  await expect(page.getByRole('button', { name: /Check delivery availability/ })).toHaveCount(0);
  await expect(page.getByText(/Deliver to Neemuch \(458441\).*Check area/i)).toHaveCount(0);
  await expect(page.getByText(/Deliver to:\s*Neemuch \(458441\)/i)).toHaveCount(0);

  const response = await request.get('/api/serviceability?pincode=458441');
  expect(response.status()).toBe(200);
  expect(await response.json()).toMatchObject({ serviceable: true, pincode: '458441', city: 'Neemuch' });
});
