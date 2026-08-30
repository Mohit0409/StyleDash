import { expect, test } from '@playwright/test';

test('customer can register and receive a working authenticated session', async ({
  page,
}) => {
  const unique = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  const email = `e2e-${unique}@example.test`;
  const phone = `+919${String(Date.now()).slice(-9)}`;

  await page.goto('/register');

  await page.getByPlaceholder('Full name').fill('StyleDash E2E Customer');
  await page.getByPlaceholder('Phone number').fill(phone);
  await page.getByPlaceholder('Email').fill(email);
  await page
    .getByPlaceholder('Password (8+ characters)')
    .fill('E2E-only-password-2026!');

  await page.getByRole('button', { name: 'Register' }).click();

  await expect(page).toHaveURL(/\/profile$/);

  // Session must remain usable on another protected route.
  await page.goto('/orders');

  await expect(page).toHaveURL(/\/orders$/);
  await expect(
    page.getByRole('heading', { name: 'Welcome back' }),
  ).toHaveCount(0);
});
