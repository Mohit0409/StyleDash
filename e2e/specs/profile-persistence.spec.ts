import { expect, test } from '@playwright/test';

test('saved profile survives logout and login', async ({ page }) => {
  const unique = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  const email = `profile-persistence-${unique}@example.test`;
  const phone = `9${Math.floor(100000000 + Math.random() * 900000000)}`;
  const password = 'E2E-profile-persistence-2026!';
  const street = `42 Persistence Market Road ${unique}`;

  await page.goto('/register');
  await page.getByPlaceholder('Full name').fill('Profile Persistence Customer');
  await page.getByPlaceholder('Phone number').fill(phone);
  await page.getByPlaceholder('Email').fill(email);
  await page.getByPlaceholder('Password (8+ characters)').fill(password);
  await page.getByRole('button', { name: 'Register' }).click();
  await expect(page).toHaveURL(/\/profile$/);

  await page.getByText('Street address and landmark').locator('input').fill(street);
  await page.getByRole('button', { name: 'Save profile' }).click();
  await expect(page.getByRole('status')).toHaveText('Profile and delivery address saved.');

  await page.getByRole('button', { name: 'Logout' }).click();
  await expect(page).toHaveURL(/\/login$/);

  await page.getByPlaceholder('Email').fill(email);
  await page.getByPlaceholder('Password (8+ characters)').fill(password);
  await page.getByRole('button', { name: 'Login' }).click();
  await expect(page).toHaveURL(/\/profile$/);
  await expect(page.getByText('Street address and landmark').locator('input')).toHaveValue(street);
});
