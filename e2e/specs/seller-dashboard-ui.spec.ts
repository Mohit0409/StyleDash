import { expect, test } from '@playwright/test';

test('approved shop enters seller dashboard before activation', async ({ page }) => {
  await page.route('**/api/**', async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const json = (body: unknown) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
    if (path === '/api/auth/me') {
      await json({ success: true, csrfToken: 'csrf-dashboard', user: { uid: 'seller-approved', name: 'Approved Seller', email: 'approved@example.test', role: 'customer' } });
      return;
    }
    if (path === '/api/vendor-applications/me') {
      await json({ success: true, application: {
        id: 'shop-approved', status: 'APPROVED', shopName: 'Approved Shop', ownerName: 'Approved Seller',
        registeredEmail: 'approved@example.test', category: 'Clothing & Fashion', description: 'Approved seller dashboard test shop.',
        address: 'Main Market', city: 'Neemuch', state: 'Madhya Pradesh', pincode: '458441',
        createdAt: '2026-08-25T00:00:00Z', updatedAt: '2026-08-25T00:00:00Z',
      } });
      return;
    }
    if (path === '/api/shop-products') {
      await json({ success: true, products: [] });
      return;
    }
    await route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ success: false, error: 'Unexpected API request.' }) });
  });

  await page.goto('/partner');
  await expect(page.getByRole('heading', { name: 'Shop Approved', exact: true }).first()).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Seller Dashboard' })).toBeVisible();
  await expect(page.getByText('APPROVED', { exact: true })).toBeVisible();
  await page.getByRole('tab', { name: 'My Shop', exact: true }).click();
  await expect(page.getByText('Approved Shop')).toBeVisible();
  await page.getByRole('tab', { name: 'Products', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Product submissions' })).toBeVisible();
  await expect(page.getByRole('button', { name: /publish/i })).toHaveCount(0);
});
