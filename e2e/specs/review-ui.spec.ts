import { expect, test } from '@playwright/test';
import { existsSync, readFileSync, renameSync, writeFileSync } from 'node:fs';
import path from 'node:path';

const PRODUCT_ID = 'sd-prod-001';
const PRODUCT_SLUG = 'pure-cotton-oversized-graphic-tee-sd-prod-001';

const grantDeliveredPurchase = (userId: string) => {
  const statePath = path.join(process.cwd(), '.e2e-runtime', 'payment-state', 'orders.json');
  const state = existsSync(statePath)
    ? JSON.parse(readFileSync(statePath, 'utf8'))
    : { orders: {}, inventory: {}, idempotency: {}, processedPayments: {}, processedRefunds: {}, processedWebhookEvents: {}, operationalAlerts: {} };
  const now = new Date().toISOString();
  const orderId = `review-e2e-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  state.orders[orderId] = {
    id: orderId,
    userId,
    status: 'delivered',
    paymentMethod: 'cod',
    paymentStatus: 'pending',
    fulfillmentRequired: true,
    isPaymentTestOrder: false,
    createdAt: now,
    updatedAt: now,
    statusHistory: [{ status: 'delivered', at: now }],
    items: [{ productId: PRODUCT_ID, productName: 'Pure Cotton Oversized Graphic Tee' }],
  };
  const temporary = `${statePath}.${process.pid}.tmp`;
  writeFileSync(temporary, JSON.stringify(state), 'utf8');
  renameSync(temporary, statePath);
  return orderId;
};
test('verified delivered customer can publish edit and delete a review', async ({ page }) => {
  const unique = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  const phone = `+919${String(Date.now()).slice(-9)}`;

  await page.goto('/register');
  await page.getByPlaceholder('Full name').fill('Review E2E Customer');
  await page.getByPlaceholder('Phone number').fill(phone);
  await page.getByPlaceholder('Email').fill(`review-${unique}@example.test`);
  await page.getByPlaceholder('Password (8+ characters)').fill('E2E-review-password-2026!');
  await page.getByRole('button', { name: 'Register' }).click();
  await expect(page).toHaveURL(/\/profile$/);

  const me = await page.evaluate(async () => {
    const response = await fetch('/api/auth/me');
    return response.json();
  });
  const userId = me.user?.id || me.user?.uid;
  expect(userId).toBeTruthy();

  await page.goto(`/product/${PRODUCT_SLUG}`);
  await expect(page.getByRole('heading', { name: 'Customer Reviews' })).toBeVisible();
  await expect(page.getByText('Reviews are available after this product has been delivered to you.')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Publish Review' })).toHaveCount(0);

  grantDeliveredPurchase(userId);
  await page.reload();
  await expect(page.getByText('Verified delivered purchase')).toBeVisible();
  await page.getByRole('radio', { name: '4 stars' }).click();
  await page.getByPlaceholder('What stood out?').fill('Great local purchase');
  await page.getByPlaceholder('Share your experience with this product.').fill('Comfortable fit and exactly as shown.');
  await page.getByRole('button', { name: 'Publish Review' }).click();

  await expect(page.getByText('Based on 1 verified review')).toBeVisible();
  await expect(page.getByText('Verified Purchase')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Great local purchase' })).toBeVisible();
  await expect(page.getByRole('article').getByText('Comfortable fit and exactly as shown.')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Edit your review' })).toBeVisible();

  await page.getByRole('radio', { name: '5 stars' }).click();
  await page.getByPlaceholder('What stood out?').fill('Excellent local purchase');
  await page.getByPlaceholder('Share your experience with this product.').fill('Updated review after wearing it again.');
  await page.getByRole('button', { name: 'Update Review' }).click();

  await expect(page.getByRole('heading', { name: 'Excellent local purchase' })).toBeVisible();
  await expect(page.getByRole('article').getByText('Updated review after wearing it again.')).toBeVisible();
  await expect(page.getByRole('article').getByLabel('5 out of 5 stars')).toBeVisible();

  page.once('dialog', dialog => dialog.accept());
  await page.getByRole('button', { name: 'Delete' }).click();
  await expect(page.getByText('No customer reviews yet.')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Publish Review' })).toBeVisible();
});
