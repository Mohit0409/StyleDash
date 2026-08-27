import { expect, test } from '@playwright/test';

test('customer submits eligible return and cancellation requests', async ({ page }) => {
  let requests: Array<Record<string, unknown>> = [];
  let cancellationRequest: Record<string, unknown> | undefined;
  const deliveredOrder = {
    id: 'SD-RETURN-UI', createdAt: '2026-08-27T08:00:00Z', updatedAt: '2026-08-27T09:00:00Z',
    status: 'delivered', paymentStatus: 'paid', paymentMethod: 'upi', grandTotal: 800,
    fulfillments: [{ shopName: 'Approved Shop', status: 'DELIVERED', updatedAt: '2026-08-27T09:00:00Z' }],
    items: [{ productId: 'prod-return', variantId: 'var-return', productName: 'Return Item', size: 'M', colourName: 'Black', quantity: 2, lineTotal: 800,
      returnEligibility: { issueReturn: { available: true, windowDays: 2, deadline: '2026-08-29T09:00:00Z' }, sizeExchange: { available: true, windowDays: 7, deadline: '2026-09-03T09:00:00Z' } } }],
  };
  const cancellableOrder = {
    id: 'SD-CANCEL-UI', createdAt: '2026-08-27T10:00:00Z', updatedAt: '2026-08-27T10:00:00Z',
    status: 'placed', paymentStatus: 'pending', paymentMethod: 'cod', grandTotal: 500,
    fulfillments: [{ shopName: 'Approved Shop', status: 'NEW', updatedAt: null }],
    items: [{ productId: 'prod-cancel', variantId: 'var-cancel', productName: 'Cancel Item', size: 'L', colourName: 'Blue', quantity: 1, lineTotal: 500,
      returnEligibility: { issueReturn: { available: false, code: 'return_not_delivered' }, sizeExchange: { available: false, code: 'return_not_delivered' } } }],
  };
  await page.route('**/api/**', async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const json = (body: unknown, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
    if (path === '/api/auth/me') {
      await json({ success: true, csrfToken: 'csrf-return-ui', user: { uid: 'buyer-returns', name: 'Buyer Returns', email: 'buyer@example.test', role: 'customer' } });
      return;
    }
    if (path === '/api/return-requests' && request.method() === 'GET') {
      await json({ success: true, requests });
      return;
    }
    if (path === '/api/orders' && request.method() === 'GET') {
      await json({ success: true, orders: [deliveredOrder, { ...cancellableOrder, ...(cancellationRequest ? { cancellationRequest } : {}) }] });
      return;
    }
    if (path === '/api/orders/SD-RETURN-UI/return-requests' && request.method() === 'POST') {
      const payload = request.postDataJSON() as Record<string, unknown>;
      const created = { id: 'ret-ui-1', orderId: 'SD-RETURN-UI', shopName: 'Approved Shop', productId: 'prod-return', productName: 'Return Item', variantId: 'var-return', requestType: payload.requestType, reason: payload.reason, details: payload.details || null, quantity: payload.quantity || 1, unitPrice: 400, itemSubtotal: 400, status: 'REQUESTED', createdAt: '2026-08-27T11:00:00Z', updatedAt: '2026-08-27T11:00:00Z' };
      requests = [created];
      await json({ success: true, request: created }, 201);
      return;
    }
    if (path === '/api/orders/SD-CANCEL-UI/cancellation-request' && request.method() === 'POST') {
      const payload = request.postDataJSON() as Record<string, unknown>;
      cancellationRequest = { status: 'REQUESTED', reason: payload.reason, details: payload.details || null, createdAt: '2026-08-27T11:05:00Z', updatedAt: '2026-08-27T11:05:00Z' };
      await json({ success: true, cancellationRequest }, 201);
      return;
    }
    await route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ success: false, error: `Unexpected ${request.method()} ${path}` }) });
  });

  await page.goto('/orders');
  await expect(page.getByRole('heading', { name: 'Your Orders' })).toBeVisible();
  await page.getByRole('button', { name: 'Report item issue' }).click();
  await page.getByLabel('Issue').selectOption('DAMAGED');
  await page.getByLabel('Details (optional)').last().fill('Outer package and item arrived damaged');
  await page.getByRole('button', { name: 'Submit request' }).click();
  await expect(page.getByText('requested', { exact: true })).toBeVisible();
  await expect(page.getByText(/issue return · damaged/i)).toBeVisible();

  await page.getByRole('button', { name: 'Request cancellation' }).click();
  await page.getByLabel('Reason').selectOption('ORDERED_BY_MISTAKE');
  await page.getByLabel('Details (optional)').last().fill('I selected the wrong product');
  await page.getByRole('button', { name: 'Submit cancellation request' }).click();
  await expect(page.getByText(/Cancellation request: requested/i)).toBeVisible();
});
