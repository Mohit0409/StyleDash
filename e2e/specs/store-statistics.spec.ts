import { expect, test } from '@playwright/test';

test('store profile displays published products, verified rating and catalogue activity', async ({ page }) => {
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
    rating: 0,
    reviewCount: 0,
    productCount: 4,
    createdAt: new Date(Date.now() - 100 * 24 * 60 * 60 * 1000).toISOString(),
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
    exchangeAvailable: false,
    vendorId: store.id,
    storeSlug: store.slug,
    storeName: store.storeName,
    active: true,
    updatedAt,
  }));

  await page.route('**/api/stores/active', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ success: true, stores: [store] }),
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
  await page.route('**/api/store-reviews?*', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      success: true,
      storeId: store.id,
      rating: 4.6,
      reviewCount: 7,
      distribution: { '5': 5, '4': 2, '3': 0, '2': 0, '1': 0 },
      reviews: [],
    }),
  }));

  await page.goto('/store/store-stats-test');
  const statistics = page.getByTestId('store-statistics');
  await expect(statistics).toBeVisible();
  await expect(page.getByTestId('store-stat-products')).toContainText('4');
  await expect(page.getByTestId('store-stat-rating')).toContainText('4.6 / 5');
  await expect(page.getByTestId('store-stat-rating')).toContainText('7 verified customer reviews');
  await expect(page.getByTestId('store-stat-activity')).toContainText('Daily active');
  await expect(page.getByTestId('store-stat-update-counts')).toContainText('1 updated in 24h');
  await expect(page.getByTestId('store-stat-update-counts')).toContainText('2 updated in 7 days');
  await expect(page.getByTestId('store-stat-update-counts')).toContainText('3 updated in 30 days');
  await expect(page.getByRole('heading', { name: 'Store Inventory Catalogue' })).toBeVisible();
});
