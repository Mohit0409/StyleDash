import { expect, test } from '@playwright/test';

test('forgot-password response remains generic', async ({ page }) => {
  await page.goto('/forgot-password');

  await page
    .getByPlaceholder('Email address')
    .fill('does-not-exist-e2e@example.test');

  await page
    .getByRole('button', { name: 'Send reset instructions' })
    .click();

  await expect(page.getByRole('status')).toHaveText(
    'If an account exists, reset instructions will be sent shortly.',
  );
});

test('reset token is removed from visible URL and invalid token fails safely', async ({
  page,
}) => {
  const fakeToken = 'A'.repeat(64);

  await page.goto(`/reset-password#token=${fakeToken}`);

  await expect(page).toHaveURL(/\/reset-password$/);

  expect(page.url()).not.toContain(fakeToken);

  await page.getByPlaceholder('New password', { exact: true }).fill('New-E2E-password-2026!');
  await page
    .getByPlaceholder('Confirm new password')
    .fill('New-E2E-password-2026!');

  await page.getByRole('button', { name: 'Reset password' }).click();

  await expect(page.getByRole('alert')).toContainText(
    'invalid or has expired',
  );

  expect(page.url()).not.toContain(fakeToken);
});

test('profile can start password recovery without the current password', async ({ page }) => {
  const unique = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  const email = `forgot-current-${unique}@example.test`;
  const phone = `9${Math.floor(100000000 + Math.random() * 900000000)}`;

  await page.goto('/register');
  await page.getByPlaceholder('Full name').fill('Forgot Current Password Customer');
  await page.getByPlaceholder('Phone number').fill(phone);
  await page.getByPlaceholder('Email').fill(email);
  await page.getByPlaceholder('Password (8+ characters)').fill('E2E-forgot-current-2026!');
  await page.getByRole('checkbox', { name: /agree to the terms/i }).check();
  await page.getByRole('button', { name: 'Register' }).click();
  await expect(page).toHaveURL(/\/profile$/);

  await page.getByRole('link', { name: 'Forgot current password?' }).click();

  await expect(page).toHaveURL(/\/forgot-password$/);
  await expect(page.getByPlaceholder('Email address')).toHaveValue(email);
  await expect(page.getByPlaceholder('Current password')).toHaveCount(0);
});
