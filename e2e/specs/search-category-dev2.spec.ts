import { expect, test, type Page } from '@playwright/test';

const visibleSearch = (page: Page) =>
  page.locator('header input[aria-label="Search products, brands, or local Neemuch stores"]:visible');

test('homepage category cards use canonical catalogue queries', async ({ page }) => {
  await page.goto('/');

  const departmentSection = page.locator('section').filter({
    has: page.getByRole('heading', { name: 'Shop by Department' }),
  });
  await expect(departmentSection.getByRole('link', { name: /Men's Fashion/ })).toHaveAttribute('href', '/products?dept=men');
  await expect(departmentSection.getByRole('link', { name: /Women's Fashion/ })).toHaveAttribute('href', '/products?dept=women');
  await expect(departmentSection.getByRole('link', { name: /Kids Wear/ })).toHaveAttribute('href', '/products?dept=kids');
  await expect(departmentSection.getByRole('link', { name: /Footwear/ })).toHaveAttribute('href', '/products?category=Footwear');
  const accessoriesCard = departmentSection.getByRole('link', { name: /Accessories/ });
  await expect(accessoriesCard).toHaveAttribute('href', '/products?category=Accessories');
  await expect(accessoriesCard.locator('img')).toHaveAttribute('src', /photo-1515562141207-7a88fb7ce338/);
  await expect(departmentSection.getByRole('link', { name: /Beauty & Personal Care/ })).toHaveAttribute(
    'href',
    '/products?category=Beauty%20%26%20Personal%20Care',
  );
});

test('search suggestions debounce data loads and support keyboard navigation', async ({ page }) => {
  let productRequests = 0;
  let storeRequests = 0;
  page.on('request', request => {
    const path = new URL(request.url()).pathname;
    if (path === '/api/shop-products/published') productRequests += 1;
    if (path === '/api/stores/active') storeRequests += 1;
  });

  await page.goto('/');
  await page.waitForLoadState('networkidle');
  productRequests = 0;
  storeRequests = 0;

  const search = visibleSearch(page);
  await search.fill('Pure Cotton');
  const suggestions = page.getByRole('listbox', { name: 'Search suggestions' });
  await expect(suggestions).toBeVisible();
  await expect(suggestions.getByRole('option').first()).toBeVisible();

  await search.press('ArrowDown');
  await search.press('Enter');
  await expect(page).toHaveURL(/\/product\//);
  expect(productRequests).toBeLessThanOrEqual(1);
  expect(storeRequests).toBeLessThanOrEqual(1);
});

test('search keeps the normal full-results fallback when suggestions miss', async ({ page }) => {
  await page.goto('/');

  const search = visibleSearch(page);
  await search.fill('zzzzzzq');
  const suggestions = page.getByRole('listbox', { name: 'Search suggestions' });
  await expect(suggestions).toBeVisible();
  await expect(suggestions.getByText('No suggestions found')).toBeVisible();

  await search.press('Enter');
  await expect(page).toHaveURL(/\/products\?search=zzzzzzq$/);
  await expect(page.locator('main')).toBeVisible();
});

test('empty Beauty category stays selected instead of falling back to unrelated products', async ({ page }) => {
  await page.goto('/products?category=Beauty%20%26%20Personal%20Care');

  await expect(page.getByRole('heading', { name: 'Beauty & Personal Care Catalogue' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'No matching products found' })).toBeVisible();
  expect(new URL(page.url()).searchParams.get('category')).toBe('Beauty & Personal Care');
});
