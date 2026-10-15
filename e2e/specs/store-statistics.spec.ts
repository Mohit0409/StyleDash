import { expect, test } from '@playwright/test';

test('compact store statistics open nested verified reviews without occupying default page space', async ({ page }) => {
  const store = {
    id: 'store-stats-vendor',
    slug: 'store-stats-test',
    storeName: 'Test Local Store Statistics',
    category: 'Clothing & Fashion',
    address: 'Market Road, Neemuch',
    city: 'Neemuch',
    pincode: '458441',
    description: 'Test published catalogue with verified reviews',
    bannerImage: '/product-placeholder.svg',
    logoImage: '/product-placeholder.svg',
    deliveryMinutes: 60,
    active: true,
    approved: true,
    rating: 5,
    reviewCount: 2,
    productCount: 4,
    createdAt: new Date(Date.now() - 100 * 24 * 60 * 60 * 1000).toISOString(),
  };
  const unratedStore = {
    ...store,
    id: 'store-unrated-vendor',
    slug: 'store-unrated-test',
    storeName: 'Unrated Local Store',
    rating: 0,
    reviewCount: 0,
    productCount: 0,
  };
  const day = 24 * 60 * 60 * 1000;
  const dates = [1 / 24, 3, 20, 45].map(daysAgo => new Date(Date.now() - daysAgo * day).toISOString());
  const products = dates.map((updatedAt, index) => ({
    id: 'stats-product-' + index,
    slug: 'store-stats-product-' + index,
    name: 'Store Statistics Product ' + (index + 1),
    brand: 'Local Store',
    department: 'men',
    category: 'Clothing & Fashion',
    shortDescription: 'Locally published item',
    description: 'Locally published item',
    material: 'Cotton',
    careInstructions: [],
    price: 399,
    originalPrice: 599,
    discount: 33,
    images: ['/product-placeholder.svg'],
    thumbnail: '/product-placeholder.svg',
    rating: 0,
    reviewCount: 0,
    variants: [{
      id: 'stats-variant-' + index,
      sku: 'stats-sku-' + index,
      size: 'M',
      available: true,
      stock: 5,
      colourName: 'Blue',
      price: 399,
      images: ['/product-placeholder.svg'],
    }],
    tags: [],
    expressDelivery: false,
    returnWindowDays: 0,
    vendorId: store.id,
    storeSlug: store.slug,
    storeName: store.storeName,
    active: true,
    updatedAt,
  }));

  await page.route('**/api/stores/active', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ success: true, stores: [store, unratedStore] }),
  }));
  await page.route('**/api/shop-products/published?*', route => {
    const url = new URL(route.request().url());
    if (url.searchParams.get('vendorId') === store.id) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, products }),
      });
    }
    return route.continue();
  });
  await page.route('**/api/inventory/availability?*', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      success: true,
      availability: products.map((product, index) => ({
        productId: product.id,
        variantId: 'stats-variant-' + index,
        available: true,
      })),
    }),
  }));
  let reviewFetches = 0;
  await page.route('**/api/store-reviews?*', route => {
    reviewFetches += 1;
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        storeId: store.id,
        rating: 4.6,
        reviewCount: 7,
        distribution: { '5': 5, '4': 2, '3': 0, '2': 0, '1': 0 },
        reviews: [{
          id: 'verified-review-1',
          storeId: store.id,
          userName: 'Verified local customer',
          rating: 5,
          title: 'Great local service',
          comment: 'A reliable purchase from this store',
          createdAt: new Date().toISOString(),
        }],
      }),
    });
  });

  // Card badge must show actual rating rather than "New", and never invent
  // a score for the second store that has no verified reviews.
  await page.goto('/stores');
  await expect(page.getByTestId('store-card-rating')).toHaveCount(2);
  await expect(page.getByTestId('store-card-rating').first()).toContainText('5/5');
  await expect(page.getByTestId('store-card-rating').last()).toContainText('Not rated');
  await expect(page.getByTestId('store-card-rating').first()).not.toContainText('New');

  await page.goto('/store/store-stats-test');
  const trigger = page.getByTestId('store-stat-trigger');
  await expect(trigger).toBeVisible();
  await expect(trigger).toHaveAttribute('aria-expanded', 'false');
  await expect.poll(async () => page.getByTestId('store-statistics').evaluate(element => element.getBoundingClientRect().height)).toBe(0);
  await expect(page.getByTestId('store-stat-panel')).toHaveCount(0);
  await expect(page.getByRole('heading', { name: 'Store Reviews' })).toHaveCount(0);
  await expect(page.getByRole('heading', { name: 'Store Inventory Catalogue' })).toBeVisible();
  expect(reviewFetches).toBe(0);

  await trigger.click();
  await expect(trigger).toHaveAttribute('aria-expanded', 'true');
  await expect(page.getByTestId('store-stat-products')).toContainText('4');
  await expect(page.getByTestId('store-stat-rating')).toContainText('5/5');
  await expect(page.getByTestId('store-stat-activity')).toContainText('Daily active');
  await expect(page.getByTestId('store-stat-update-counts')).toContainText('1 updated in 24h');
  await expect(page.getByTestId('store-stat-update-counts')).toContainText('2 updated in 7 days');
  await expect(page.getByTestId('store-stat-update-counts')).toContainText('3 updated in 30 days');
  const ratingToggle = page.getByTestId('store-rating-toggle');
  await expect(ratingToggle).toHaveAttribute('aria-expanded', 'false');
  expect(reviewFetches).toBe(0);

  await ratingToggle.click();
  await expect(ratingToggle).toHaveAttribute('aria-expanded', 'true');
  await expect(page.getByTestId('store-rating-reviews')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Store Reviews' })).toBeVisible();
  await expect(page.getByText('Great local service')).toBeVisible();
  await expect(page.getByTestId('store-stat-rating')).toContainText('4.6/5');
  expect(reviewFetches).toBeGreaterThan(0);

  await ratingToggle.click();
  await expect(page.getByTestId('store-rating-reviews')).toHaveCount(0);
  await trigger.click();
  await expect(page.getByTestId('store-stat-panel')).toHaveCount(0);
  await trigger.click();
  await expect(page.getByTestId('store-rating-toggle')).toHaveAttribute('aria-expanded', 'false');
  await page.getByTestId('store-rating-toggle').click();
  await page.keyboard.press('Escape');
  await expect(trigger).toHaveAttribute('aria-expanded', 'false');
  await expect(page.getByTestId('store-stat-panel')).toHaveCount(0);
  await expect(trigger).toBeFocused();
});
