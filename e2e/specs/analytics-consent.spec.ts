import { expect, test } from '@playwright/test';

test('keeps Google Analytics and Meta Pixel off when analytics is declined', async ({ page }) => {
  const trackerRequests: string[] = [];
  page.on('request', request => { if (/googletagmanager\.com|connect\.facebook\.net/.test(request.url())) trackerRequests.push(request.url()); });
  await page.goto('/');
  await expect(page.getByRole('dialog', { name: 'Analytics preferences' })).toBeVisible();
  expect(trackerRequests).toEqual([]);
  await page.getByRole('button', { name: 'Only necessary' }).click();
  await page.goto('/products');
  expect(trackerRequests).toEqual([]);
  await expect.poll(() => page.evaluate(() => localStorage.getItem('vibe4you_analytics_consent_v1'))).toBe('declined');
});

test('loads both trackers after consent and removes their cookies on withdrawal', async ({ page }) => {
  const trackerRequests: string[] = [];
  const collectionRequests: string[] = [];
  await page.route('https://www.googletagmanager.com/**', async route => {
    trackerRequests.push(route.request().url());
    await route.fulfill({ status: 200, contentType: 'text/javascript', body: `document.cookie='_ga=e2e; path=/';(()=>{const l=window.dataLayer||[],s=a=>{if(a[0]==='event')fetch('https://www.google-analytics.com/g/collect?en='+encodeURIComponent(a[1]))};l.forEach(s);const p=l.push.bind(l);l.push=(...x)=>{x.forEach(s);return p(...x)}})();` });
  });
  await page.route('https://connect.facebook.net/**', async route => {
    trackerRequests.push(route.request().url());
    await route.fulfill({ status: 200, contentType: 'text/javascript', body: `document.cookie='_fbp=e2e; path=/';(()=>{const p=window.fbq,s=a=>{if(a[0]==='track')fetch('https://www.facebook.com/tr?ev='+encodeURIComponent(a[1]))};p.queue.forEach(s);p.callMethod=(...a)=>s(a)})();` });
  });
  await page.route(/https:\/\/(?:www\.google-analytics\.com\/g\/collect|www\.facebook\.com\/tr).*/, async route => { collectionRequests.push(route.request().url()); await route.fulfill({ status: 204, body: '' }); });
  await page.goto('/');
  await page.getByRole('button', { name: 'Allow analytics' }).click();
  await expect.poll(() => trackerRequests.some(url => url.includes('gtag/js'))).toBe(true);
  await expect.poll(() => trackerRequests.some(url => url.includes('fbevents.js'))).toBe(true);
  await expect.poll(() => collectionRequests.length).toBeGreaterThan(1);
  await page.getByRole('link', { name: 'Privacy Policy' }).click();
  await expect(page).toHaveURL('/privacy');
  await expect.poll(() => page.evaluate(() => JSON.stringify(window.dataLayer || []))).toContain('/privacy');
  const queue = await page.evaluate(() => JSON.stringify(window.dataLayer || []));
  expect(queue).toContain('/privacy');
  expect(queue).not.toContain('?');
  await page.getByRole('button', { name: 'Analytics Preferences' }).click();
  await page.getByRole('button', { name: 'Only necessary' }).click();
  await expect.poll(() => page.evaluate(() => !document.cookie.includes('_ga=') && !document.cookie.includes('_fbp='))).toBe(true);
  const afterWithdrawal = collectionRequests.length;
  await page.getByRole('link', { name: 'Help & Support' }).click();
  await expect(page).toHaveURL('/help');
  expect(collectionRequests).toHaveLength(afterWithdrawal);
  await page.getByRole('button', { name: 'Analytics Preferences' }).click();
  await page.getByRole('button', { name: 'Allow analytics' }).click();
  await expect.poll(() => collectionRequests.length).toBeGreaterThan(afterWithdrawal);
});

test('never initializes trackers on sensitive routes', async ({ page }) => {
  const trackerRequests: string[] = [];
  await page.addInitScript(() => localStorage.setItem('vibe4you_analytics_consent_v1', 'accepted'));
  page.on('request', request => { if (/googletagmanager\.com|connect\.facebook\.net/.test(request.url())) trackerRequests.push(request.url()); });
  await page.goto('/reset-password#token=must-not-leak');
  await expect(page).toHaveURL('/reset-password');
  expect(trackerRequests).toEqual([]);
  await page.goto('/order-success/ORDER-PRIVATE-12345');
  expect(trackerRequests).toEqual([]);
  const queue = await page.evaluate(() => JSON.stringify(window.dataLayer || []));
  expect(queue).not.toContain('ORDER-PRIVATE-12345');
  expect(queue).not.toContain('must-not-leak');
});
