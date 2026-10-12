import { expect, test } from '@playwright/test';

test('catalogue has 24 items per page and preserves the existing sort query', async ({ page }) => {
  await page.goto('/products?sort=price-asc&page=2');
  const grid = page.locator('#catalogue-products');
  const cards = grid.locator('a[data-product-card-image]');
  const pagination = page.getByTestId('catalogue-pagination');
  await expect(pagination).toBeVisible();
  await expect(cards).toHaveCount(24);
  await expect(pagination.getByRole('button', { name: /Page 2 of .* for products/ })).toHaveAttribute('aria-current', 'page');
  await expect(pagination.getByRole('status')).toContainText('Showing 25–48 of');
  const secondPageFirst = await cards.first().getAttribute('href');

  await pagination.getByRole('button', { name: 'Previous products page' }).click();
  await expect(page).toHaveURL(/\/products\?sort=price-asc$/);
  await expect(pagination.getByRole('button', { name: /Page 1 of .* for products/ })).toHaveAttribute('aria-current', 'page');
  const firstPageFirst = await cards.first().getAttribute('href');
  expect(firstPageFirst).not.toBe(secondPageFirst);

  await pagination.getByRole('button', { name: 'Next products page' }).click();
  await expect(page).toHaveURL(/\/products\?sort=price-asc&page=2$/);
  await expect(cards.first()).toHaveAttribute('href', secondPageFirst!);
  await page.goBack();
  await expect(page).toHaveURL(/\/products\?sort=price-asc$/);
});

test('filters and sorting reset to the first page, and deep links clamp safely', async ({ page }) => {
  await page.goto('/products?sort=price-asc&page=999999');
  const paginator = page.getByTestId('catalogue-pagination');
  await expect(paginator).toBeVisible();
  const current = paginator.locator('[aria-current="page"]');
  const last = Number((await current.textContent())?.trim());
  expect(last).toBeGreaterThan(2);
  await expect.poll(() => new URL(page.url()).searchParams.get('page')).toBe(String(last));

  if ((page.viewportSize()?.width ?? 1280) < 1024) {
    await page.getByRole('button', { name: 'Filter & Sort' }).click();
  }
  await page.getByRole('combobox', { name: 'Sort products' }).selectOption('price-desc');
  await expect.poll(() => new URL(page.url()).searchParams.get('page')).toBeNull();
  await expect.poll(() => new URL(page.url()).searchParams.get('sort')).toBe('price-desc');

  await page.goto('/products?search=__no_matching_products_47382__&page=9000');
  await expect(page.getByRole('heading', { name: 'No matching products found' })).toBeVisible();
  await expect(page.getByTestId('catalogue-pagination')).toHaveCount(0);
  await expect.poll(() => new URL(page.url()).searchParams.get('page')).toBeNull();
});

test('each Offers period has its own pagination and retains other period selections', async ({ page }) => {
  await page.goto('/offers');
  const today = page.getByTestId('offers-today-pagination');
  const week = page.getByTestId('offers-week-pagination');
  const month = page.getByTestId('offers-month-pagination');
  await expect(today).toBeVisible();
  await expect(week).toBeVisible();
  await expect(month).toBeVisible();

  const todayItems = page.getByTestId('offers-products-today').locator('a[data-product-card-image]');
  const weekItems = page.getByTestId('offers-products-week').locator('a[data-product-card-image]');
  await expect(todayItems).toHaveCount(8);
  await expect(weekItems).toHaveCount(8);
  const firstTodayItem = await todayItems.first().getAttribute('href');
  const firstWeekItem = await weekItems.first().getAttribute('href');

  await today.getByRole('button', { name: 'Next today offers page' }).click();
  await expect.poll(() => new URL(page.url()).searchParams.get('todayPage')).toBe('2');
  await expect(todayItems).toHaveCount(8);
  await expect(todayItems.first()).not.toHaveAttribute('href', firstTodayItem!);
  expect(await weekItems.first().getAttribute('href')).toBe(firstWeekItem);

  await week.getByRole('button', { name: 'Next week offers page' }).click();
  await expect.poll(() => new URL(page.url()).searchParams.get('weekPage')).toBe('2');
  expect(new URL(page.url()).searchParams.get('todayPage')).toBe('2');
  await expect(weekItems.first()).not.toHaveAttribute('href', firstWeekItem!);

  await page.reload();
  await expect(today.getByRole('button', { name: /Page 2 of .* today offers/ })).toHaveAttribute('aria-current', 'page');
  await expect(week.getByRole('button', { name: /Page 2 of .* week offers/ })).toHaveAttribute('aria-current', 'page');
  await expect(month.getByRole('button', { name: /Page 1 of .* month offers/ })).toHaveAttribute('aria-current', 'page');
});

test('an empty signed-out wishlist does not show a false page count', async ({ page }) => {
  await page.goto('/wishlist?page=10');
  await expect(page.getByRole('heading', { name: /Saved Wishlist \(0\)/ })).toBeVisible();
  await expect(page.getByTestId('wishlist-pagination')).toHaveCount(0);
  await expect.poll(() => new URL(page.url()).searchParams.get('page')).toBeNull();
});

test('store inventory has separate shareable pages and clamps invalid deep links', async ({ page }) => {
  const store = {
    id: 'pagination-vendor', slug: 'pagination-test-store', storeName: 'Pagination Test Store',
    approved: true, active: true, category: 'Clothing & Fashion',
    address: 'Neemuch Market Road', city: 'Neemuch', pincode: '458441',
    bannerImage: '/product-placeholder.svg', logoImage: '/product-placeholder.svg',
    description: 'Test local shop', deliveryMinutes: 60, rating: 5, reviewCount: 0,
  };
  const products = Array.from({ length: 37 }, (_, index) => ({
    id: `page-test-${index}`, slug: `page-test-product-${index}`,
    name: `Paginated Store Item ${index + 1}`,
    brand: 'Pagination', department: 'men', category: 'Clothing & Fashion',
    subcategory: 'T-Shirts', shortDescription: 'Test item',
    description: 'Local published item', material: 'Cotton', careInstructions: [],
    price: 499, originalPrice: 799, discount: 38, images: ['/product-placeholder.svg'],
    thumbnail: '/product-placeholder.svg', rating: 4.5, reviewCount: 0,
    variants: [{ id: `page-variant-${index}`, size: 'M', available: true, stock: 4, colourName: 'Blue', sku: `page-sku-${index}`, price: 499, images: ['/product-placeholder.svg'] }],
    tags: [], newArrival: false, trending: false, featured: false,
    expressDelivery: false, returnWindowDays: 0, exchangeAvailable: false,
    vendorId: store.id, storeSlug: store.slug, storeName: store.storeName, active: true,
  }));
  await page.route('**/api/stores/active', route => route.fulfill({
    status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, stores: [store] }),
  }));
  await page.route('**/api/shop-products/published?*', route => {
    const url = new URL(route.request().url());
    if (url.searchParams.get('vendorId') === store.id) {
      return route.fulfill({
        status: 200, contentType: 'application/json',
        body: JSON.stringify({ success: true, products }),
      });
    }
    return route.continue();
  });
  await page.route('**/api/inventory/availability?*', route => route.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify({
      success: true,
      availability: products.map((product, index) => ({
        productId: product.id, variantId: `page-variant-${index}`, available: true,
      })),
    }),
  }));

  await page.goto('/store/pagination-test-store?page=2');
  const cards = page.locator('#store-inventory a[data-product-card-image]');
  const pager = page.getByTestId('store-pagination');
  await expect(cards).toHaveCount(16);
  await expect(pager.getByRole('status')).toContainText('Showing 17–32 of 37');
  await expect(pager.getByRole('button', { name: /Page 2 of 3 for store products/ })).toHaveAttribute('aria-current', 'page');
  expect(await cards.first().getAttribute('href')).toBe('/product/page-test-product-16');

  await pager.getByRole('button', { name: 'Next store products page' }).click();
  await expect.poll(() => new URL(page.url()).searchParams.get('page')).toBe('3');
  await expect(cards).toHaveCount(5);

  await page.goto('/store/pagination-test-store?page=999');
  await expect.poll(() => new URL(page.url()).searchParams.get('page')).toBe('3');
  await expect(cards).toHaveCount(5);
});

test('guest wishlist keeps its selected products while moving between pages', async ({ page }) => {
  await page.addInitScript(() => {
    const ids = Array.from({ length: 26 }, (_, index) =>
      `sd-prod-${String(index + 1).padStart(3, '0')}`);
    localStorage.setItem('sd_wishlist_ids', JSON.stringify(ids));
  });

  await page.goto('/wishlist?page=2');
  const wishlist = page.locator('#wishlist-products');
  const links = wishlist.locator('a[data-product-card-image]');
  const pager = page.getByTestId('wishlist-pagination');
  await expect(page.getByRole('heading', { name: 'Saved Wishlist (26)' })).toBeVisible();
  await expect(links).toHaveCount(12);
  await expect(pager.getByRole('status')).toContainText('Showing 13–24 of 26 wishlist products');
  const secondPageFirst = await links.first().getAttribute('href');

  await pager.getByRole('button', { name: 'Next wishlist products page' }).click();
  await expect.poll(() => new URL(page.url()).searchParams.get('page')).toBe('3');
  await expect(links).toHaveCount(2);

  await pager.getByRole('button', { name: /Page 1 of 3 for wishlist products/ }).click();
  await expect.poll(() => new URL(page.url()).searchParams.get('page')).toBeNull();
  await expect(links).toHaveCount(12);
  expect(await links.first().getAttribute('href')).not.toBe(secondPageFirst);
});
