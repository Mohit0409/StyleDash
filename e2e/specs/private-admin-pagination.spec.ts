import { expect, test, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const ROOT = process.env.ADMIN_PAGER_ASSET_ROOT ? resolve(process.env.ADMIN_PAGER_ASSET_ROOT) : resolve(process.cwd(), 'server/admin');
const ORIGIN = 'http://127.0.0.1:19876';
const products = Array.from({ length: 63 }, (_, i) => ({
  id: 'product-' + (i + 1),
  applicationId: 'store-1',
  name: 'Product ' + (i + 1),
  description: 'Product listing fixture',
  brand: 'Test Brand',
  department: 'unisex',
  category: i < 20 ? 'Footwear' : 'Accessories',
  status: i < 20 ? 'APPROVED' : 'PUBLISHED',
  pricePaise: 10000,
  originalPricePaise: 15000,
  customerPricePaise: 10500,
  inventory: 4,
  variants: [],
}));
const requests = Array.from({ length: 63 }, (_, i) => ({
  id: 'request-' + (i + 1),
  productName: 'Request product ' + (i + 1),
  applicationId: 'store-1',
  shopName: 'Test Shop',
  action: 'UPDATE',
  status: 'UNDER_REVIEW',
  changeSummary: [],
}));
const inventory = Array.from({ length: 63 }, (_, i) => ({
  variantId: 'variant-' + (i + 1),
  productId: 'product-' + (i + 1),
  productName: 'Stock item ' + (i + 1),
  brand: 'Test Brand',
  category: 'Accessories',
  department: 'unisex',
  storeId: 'store-1',
  storeName: 'Test Shop',
  size: 'M',
  colour: 'Blue',
  stock: i < 20 ? 0 : 7,
}));
const shops = [{ id: 'store-1', name: 'Test Shop', status: 'ACTIVE' }];
const read = (name: string) => readFileSync(resolve(ROOT, name));

async function openMockAdmin(page: Page) {
  const unsafeRequests: string[] = [];
  const calls: string[] = [];
  await page.route('**/*', async route => {
    const request = route.request();
    const url = new URL(request.url());
    if (url.origin !== ORIGIN) {
      unsafeRequests.push(request.url());
      await route.abort();
      return;
    }
    if (!['GET', 'HEAD'].includes(request.method())) {
      unsafeRequests.push(request.method() + ' ' + url.pathname);
      await route.fulfill({ status: 403, contentType: 'application/json',
        body: JSON.stringify({ error: 'All mock admin writes are prohibited' }) });
      return;
    }
    if (url.pathname === '/') {
      await route.fulfill({ status: 200, contentType: 'text/html', body: read('index.html') });
      return;
    }
    const assets: Record<string, string> = {
      '/admin.js': 'admin.js',
      '/admin.css': 'admin.css',
      '/admin-variants.css': 'admin-variants.css',
      '/leaflet.js': 'leaflet.js',
      '/leaflet.css': 'leaflet.css',
      '/delivery-zone-map.js': 'delivery-zone-map.js',
    };
    if (assets[url.pathname]) {
      await route.fulfill({ status: 200,
        contentType: url.pathname.endsWith('.js') ? 'application/javascript' : 'text/css',
        body: read(assets[url.pathname]) });
      return;
    }
    calls.push(url.pathname);
    const endpoints: Record<string, unknown> = {
      '/api/admin/me': { admin: { username: 'Local test admin' }, csrfToken: 'nonproduction-test' },
      '/api/admin/orders': { orders: [] },
      '/api/admin/shop-products': { products },
      '/api/admin/vendors': { applications: [{ id: 'store-1', shopName: 'Test Shop', status: 'ACTIVE' }] },
      '/api/admin/shop-product-requests': { requests },
      '/api/admin/inventory': { shops, inventory },
    };
    const payload = endpoints[url.pathname];
    if (payload !== undefined) {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(payload) });
      return;
    }
    await route.fulfill({ status: 404, contentType: 'application/json', body: '{}' });
  });
  await page.goto(ORIGIN + '/', { waitUntil: 'domcontentloaded' });
  await expect(page.locator('#app-view')).toBeVisible();
  return { unsafeRequests, calls };
}

test('shop products paginate, page 2 changes items, and bulk selects visible records only', async ({ page }) => {
  const env = await openMockAdmin(page);
  await page.locator('[data-tab="shop-products"]').click();
  await expect(page.getByRole('navigation', { name: 'Shop products pagination' })).toBeVisible();
  const cards = page.locator('#content .grid .card');
  await expect(cards).toHaveCount(25);
  await expect(cards.first()).toContainText('Product 1');
  await page.getByRole('button', { name: 'Next Shop products page' }).click();
  await expect(cards).toHaveCount(25);
  await expect(cards.first()).toContainText('Product 26');
  await expect(page.getByRole('status', { name: '' }).last()).toBeVisible();
  const select = page.locator('[data-bulk-select-all="products"]');
  await select.check();
  await expect(page.locator('#bulk-count-products')).toHaveText('25');
  await page.getByRole('button', { name: 'Next Shop products page' }).click();
  await expect(cards).toHaveCount(13);
  await expect(cards.first()).toContainText('Product 51');
  await expect(page.locator('#bulk-count-products')).toHaveText('0');
  if (process.env.ADMIN_PAGER_ASSET_ROOT) {
    await expect(page.locator('[data-bulk-target="products"] option[value="SET_COMMISSION"]')).toHaveCount(1);
  }
  await expect(page.locator('[data-bulk-select="products"]:checked')).toHaveCount(0);
  await expect(page.locator('#content')).toContainText('Select this page');
  expect(env.unsafeRequests).toEqual([]);
  expect(env.calls.filter(x => x === '/api/admin/shop-products')).toHaveLength(1);
});

test('search and category filters reset shop products to first page', async ({ page }) => {
  await openMockAdmin(page);
  await page.locator('[data-tab="shop-products"]').click();
  const cards = page.locator('#content .grid .card');
  await page.getByRole('button', { name: 'Page 3 of 3 for Shop products' }).click();
  await expect(cards).toHaveCount(13);
  await page.locator('#search').fill('Product 1');
  await page.locator('#search-form button[type="submit"]').click();
  await expect(cards).toHaveCount(11);
  await expect(cards.first()).toContainText('Product 1');
  await expect(page.getByRole('navigation', { name: 'Shop products pagination' })).toHaveCount(1);
  await page.locator('#search').fill('');
  await page.locator('#search-form button[type="submit"]').click();
  await page.getByRole('button', { name: 'Page 3 of 3 for Shop products' }).click();
  await page.locator('select[data-admin-filter="category"]').selectOption('Footwear');
  await expect(cards).toHaveCount(20);
  await expect(cards.first()).toContainText('Product 1');
  await expect(page.getByRole('navigation', { name: 'Shop products pagination' })).toContainText('Page 1 of 1');
});

test('product requests paginate and selections are not carried across pages', async ({ page }) => {
  const env = await openMockAdmin(page);
  await page.locator('[data-tab="shop-product-requests"]').click();
  const cards = page.locator('#content .grid .card');
  await expect(cards).toHaveCount(25);
  await page.getByRole('button', { name: 'Next Product requests page' }).click();
  await expect(cards.first()).toContainText('Request product 26');
  await page.locator('[data-bulk-select-all="requests"]').check();
  await expect(page.locator('#bulk-count-requests')).toHaveText('25');
  await page.getByRole('button', { name: 'Next Product requests page' }).click();
  await expect(cards).toHaveCount(13);
  await expect(page.locator('#bulk-count-requests')).toHaveText('0');
  expect(env.unsafeRequests).toEqual([]);
});

test('inventory stock filters clamp pages and keep adjustment actions untouched', async ({ page }) => {
  const env = await openMockAdmin(page);
  await page.locator('[data-tab="inventory"]').click();
  const rows = page.locator('#content table tbody tr');
  await expect(rows).toHaveCount(25);
  await page.getByRole('button', { name: 'Page 3 of 3 for Inventory' }).click();
  await expect(rows).toHaveCount(13);
  await expect(rows.first()).toContainText('Stock item 51');
  await expect(rows.locator('[data-action="inventory"]')).toHaveCount(13);
  await page.locator('select[data-admin-filter="stock"]').selectOption('out');
  await expect(rows).toHaveCount(20);
  await expect(rows.first()).toContainText('Stock item 1');
  await expect(page.getByRole('navigation', { name: 'Inventory pagination' })).toContainText('Page 1 of 1');
  expect(env.unsafeRequests).toEqual([]);
});

test('empty product searches and mobile pagination retain readable layout', async ({ page }) => {
  await openMockAdmin(page);
  await page.locator('[data-tab="shop-products"]').click();
  await page.locator('#search').fill('missing-product-token');
  await page.locator('#search-form button[type="submit"]').click();
  await expect(page.locator('#content .grid .card')).toHaveCount(0);
  await expect(page.getByRole('navigation', { name: 'Shop products pagination' })).toHaveCount(0);
  await page.locator('#search').fill('');
  await page.locator('#search-form button[type="submit"]').click();
  const currentPage = page.getByRole('navigation', { name: 'Shop products pagination' });
  await expect(currentPage).toBeVisible();
  expect(await currentPage.evaluate(el => el.scrollWidth <= el.clientWidth + 1)).toBe(true);
});
