import { expect, test } from '@playwright/test';

test('lower homepage uses bounded merchandising rows with View All links', async ({ page }) => {
  await page.goto('/');
  await page.waitForLoadState('networkidle');

  const merchandising = page.getByTestId('homepage-merchandising');
  await expect(merchandising).toBeVisible();

  const department = page.locator('section').filter({
    has: page.getByRole('heading', { name: 'Shop by Department' }),
  });
  const departmentBox = await department.boundingBox();
  const merchBox = await merchandising.boundingBox();
  expect(departmentBox && merchBox && merchBox.y >= departmentBox.y + departmentBox.height - 2).toBeTruthy();

  const expected = [
    ['express', 'Weekend Express Picks', '/products?filter=express'],
    ['new', 'New Drops', '/products?filter=new'],
    ['trending', 'Trending in Neemuch', '/products?sort=rating'],
    ['under499', 'Styles Under ₹499', '/products?maxPrice=499'],
    ['women', 'Women', '/products?dept=women'],
    ['men', 'Men', '/products?dept=men'],
    ['accessories', 'Accessories', '/products?category=Accessories'],
  ] as const;

  for (const [id, title, href] of expected) {
    const row = merchandising.locator(`[data-home-section="${id}"]`);
    await expect(merchandising.getByRole('heading', { name: title, exact: true })).toBeVisible();
    const viewAll = merchandising.locator(`a[href="${href}"]`).filter({ hasText: 'View All' });
    await expect(viewAll).toBeVisible();
    const productLinks = row.locator('a[href^="/product/"]');
    const uniqueProducts = new Set(await productLinks.evaluateAll(nodes => nodes.map(node => node.getAttribute('href'))));
    expect(uniqueProducts.size).toBeLessThanOrEqual(5);
    expect(uniqueProducts.size).toBeGreaterThan(0);
  }

  const beauty = merchandising.locator('[data-home-section="beauty"]');
  if (await beauty.count()) {
    const beautyLinks = beauty.locator('a[href^="/product/"]');
    expect(new Set(await beautyLinks.evaluateAll(nodes => nodes.map(node => node.getAttribute('href')))).size).toBeLessThanOrEqual(5);
  }

  const stores = merchandising.locator('[data-home-section="stores"]');
  if (await stores.count()) {
    expect(new Set(await stores.locator('a[href^="/store/"]').evaluateAll(nodes => nodes.map(node => node.getAttribute('href')))).size).toBeLessThanOrEqual(5);
  }
});


test('homepage merchandising stays usable from mobile through TV-sized viewports', async ({ page }) => {
  const viewports = [
    { width: 390, height: 844 },
    { width: 1366, height: 768 },
    { width: 1920, height: 1080 },
    { width: 2560, height: 1440 },
  ];

  for (const viewport of viewports) {
    await page.setViewportSize(viewport);
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    const merchandising = page.getByTestId('homepage-merchandising');
    await expect(merchandising).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow).toBeLessThanOrEqual(1);
    const firstRow = merchandising.locator('[data-home-section]').first();
    const box = await firstRow.boundingBox();
    expect(box?.width || 0).toBeGreaterThan(250);
  }
});
