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

  await expect(page.getByRole('link', { name: 'vibe4you home' })).toBeVisible();
  await expect(page.getByText('Your City. Your Shops. Your Style.', { exact: true }).first()).toBeVisible();
  await expect(page.locator('header')).not.toContainText('StyleDash');
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
  await expect(page.locator('main')).toContainText('Grievance officer: Swapnil');

  await page.goto('/returns');
  await expect(page.locator('main')).toContainText('7-day size exchange');
  await expect(page.locator('main')).toContainText('INR 50');

  await page.goto('/privacy');
  await expect(page.locator('main')).toContainText('Mohit Jangd');
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

test('wishlist icon buttons expose accessible names', async ({ page }) => {
  await page.goto('/');

  await expect(
    page.getByRole('button', { name: 'Add Pure Cotton Oversized Graphic Tee to wishlist' }).first(),
  ).toBeVisible();
});

test('public SEO exposes canonical and social metadata without query duplication', async ({ page }) => {
  await page.goto('/products?dept=men&sort=price-asc');

  await expect(page.locator('link[rel="canonical"]')).toHaveAttribute('href', /\/products$/);
  await expect(page.locator('meta[property="og:url"]')).toHaveAttribute('content', /\/products$/);
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
