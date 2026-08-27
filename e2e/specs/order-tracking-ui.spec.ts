import { expect, test } from '@playwright/test';

test('customer sees per-shop carrier and tracking details', async ({ page }) => {
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname;
    const json = (body: unknown) => route.fulfill({
      status: 200, contentType: 'application/json', body: JSON.stringify(body),
    });
    if (path === '/api/auth/me') {
      await json({ success: true, csrfToken: 'csrf-orders', user: {
        uid: 'buyer-1', name: 'Buyer One', email: 'buyer@example.test', role: 'customer',
      } });
      return;
    }
    if (path === '/api/orders') {
      await json({ success: true, orders: [{
        id: 'SD-TRACK-1', createdAt: '2026-08-27T08:00:00Z', status: 'placed',
        paymentStatus: 'paid', grandTotal: 800,
        fulfillments: [{ shopName: 'Approved Shop', status: 'SHIPPED',
          updatedAt: '2026-08-27T09:00:00Z', shipping: {
            carrier: 'Delhivery', trackingNumber: 'DLV-123456',
          } }],
        items: [{ variantId: 'v1', productName: 'Seller Item', size: 'M',
          colourName: 'Black', quantity: 2, lineTotal: 800 }],
      }] });
      return;
    }
    await route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ success: false }) });
  });

  await page.goto('/orders');
  await expect(page.getByRole('heading', { name: 'Your Orders' })).toBeVisible();
  await expect(page.getByText('Approved Shop')).toBeVisible();
  await expect(page.getByText('SHIPPED', { exact: true })).toBeVisible();
  await expect(page.getByText('Delhivery · Tracking DLV-123456')).toBeVisible();
});
