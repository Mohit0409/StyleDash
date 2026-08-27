import { expect, test } from '@playwright/test';

test('seller sees read-only settlement earnings and payout status', async ({ page }) => {
  await page.route('**/api/**', async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const json = (body: unknown) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
    if (path === '/api/auth/me') {
      await json({ success: true, csrfToken: 'csrf-earnings', user: { uid: 'seller-earnings', name: 'Seller Earnings', email: 'earnings@example.test', role: 'customer' } });
      return;
    }
    if (path === '/api/vendor-applications/me') {
      await json({ success: true, application: {
        id: 'shop-earnings', status: 'ACTIVE', shopName: 'Earnings Shop', ownerName: 'Seller Earnings',
        registeredEmail: 'earnings@example.test', category: 'Clothing & Fashion', description: 'Seller earnings fixture.',
        address: 'Main Market', city: 'Neemuch', state: 'Madhya Pradesh', pincode: '458441', commissionPercent: 12,
        createdAt: '2026-08-25T00:00:00Z', updatedAt: '2026-08-25T00:00:00Z',
      } });
      return;
    }
    if (path === '/api/shop-products') { await json({ success: true, products: [] }); return; }
    if (path === '/api/seller-orders') { await json({ success: true, orders: [] }); return; }
    if (path === '/api/seller-return-requests') { await json({ success: true, requests: [] }); return; }
    if (path === '/api/seller-settlements') {
      await json({ success: true, settlements: [
        {
          id: 'set-eligible', orderId: 'SD-EARN-1', shopName: 'Earnings Shop', grossAmountPaise: 159900,
          commissionPercent: 12, commissionAmountPaise: 19188, netAmountPaise: 140712,
          paymentMethod: 'upi', status: 'ELIGIBLE', deliveredAt: '2026-08-20T10:00:00Z',
          clearanceUntil: '2026-08-27T10:00:00Z', eligibleAt: '2026-08-27T10:01:00Z',
          createdAt: '2026-08-20T10:00:00Z', updatedAt: '2026-08-27T10:01:00Z',
        },
        {
          id: 'set-paid', orderId: 'SD-EARN-2', shopName: 'Earnings Shop', grossAmountPaise: 100000,
          commissionPercent: 12, commissionAmountPaise: 12000, netAmountPaise: 88000,
          paymentMethod: 'cod', status: 'SETTLED', deliveredAt: '2026-08-18T10:00:00Z',
          clearanceUntil: '2026-08-25T10:00:00Z', collectionConfirmedAt: '2026-08-18T12:00:00Z',
          settledAt: '2026-08-26T10:00:00Z', payoutReference: 'UTR-SETTLED-123',
          createdAt: '2026-08-18T10:00:00Z', updatedAt: '2026-08-26T10:00:00Z',
        },
      ] });
      return;
    }
    await route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ success: false, error: `Unexpected ${request.method()} ${path}` }) });
  });

  await page.goto('/partner');
  await page.getByRole('tab', { name: 'Earnings', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Earnings & payouts' })).toBeVisible();
  await expect(page.getByText('ELIGIBLE', { exact: true })).toBeVisible();
  await expect(page.getByText('SETTLED', { exact: true })).toBeVisible();
  await expect(page.getByText('₹1,599.00')).toBeVisible();
  await expect(page.getByText('₹191.88')).toBeVisible();
  await expect(page.getByText('₹1,407.12').first()).toBeVisible();
  await expect(page.getByText('UTR-SETTLED-123')).toBeVisible();
  await expect(page.getByRole('button', { name: /release|settle|payout|collection/i })).toHaveCount(0);
});
