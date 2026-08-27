import { expect, test } from '@playwright/test';

test('approved shop enters seller dashboard before activation', async ({ page }) => {
  let fulfillment: Record<string, unknown> = {
    status: 'NEW', updatedAt: null, allowedNextStatuses: ['PROCESSING'], shipping: null,
  };
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
    if (path === '/api/seller-settlements') { await json({ success: true, settlements: [] }); return; }
    if (path === '/api/seller-return-requests') {
      await json({ success: true, requests: [] });
      return;
    }
    if (path === '/api/seller-orders') {
      await json({ success: true, orders: [{
        id: 'SD-SELLER-1', status: 'placed', paymentStatus: 'paid', paymentMethod: 'upi', deliveryMethod: 'express',
        createdAt: '2026-08-25T12:00:00Z', updatedAt: '2026-08-25T12:01:00Z', sellerSubtotal: 800,
        address: { name: 'Buyer One', phone: '9999999999', street: 'Main Road', city: 'Neemuch', state: 'Madhya Pradesh', pincode: '458441' },
        items: [{ productId: 'shopprod_1', productName: 'Seller Item', variantId: 'v1', quantity: 2, unitPrice: 400, lineTotal: 800 }],
        fulfillment,
      }] });
      return;
    }
    if (path === '/api/seller-orders/SD-SELLER-1/fulfillment' && request.method() === 'PATCH') {
      const payload = request.postDataJSON() as { status: string; carrier?: string; trackingNumber?: string };
      const nextByStatus: Record<string, string[]> = { PROCESSING: ['READY'], READY: ['SHIPPED'], SHIPPED: ['DELIVERED'], DELIVERED: [] };
      fulfillment = {
        status: payload.status, updatedAt: '2026-08-27T12:02:00Z', allowedNextStatuses: nextByStatus[payload.status] || [],
        shipping: payload.carrier && payload.trackingNumber ? { carrier: payload.carrier, trackingNumber: payload.trackingNumber } : (fulfillment.shipping || null),
      };
      await json({ success: true, fulfillment });
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
  await page.getByRole('tab', { name: 'Orders', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Seller Orders' })).toBeVisible();
  await expect(page.getByText('Seller Item')).toBeVisible();
  await expect(page.getByText('Buyer One')).toBeVisible();
  await expect(page.getByText('INR 800').first()).toBeVisible();
  await expect(page.getByText('NEW', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Start processing' }).click();
  await expect(page.getByText('PROCESSING', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Mark ready' }).click();
  await expect(page.getByText('READY', { exact: true })).toBeVisible();
  await page.getByLabel('Carrier (optional)').fill('Delhivery');
  await page.getByLabel('Tracking number (optional)').fill('DLV-123456');
  await page.getByRole('button', { name: 'Mark shipped' }).click();
  await expect(page.getByText('SHIPPED', { exact: true })).toBeVisible();
  await expect(page.getByText('Tracking: DLV-123456')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Mark delivered' })).toBeVisible();
  await page.getByRole('tab', { name: 'Products', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Product submissions' })).toBeVisible();
  await expect(page.getByRole('button', { name: /publish/i })).toHaveCount(0);
});
