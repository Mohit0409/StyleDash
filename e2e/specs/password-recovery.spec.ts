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
