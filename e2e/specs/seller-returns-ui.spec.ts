import { expect, test } from '@playwright/test';

test('seller sees only shop return requests and adds a review note', async ({ page }) => {
  let sellerNote: string | null = null;
  await page.route('**/api/**', async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const json = (body: unknown, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
    if (path === '/api/auth/me') {
      await json({ success: true, csrfToken: 'csrf-seller-return', user: { uid: 'seller-return', name: 'Seller Return', email: 'seller@example.test', role: 'customer' } });
      return;
    }
    if (path === '/api/vendor-applications/me') {
      await json({ success: true, application: { id: 'shop-return', status: 'APPROVED', shopName: 'Return Shop', ownerName: 'Seller Return', registeredEmail: 'seller@example.test', category: 'Clothing & Fashion', description: 'Return workflow seller.', address: 'Main Market', city: 'Neemuch', state: 'Madhya Pradesh', pincode: '458441', createdAt: '2026-08-25T00:00:00Z', updatedAt: '2026-08-25T00:00:00Z' } });
      return;
    }
    if (path === '/api/shop-products') { await json({ success: true, products: [] }); return; }
    if (path === '/api/seller-orders') { await json({ success: true, orders: [] }); return; }
    if (path === '/api/seller-return-requests' && request.method() === 'GET') {
      await json({ success: true, requests: [{ id: 'ret-seller-1', orderId: 'SD-SELLER-RETURN', shopName: 'Return Shop', productId: 'prod-1', productName: 'Seller Return Item', variantId: 'var-1', requestType: 'SIZE_EXCHANGE', reason: 'SIZE_ISSUE', details: 'Need a larger size', quantity: 1, unitPrice: 900, itemSubtotal: 900, status: 'REQUESTED', sellerNote, adminNote: null, createdAt: '2026-08-27T10:00:00Z', updatedAt: '2026-08-27T10:00:00Z' }] });
      return;
    }
    if (path === '/api/seller-return-requests/ret-seller-1' && request.method() === 'PATCH') {
      sellerNote = String((request.postDataJSON() as { note?: string }).note || '');
      await json({ success: true, request: { id: 'ret-seller-1', orderId: 'SD-SELLER-RETURN', shopName: 'Return Shop', productId: 'prod-1', productName: 'Seller Return Item', variantId: 'var-1', requestType: 'SIZE_EXCHANGE', reason: 'SIZE_ISSUE', details: 'Need a larger size', quantity: 1, unitPrice: 900, itemSubtotal: 900, status: 'REQUESTED', sellerNote, adminNote: null, createdAt: '2026-08-27T10:00:00Z', updatedAt: '2026-08-27T10:01:00Z' } });
      return;
    }
    await route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ success: false, error: `Unexpected ${request.method()} ${path}` }) });
  });

  await page.goto('/partner');
  await page.getByRole('tab', { name: 'Returns', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Returns & Exchanges' })).toBeVisible();
  await expect(page.getByText('Seller Return Item')).toBeVisible();
  await expect(page.getByText(/^Qty 1 .* SIZE EXCHANGE$/)).toBeVisible();
  await page.getByPlaceholder('Add seller review note').fill('Large size is available for exchange');
  await page.getByRole('button', { name: 'Save note' }).click();
  await expect(page.getByText(/Your note: Large size is available for exchange/i)).toBeVisible();
});
