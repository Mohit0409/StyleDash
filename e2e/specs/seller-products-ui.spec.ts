import { expect, test } from '@playwright/test';

test('approved shop owner can draft and submit but cannot publish a product', async ({ page }) => {
  let product: Record<string, unknown> | null = null;
  let createPayload: Record<string, unknown> | null = null;
  let uploadedImageData: Buffer | null = null;
  let uploadCount = 0;

  await page.route('**/media/product-images/**', async route => {
    await route.fulfill({ status: 200, contentType: 'image/webp', body: uploadedImageData || Buffer.alloc(0) });
  });

  await page.route('**/api/**', async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const method = request.method();
    const json = (body: unknown, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });

    if (path === '/api/auth/me') {
      await json({ success: true, csrfToken: 'csrf-e2e', user: { uid: 'seller-1', name: 'Seller E2E', email: 'seller@example.test', role: 'customer' } });
      return;
    }
    if (path === '/api/vendor-applications/me' && method === 'GET') {
      await json({ success: true, application: {
        id: 'shop-1', status: 'ACTIVE', shopName: 'E2E Active Shop', ownerName: 'Seller E2E',
        registeredEmail: 'seller@example.test', category: 'Clothing & Fashion', description: 'Active test shop',
        address: 'Main market', city: 'Neemuch', state: 'Madhya Pradesh', pincode: '458441',
        createdAt: '2026-08-20T00:00:00Z', updatedAt: '2026-08-20T00:00:00Z',
      } });
      return;
    }
    if (path === '/api/shop-products' && method === 'GET') {
      await json({ success: true, products: product ? [product] : [] });
      return;
    }
    if (path === '/api/shop-product-requests' && method === 'GET') {
      await json({ success: true, requests: [] });
      return;
    }
    if (path === '/api/shop-product-images' && method === 'POST') {
      const upload = request.postDataJSON() as Record<string, unknown>;
      expect(upload.contentType).toBe('image/webp');
      expect(typeof upload.dataBase64).toBe('string');
      uploadedImageData = Buffer.from(String(upload.dataBase64), 'base64');
      uploadCount += 1;
      const digest = String(uploadCount).padStart(32, '0');
      await json({ success: true, image: { url: `/media/product-images/${digest}.webp`, bytes: uploadedImageData.length, contentType: 'image/webp' } }, 201);
      return;
    }
    if (path === '/api/shop-products' && method === 'POST') {
      createPayload = request.postDataJSON() as Record<string, unknown>;
      product = {
        ...createPayload, id: 'shopprod_1', slug: 'local-product-shopprod-1', applicationId: 'shop-1',
        status: 'DRAFT', createdAt: '2026-08-20T00:00:00Z', updatedAt: '2026-08-20T00:00:00Z',
      };
      await json({ success: true, product }, 201);
      return;
    }
    if (path === '/api/shop-products/shopprod_1/submit' && method === 'POST') {
      product = { ...(product || {}), status: 'SUBMITTED', submittedAt: '2026-08-20T00:01:00Z' };
      await json({ success: true, product });
      return;
    }
    await json({ success: false, error: 'Unexpected mocked API request.' }, 500);
  });

  await page.goto('/partner');
  await expect(page.getByRole('heading', { name: 'Shop Active', exact: true }).first()).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Product submissions' })).toBeVisible();

  await page.getByRole('button', { name: 'New Product Draft' }).click();
  await page.getByLabel('Product name').fill('Local Product');
  await page.getByLabel('Description').fill('A locally submitted product for private review.');
  await page.getByLabel('Price (INR)', { exact: true }).fill('500');
  await page.getByLabel('Original price (INR)').fill('600');
  await page.getByPlaceholder('Size, e.g. S or XL').fill('M');
  await page.getByPlaceholder('Stock').fill('2');
  await page.getByRole('button', { name: '+ Add size' }).click();
  await page.getByPlaceholder('Size, e.g. S or XL').nth(1).fill('L');
  await page.getByPlaceholder('Stock').nth(1).fill('3');
  await page.getByLabel('Colour name').fill('Black');
  await page.getByPlaceholder('Size, e.g. S or XL').nth(1).fill('M');
  await page.getByRole('button', { name: 'Save Product Draft' }).click();
  await expect(page.getByRole('alert')).toContainText('Each size can appear only once');
  await page.getByPlaceholder('Size, e.g. S or XL').nth(1).fill('L');
  await expect(page.getByRole('radio', { name: 'Image link' })).toHaveAttribute('aria-checked', 'true');
  await expect(page.getByLabel('HTTPS image URLs')).toBeVisible();
  await page.getByRole('radio', { name: 'Image upload' }).click();
  await expect(page.getByLabel('HTTPS image URLs')).toHaveCount(0);
  const tinyPng = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=', 'base64');
  await page.getByLabel('Upload product images').setInputFiles([
    { name: 'local-product-1.png', mimeType: 'image/png', buffer: tinyPng },
    { name: 'local-product-2.png', mimeType: 'image/png', buffer: tinyPng },
  ]);
  await expect(page.getByText(/2 images optimized and uploaded/)).toBeVisible();
  await expect(page.getByAltText('Uploaded product image 1 preview')).toBeVisible();
  await expect(page.getByAltText('Uploaded product image 2 preview')).toBeVisible();
  await expect(page.getByText('MAIN', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Move uploaded image 2 left' }).click();
  await page.getByRole('radio', { name: 'Image link' }).click();
  await expect(page.getByLabel('HTTPS image URLs')).toHaveValue('');
  await page.getByRole('radio', { name: 'Image upload' }).click();
  await expect(page.getByAltText('Uploaded product image 1 preview')).toBeVisible();
  await page.getByRole('button', { name: 'Save Product Draft' }).click();

  await expect(page.getByRole('heading', { name: 'Local Product' })).toBeVisible();
  await expect(page.getByText('Draft', { exact: true })).toBeVisible();
  expect(createPayload).not.toHaveProperty('status');
  expect(createPayload).not.toHaveProperty('applicationId');
  expect(createPayload?.variants).toEqual([{ size: 'M', inventory: 2 }, { size: 'L', inventory: 3 }]);
  expect(createPayload?.imageUrls).toEqual([
    '/media/product-images/00000000000000000000000000000002.webp',
    '/media/product-images/00000000000000000000000000000001.webp',
  ]);

  const draftCard = page.getByRole('article').filter({ has: page.getByRole('heading', { name: 'Local Product' }) });
  await draftCard.getByRole('button', { name: 'Edit', exact: true }).click();
  await expect(page.getByRole('radio', { name: 'Image upload' })).toHaveAttribute('aria-checked', 'true');
  await expect(page.getByLabel('HTTPS image URLs')).toHaveCount(0);
  await expect(page.getByAltText('Uploaded product image 1 preview')).toBeVisible();
  await page.getByRole('button', { name: 'Cancel', exact: true }).click();

  await page.getByRole('button', { name: 'Submit', exact: true }).click();
  await expect(draftCard.getByText('In review', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: /publish/i })).toHaveCount(0);
});


test('published seller can update stock and submit edit or unpublish requests without direct publish powers', async ({ page }) => {
  let requests: Array<Record<string, unknown>> = [];
  let editPayload: Record<string, unknown> | null = null;
  let stockPayload: Record<string, unknown> | null = null;
  let unpublishPayload: Record<string, unknown> | null = null;
  const products: Array<Record<string, unknown>> = [
    {
      id: 'shopprod_edit', slug: 'edit-live', applicationId: 'shop-1', status: 'PUBLISHED',
      name: 'Editable Live Product', description: 'Published product that can request reviewed catalogue changes.',
      brand: 'Local', department: 'women', category: 'Clothing & Fashion',
      pricePaise: 50000, originalPricePaise: 60000, inventory: 6, size: 'M, S, L',
      colourName: 'Black', colourHex: '#000000', imageUrls: ['https://pngtree.com/freepng/legacy-product.html', '/media/product-images/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.webp'],
      attributes: {}, variants: [
        { id: 'shopprod_edit-var-1', size: 'M', inventory: 2 },
        { id: 'shopprod_edit-var-2', size: 'S', inventory: 1 },
        { id: 'shopprod_edit-var-3', size: 'L', inventory: 3 },
      ], createdAt: '2026-08-20T00:00:00Z', updatedAt: '2026-08-20T00:00:00Z',
    },
    {
      id: 'shopprod_remove', slug: 'remove-live', applicationId: 'shop-1', status: 'PUBLISHED',
      name: 'Unpublish Live Product', description: 'Published product that can request administrator unpublishing.',
      brand: 'Local', department: 'women', category: 'Clothing & Fashion',
      pricePaise: 70000, originalPricePaise: 80000, inventory: 0, size: 'L',
      colourName: 'Blue', colourHex: '#0000FF', imageUrls: ['https://example.test/remove.jpg'],
      attributes: {}, variants: [{ id: 'shopprod_remove-var-1', size: 'L', inventory: 0 }], createdAt: '2026-08-20T00:00:00Z', updatedAt: '2026-08-20T00:00:00Z',
    },
  ];

  await page.route('**/media/product-images/**', async route => {
    await route.fulfill({ status: 200, contentType: 'image/webp', body: Buffer.alloc(8) });
  });

  await page.route('**/api/**', async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const method = request.method();
    const json = (body: unknown, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
    if (path === '/api/auth/me') return void await json({ success: true, csrfToken: 'csrf-live', user: { uid: 'seller-1', name: 'Seller E2E', email: 'seller@example.test', role: 'customer' } });
    if (path === '/api/vendor-applications/me' && method === 'GET') return void await json({ success: true, application: {
      id: 'shop-1', status: 'ACTIVE', shopName: 'E2E Active Shop', ownerName: 'Seller E2E',
      registeredEmail: 'seller@example.test', category: 'Clothing & Fashion', description: 'Active test shop',
      address: 'Main market', city: 'Neemuch', state: 'Madhya Pradesh', pincode: '458441',
      createdAt: '2026-08-20T00:00:00Z', updatedAt: '2026-08-20T00:00:00Z',
    } });
    if (path === '/api/shop-products' && method === 'GET') return void await json({ success: true, products });
    if (path === '/api/shop-product-requests' && method === 'GET') return void await json({ success: true, requests });
    if (path === '/api/shop-products/shopprod_edit/stock' && method === 'PATCH') {
      stockPayload = request.postDataJSON() as Record<string, unknown>;
      const variants = (products[0].variants as Array<Record<string, unknown>>).map(variant =>
        variant.id === 'shopprod_edit-var-1' ? { ...variant, inventory: stockPayload?.stock } : variant
      );
      products[0] = { ...products[0], inventory: variants.reduce((total, variant) => total + Number(variant.inventory), 0), variants };
      return void await json({ success: true, inventory: { productId: 'shopprod_edit', variantId: 'shopprod_edit-var-1', before: 2, stock: stockPayload.stock } });
    }
    if (path === '/api/shop-products/shopprod_edit/edit-request' && method === 'POST') {
      editPayload = request.postDataJSON() as Record<string, unknown>;
      const change = {
        id: 'shopchg_edit', productId: 'shopprod_edit', applicationId: 'shop-1', productName: 'Editable Live Product',
        action: 'EDIT', status: 'SUBMITTED', proposedProduct: editPayload,
        createdAt: '2026-08-24T00:00:00Z', updatedAt: '2026-08-24T00:00:00Z', submittedAt: '2026-08-24T00:00:00Z',
      };
      requests = [change, ...requests];
      return void await json({ success: true, request: change }, 201);
    }
    if (path === '/api/shop-products/shopprod_remove/unpublish-request' && method === 'POST') {
      unpublishPayload = request.postDataJSON() as Record<string, unknown>;
      const change = {
        id: 'shopchg_remove', productId: 'shopprod_remove', applicationId: 'shop-1', productName: 'Unpublish Live Product',
        action: 'UNPUBLISH', status: 'SUBMITTED', proposedProduct: null,
        createdAt: '2026-08-24T00:00:00Z', updatedAt: '2026-08-24T00:00:00Z', submittedAt: '2026-08-24T00:00:00Z',
      };
      requests = [change, ...requests];
      return void await json({ success: true, request: change }, 201);
    }
    await json({ success: false, error: `Unexpected mocked API request: ${method} ${path}` }, 500);
  });

  await page.goto('/partner');

  await expect(page.getByRole('button', { name: /1\s+Live/i })).toBeVisible();
  await expect(page.getByRole('button', { name: /1\s+Out of stock/i })).toBeVisible();
  await page.getByLabel('Filter products by status').selectOption('out');
  await expect(page.getByRole('heading', { name: 'Unpublish Live Product' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Editable Live Product' })).toHaveCount(0);
  await page.getByLabel('Filter products by status').selectOption('all');
  await page.getByLabel('Search your products').fill('Editable');
  await expect(page.getByRole('heading', { name: 'Editable Live Product' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Unpublish Live Product' })).toHaveCount(0);
  await page.getByLabel('Search your products').fill('');

  const editCard = page.getByRole('article').filter({ has: page.getByRole('heading', { name: 'Editable Live Product' }) });
  await editCard.getByRole('button', { name: 'M Stock' }).click();
  await editCard.getByLabel('Stock for size M').fill('0');
  await editCard.getByRole('button', { name: 'Save stock' }).click();
  await expect(editCard.getByText('M: 0', { exact: true })).toBeVisible();
  expect(stockPayload).toEqual({ variantId: 'shopprod_edit-var-1', stock: 0 });

  await editCard.getByRole('button', { name: 'Edit Listing' }).click();
  await expect(page.getByRole('heading', { name: 'Request Listing Changes' })).toBeVisible();
  await expect(page.getByRole('radio', { name: 'Image upload' })).toHaveAttribute('aria-checked', 'true');
  await expect(page.getByLabel('HTTPS image URLs')).toHaveCount(0);
  await expect(page.getByAltText('Uploaded product image 1 preview')).toBeVisible();
  await page.getByLabel('Product name').fill('Reviewed Live Product');
  await expect(page.getByLabel('Size 1')).toHaveAttribute('readonly', '');
  await expect(page.getByLabel('Stock for size M')).toHaveAttribute('readonly', '');
  await page.getByRole('button', { name: 'Remove size S' }).click();
  await expect(page.getByRole('alert')).toContainText('Set stock for size S to 0');
  await page.getByRole('button', { name: 'Remove size M' }).click();
  await expect(page.getByLabel('Size 1')).toHaveValue('S');
  await page.getByRole('button', { name: '+ Add size' }).click();
  await page.getByLabel('Size 3', { exact: true }).fill('XL');
  await page.getByLabel('Stock for size XL').fill('4');
  await page.getByRole('button', { name: 'Submit Listing Changes' }).click();
  await expect(editCard.getByText(/EDIT request submitted/i)).toBeVisible();
  expect(editPayload).not.toHaveProperty('inventory');
  expect(editPayload?.name).toBe('Reviewed Live Product');
  expect(editPayload?.variants).toEqual([
    { id: 'shopprod_edit-var-2', size: 'S', inventory: 1 },
    { id: 'shopprod_edit-var-3', size: 'L', inventory: 3 },
    { size: 'XL', inventory: 4 },
  ]);
  expect(editPayload?.imageUrls).toEqual(['/media/product-images/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.webp']);
  await expect(editCard.getByRole('button', { name: 'Edit Listing' })).toHaveCount(0);
  await expect(editCard.getByRole('button', { name: 'Request Unpublish' })).toHaveCount(0);

  const removeCard = page.getByRole('article').filter({ has: page.getByRole('heading', { name: 'Unpublish Live Product' }) });
  await removeCard.getByRole('button', { name: 'Request Unpublish' }).click();
  await removeCard.getByRole('button', { name: 'Confirm unpublish request' }).click();
  await expect(removeCard.getByText(/UNPUBLISH request submitted/i)).toBeVisible();
  expect(unpublishPayload).toEqual({});
  await expect(page.getByRole('button', { name: /publish/i })).toHaveCount(0);
});
