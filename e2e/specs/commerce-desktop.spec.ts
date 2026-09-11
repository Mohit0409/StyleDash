import { expect, Page, request as playwrightRequest, test } from '@playwright/test';

const PRODUCT_NAME = 'Pure Cotton Oversized Graphic Tee';
const PRODUCT_ROUTE =
  '/product/pure-cotton-oversized-graphic-tee-sd-prod-001';
const PASSWORD = 'E2E-only-password-2026!';

type E2EUser = {
  name: string;
  email: string;
  phone: string;
  password: string;
};

let USER_A: E2EUser;
let USER_B: E2EUser;
let USER_SYNC: E2EUser;

test.beforeEach(async ({ page }) => {
  // Keep commerce auth traffic isolated from other full-suite specs while still
  // exercising the real server rate limiter.
  await page.setExtraHTTPHeaders({ 'X-Forwarded-For': '198.51.100.40' });
});

test.beforeAll(async ({ browserName }, testInfo) => {
  void browserName;
  // Desktop and mobile projects intentionally share one isolated E2E server.
  // Scope identities to the project so the second project never creates a
  // duplicate account or exercises login rate limits as an accidental setup path.
  const projectSuffix = testInfo.project.name.replace(/[^a-z0-9]/gi, '-').toLowerCase();
  const phoneSuffix = testInfo.project.name === 'mobile-chromium' ? '12' : '10';
  USER_A = {
    name: `E2E Commerce Customer A ${projectSuffix}`,
    email: `e2e-commerce-a-${projectSuffix}@example.test`,
    phone: `98765432${phoneSuffix}`,
    password: PASSWORD,
  };
  USER_B = {
    name: `E2E Commerce Customer B ${projectSuffix}`,
    email: `e2e-commerce-b-${projectSuffix}@example.test`,
    phone: `98765433${phoneSuffix}`,
    password: PASSWORD,
  };
  USER_SYNC = {
    name: `E2E Commerce Sync Customer ${projectSuffix}`,
    email: `e2e-commerce-sync-${projectSuffix}@example.test`,
    phone: `98765434${phoneSuffix}`,
    password: PASSWORD,
  };
  const api = await playwrightRequest.newContext({
    baseURL: 'http://127.0.0.1:4173',
    extraHTTPHeaders: { 'X-Forwarded-For': '198.51.100.12' },
  });

  try {
    for (const user of [USER_A, USER_B, USER_SYNC]) {
      const response = await api.post('/api/auth/register', {
        data: {
          name: user.name,
          email: user.email,
          phone: user.phone,
          password: user.password,
          termsAccepted: true,
          termsVersion: '2026-08-14',
        },
      });

      // Playwright may restart the serial worker and encounter an already-created
      // user. Re-authenticate with current Terms consent so the fixture remains
      // restart-safe and compliant with the server-authoritative consent gate.
      if (response.status() === 409) {
        const login = await api.post('/api/auth/login', {
          data: { email: user.email, password: user.password, termsAccepted: true, termsVersion: '2026-08-14' },
        });
        expect(login.status()).toBe(200);
      } else {
        expect(response.status()).toBe(201);
      }
    }
  } finally {
    await api.dispose();
  }
});

async function loginCustomer(
  page: Page,
  user: E2EUser,
  resetAccountState = true,
) {
  await page.goto('/login');

  await page.getByPlaceholder('Email').fill(user.email);
  await page
    .getByPlaceholder('Password (8+ characters)')
    .fill(user.password);
  await page.getByRole('checkbox', { name: /agree to the terms/i }).check();

  await page.getByRole('button', { name: 'Login' }).click();
  await expect(page).toHaveURL(/\/profile$/);

  if (resetAccountState) {
    const statuses = await page.evaluate(async () => {
      const me = await fetch('/api/auth/me');
      const auth = await me.json();
      const headers = { 'Content-Type': 'application/json', 'X-CSRF-Token': auth.csrfToken };
      const cart = await fetch('/api/account-state/cart', {
        method: 'PATCH', headers, body: JSON.stringify({ items: [] }),
      });
      const wishlist = await fetch('/api/account-state/wishlist', {
        method: 'PATCH', headers, body: JSON.stringify({ productIds: [] }),
      });
      return [cart.status, wishlist.status];
    });
    expect(statuses).toEqual([200, 200]);
    await page.reload();
    await expect(page.getByRole('button', { name: /^Cart\s+0$/ })).toBeVisible();
  }
}

async function addKnownProduct(page: Page) {
  await page.goto(PRODUCT_ROUTE);

  await expect(
    page.getByRole('heading', { level: 1, name: PRODUCT_NAME, exact: true }),
  ).toBeVisible();

  await expect(
    page.getByText('In stock in Neemuch'),
  ).toBeVisible();

  const addButton = page.getByRole('button', {
    name: /Add to Cart/,
  });

  await expect(addButton).toBeEnabled();
  await addButton.click();

  await expect(
    page.getByRole('button', { name: /^Cart\s+\d+$/ }),
  ).toContainText('1');
}

async function prepareCheckout(page: Page, label: string) {
  await loginCustomer(page, USER_A);
  await addKnownProduct(page);

  await page.goto('/checkout');

  await expect(
    page.getByRole('heading', { name: 'Secure Checkout' }),
  ).toBeVisible();

  await page.getByLabel('Full Name').fill(`E2E ${label} Customer`);
  await page.getByLabel('Phone Number').fill('9876543210');
  await page
    .getByLabel('Street Address & Landmark')
    .fill('45 E2E Test Street, Neemuch');
  await expect(page.getByLabel('City')).toHaveValue('Neemuch');
  await expect(page.getByLabel('City')).toHaveAttribute('readonly', '');
  await expect(page.getByLabel('Pincode')).toHaveValue('458441');
  await expect(page.getByLabel('Pincode')).toHaveAttribute('readonly', '');
}

test('checkout enables Express and recalculates totals on a simulated Saturday', async ({ page }) => {
  await page.clock.install({ time: new Date('2026-09-05T06:30:00Z') });
  await prepareCheckout(page, 'weekend-express-selector');

  const sameDay = page.getByRole('radio', { name: /Same Day Delivery/ });
  const express = page.getByRole('radio', { name: /Express Delivery/ });
  const summary = page.getByRole('heading', { name: 'Order Summary' }).locator('..');

  await expect(sameDay).toBeChecked();
  await expect(express).toBeEnabled();
  await expect(summary.getByText('FREE', { exact: true })).toBeVisible();
  await expect(summary).toContainText('Product prices include GST.');
  await expect(summary.getByText(/GST Taxes/)).toHaveCount(0);

  await express.check();
  await expect(express).toBeChecked();
  await expect(summary.getByText('\u20b980', { exact: true })).toBeVisible();
  await expect(summary.getByText('About 60 minutes', { exact: true })).toBeVisible();
  await expect(page.getByText('Express selected. Delivery charge and estimated total have been recalculated below.')).toBeVisible();
});

test('checkout disables Express on a simulated Monday and keeps free Same Day Delivery', async ({ page }) => {
  await page.clock.install({ time: new Date('2026-09-07T06:30:00Z') });
  await prepareCheckout(page, 'weekday-normal-selector');

  const sameDay = page.getByRole('radio', { name: /Same Day Delivery/ });
  const express = page.getByRole('radio', { name: /Express Delivery/ });

  await expect(sameDay).toBeChecked();
  await expect(express).toBeDisabled();
  await expect(page.getByRole('status')).toContainText('Express Delivery is available Saturday and Sunday in Neemuch for every product.');
});
test('single-city launch fixes profile and checkout delivery area to Neemuch 458441', async ({ page }) => {
  await loginCustomer(page, USER_A);

  await page.goto('/profile');
  await expect(page.getByLabel('City')).toHaveValue('Neemuch');
  await expect(page.getByLabel('City')).toHaveAttribute('readonly', '');
  await expect(page.getByLabel('Pincode')).toHaveValue('458441');
  await expect(page.getByLabel('Pincode')).toHaveAttribute('readonly', '');
  await page.getByText('Street address and landmark').locator('input').fill('45 Single Zone Test Street');
  await page.getByRole('button', { name: 'Save profile' }).click();
  await expect(page.getByRole('status')).toHaveText('Profile and delivery address saved.');
  await expect(page.getByLabel('City')).toHaveValue('Neemuch');
  await expect(page.getByLabel('Pincode')).toHaveValue('458441');

  await addKnownProduct(page);
  await page.goto('/checkout');
  await expect(page.getByLabel('City')).toHaveValue('Neemuch');
  await expect(page.getByLabel('Pincode')).toHaveValue('458441');
  await expect(page.getByText('Vibe4You currently delivers only in Neemuch (458441).')).toBeVisible();
});

test('authoritative inventory exposes in-stock and out-of-stock variants', async ({
  request,
}) => {
  const availableResponse = await request.get(
    '/api/inventory/availability?variantId=sd-prod-001-var-1',
  );

  expect(availableResponse.status()).toBe(200);

  expect(await availableResponse.json()).toMatchObject({
    success: true,
    availability: [
      {
        variantId: 'sd-prod-001-var-1',
        available: true,
      },
    ],
  });

  const unavailableResponse = await request.get(
    '/api/inventory/availability?variantId=sd-prod-001-var-7',
  );

  expect(unavailableResponse.status()).toBe(200);

  expect(await unavailableResponse.json()).toMatchObject({
    success: true,
    availability: [
      {
        variantId: 'sd-prod-001-var-7',
        available: false,
      },
    ],
  });
});

test('product can enter cart only after authoritative inventory succeeds', async ({
  page,
}) => {
  await addKnownProduct(page);

  await page.getByRole('button', { name: /^Cart\s+\d+$/ }).click();

  const drawer = page.locator('div.fixed').filter({
    hasText: 'Your Cart',
  });

  await expect(drawer.getByText('Your Cart')).toBeVisible();

  await expect(
    drawer.getByText(PRODUCT_NAME, { exact: true }),
  ).toBeVisible();
});

test('product UI fails closed when inventory API is unavailable', async ({
  page,
}) => {
  await page.route(
    '**/api/inventory/availability*',
    route => route.abort(),
  );

  await page.goto(PRODUCT_ROUTE);

  await expect(
    page.getByRole('heading', { level: 1, name: PRODUCT_NAME, exact: true }),
  ).toBeVisible();

  await expect(
    page.getByText('Out of Stock for this variant'),
  ).toBeVisible();

  await expect(
    page.getByRole('button', { name: /Add to Cart/ }),
  ).toBeDisabled();

  await expect(
    page.getByRole('button', { name: 'Buy Now' }),
  ).toBeDisabled();
});

test('isolated COD order succeeds and another account cannot read it', async ({
  page,
}) => {
  await prepareCheckout(page, 'cod-owner-a');

  await expect(
    page.getByRole('radio', { name: /Cash \/ Pay on Delivery/ }),
  ).toBeChecked();

  await page
    .getByRole('button', { name: 'Place COD Order' })
    .click();

  await expect(page).toHaveURL(/\/order-success\/[^/?#]+$/);

  await expect(
    page.getByRole('heading', { name: 'Order Confirmed!' }),
  ).toBeVisible();

  // Wait for the account-scoped order API response to render fully.
  await expect(
    page.getByText('Order total'),
  ).toBeVisible();

  const orderId = decodeURIComponent(
    new URL(page.url()).pathname.split('/').pop() || '',
  );

  expect(orderId.length).toBeGreaterThan(0);

  await page.getByRole('link', { name: 'Track order' }).click();
  await expect(page).toHaveURL(/\/orders\/[^/?#]+\/track$/);
  await expect(page.getByRole('heading', { name: orderId })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Order items' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Download receipt' })).toHaveCount(0);

  await page.goto('/profile');

  await page.getByRole('button', { name: 'Logout' }).click();

  await expect(page).toHaveURL(/\/login$/);

  await loginCustomer(page, USER_B);

  const ownershipStatus = await page.evaluate(async id => {
    const response = await fetch(
      `/api/orders/${encodeURIComponent(id)}`,
      {
        credentials: 'include',
      },
    );

    return response.status;
  }, orderId);

  expect(ownershipStatus).toBe(404);
});

test('mocked Razorpay cancellation keeps checkout and cart intact', async ({
  page,
}) => {
  await prepareCheckout(page, 'payment-cancel');

  await page
    .getByRole('radio', { name: /UPI with Razorpay/ })
    .check();

  await page.route('**/api/create-order', async route => {
    const intent = route.request().postDataJSON();

    expect(intent.paymentMethod).toBe('upi');

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        styleDashOrderId: 'SD-E2E-CANCEL',
        razorpayOrderId: 'order_e2e_cancel',
        keyId: 'rzp_test_e2e_only',
        amount: 1000,
        currency: 'INR',
        receipt: 'e2e-cancel',
        trustedTotals: {
          subtotal: 473,
          discount: 0,
          deliveryFee: 0,
          taxes: 24,
          grandTotal: 497,
        },
      }),
    });
  });

  let verifyCalled = false;

  await page.route('**/api/verify-payment', async route => {
    verifyCalled = true;
    await route.abort();
  });

  await page.evaluate(() => {
    class CancelledRazorpay {
      private options: any;

      constructor(options: any) {
        this.options = options;
      }

      on() {
        // Cancellation is triggered by modal dismissal.
      }

      open() {
        this.options.modal.ondismiss();
      }
    }

    (window as unknown as { Razorpay: unknown }).Razorpay =
      CancelledRazorpay;
  });

  await page.getByRole('button', { name: /^Pay / }).click();

  await expect(page.getByRole('alert')).toHaveText(
    'Payment was cancelled.',
  );

  await expect(page).toHaveURL(/\/checkout$/);

  await expect(
    page.getByText(PRODUCT_NAME, { exact: true }),
  ).toBeVisible();

  expect(verifyCalled).toBe(false);
});

test('mocked Razorpay failure does not verify or clear the cart', async ({
  page,
}) => {
  await prepareCheckout(page, 'payment-failure');

  await page
    .getByRole('radio', { name: /Credit \/ Debit Card with Razorpay/ })
    .check();

  await page.route('**/api/create-order', async route => {
    const intent = route.request().postDataJSON();

    expect(intent.paymentMethod).toBe('card');

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        styleDashOrderId: 'SD-E2E-FAILED',
        razorpayOrderId: 'order_e2e_failed',
        keyId: 'rzp_test_e2e_only',
        amount: 1000,
        currency: 'INR',
        receipt: 'e2e-failed',
        trustedTotals: {
          subtotal: 473,
          discount: 0,
          deliveryFee: 0,
          taxes: 24,
          grandTotal: 497,
        },
      }),
    });
  });

  let verifyCalled = false;

  await page.route('**/api/verify-payment', async route => {
    verifyCalled = true;
    await route.abort();
  });

  await page.evaluate(() => {
    class FailedRazorpay {
      private failureHandler?: (response: unknown) => void;

      constructor(_options: unknown) {}

      on(
        event: string,
        handler: (response: unknown) => void,
      ) {
        if (event === 'payment.failed') {
          this.failureHandler = handler;
        }
      }

      open() {
        this.failureHandler?.({
          error: {
            description: 'E2E simulated payment decline',
          },
        });
      }
    }

    (window as unknown as { Razorpay: unknown }).Razorpay =
      FailedRazorpay;
  });

  await page.getByRole('button', { name: /^Pay / }).click();

  await expect(page.getByRole('alert')).toHaveText(
    'E2E simulated payment decline',
  );

  await expect(page).toHaveURL(/\/checkout$/);

  await expect(
    page.getByText(PRODUCT_NAME, { exact: true }),
  ).toBeVisible();

  expect(verifyCalled).toBe(false);
});

test('authenticated vendor application persists through the real local API', async ({
  page,
}) => {
  await loginCustomer(page, USER_A);

  await page.goto('/partner');

  await expect(
    page.getByRole('heading', {
      name: 'Start Shop Application',
    }),
  ).toBeVisible();

  await page
    .getByPlaceholder('e.g. Royal Fashion Boutique')
    .fill('E2E Fashion Store');

  await page
    .getByPlaceholder('e.g. Ramesh Kumar')
    .fill('E2E Vendor Owner');

  await page
    .getByPlaceholder('Street, market, landmark')
    .fill('45 E2E Main Market, Neemuch');

  await page
    .getByPlaceholder(
      /Describe your shop/,
    )
    .fill(
      'E2E-only test inventory description for automated launch validation.',
    );

  await page
    .getByRole('button', {
      name: 'Save Draft',
    })
    .click();

  await expect(
    page.getByRole('heading', {
      name: 'Continue Application',
    }).first(),
  ).toBeVisible();

  await page
    .getByPlaceholder(/Describe your shop/)
    .fill('Corrected E2E-only inventory description saved in the authenticated draft.');

  await page.getByRole('button', { name: 'Save Draft' }).click();
  await expect(page.getByRole('status')).toContainText('Draft saved');

  await page.getByRole('button', { name: 'Submit for Review' }).click();

  await expect(
    page.getByRole('heading', { name: 'Application Submitted', exact: true }).first(),
  ).toBeVisible();
  await expect(page.getByText(/not publicly active/i).first()).toBeVisible();
});


test('wishlist remains isolated between authenticated accounts in the same browser', async ({
  page,
}) => {
  await loginCustomer(page, USER_A);

  await page.goto(PRODUCT_ROUTE);

  await expect(
    page.getByRole('heading', {
      level: 1,
      name: PRODUCT_NAME,
      exact: true,
    }),
  ).toBeVisible();

  // Product-detail wishlist control is the unlabeled button beside Buy Now.
  const detailActions = page.locator(
    'div.flex.gap-4.pt-4',
  );

  const wishlistButton = detailActions.getByRole('button').last();

  await wishlistButton.click();

  await page.goto('/wishlist');

  await expect(
    page.getByRole('heading', {
      name: 'Saved Wishlist (1)',
    }),
  ).toBeVisible();

  await expect(
    page.getByText(PRODUCT_NAME, { exact: true }),
  ).toBeVisible();

  // Switch accounts without clearing browser localStorage.
  await page.goto('/profile');

  await page.getByRole('button', { name: 'Logout' }).click();

  await expect(page).toHaveURL(/\/login$/);

  await loginCustomer(page, USER_B);

  await page.goto('/wishlist');

  await expect(
    page.getByRole('heading', {
      name: 'Saved Wishlist (0)',
    }),
  ).toBeVisible();

  await expect(
    page.getByText(PRODUCT_NAME, { exact: true }),
  ).toHaveCount(0);

  // Switching back proves Account A's wishlist is server-backed,
  // not merely retained in this browser's localStorage.
  await page.goto('/profile');
  await page.getByRole('button', { name: 'Logout' }).click();
  await loginCustomer(page, USER_A, false);
  await page.goto('/wishlist');
  await expect(page.getByRole('heading', { name: 'Saved Wishlist (1)' })).toBeVisible();
  await expect(page.getByText(PRODUCT_NAME, { exact: true })).toBeVisible();
});


test('same account cart and wishlist sync across isolated browser contexts', async ({ browser }) => {
  const contextA = await browser.newContext({ extraHTTPHeaders: { 'X-Forwarded-For': '198.51.100.21' } });
  const contextB = await browser.newContext({ extraHTTPHeaders: { 'X-Forwarded-For': '198.51.100.22' } });
  const pageA = await contextA.newPage();
  const pageB = await contextB.newPage();

  try {
    await loginCustomer(pageA, USER_SYNC);
    await pageA.goto(PRODUCT_ROUTE);
    const cartSaved = pageA.waitForResponse(response =>
      response.url().endsWith('/api/account-state/cart') && response.request().method() === 'PATCH' && response.status() === 200,
    );
    await addKnownProduct(pageA);
    await cartSaved;

    const detailActions = pageA.locator('div.flex.gap-4.pt-4');
    const wishlistSaved = pageA.waitForResponse(response =>
      response.url().endsWith('/api/account-state/wishlist') && response.request().method() === 'PATCH' && response.status() === 200,
    );
    await detailActions.getByRole('button').last().click();
    await wishlistSaved;
    await loginCustomer(pageB, USER_SYNC, false);
    await pageB.goto('/wishlist');
    await expect(pageB.getByRole('heading', { name: 'Saved Wishlist (1)' })).toBeVisible();
    await expect(pageB.getByText(PRODUCT_NAME, { exact: true })).toBeVisible();

    await pageB.goto(PRODUCT_ROUTE);
    await expect(pageB.getByRole('button', { name: /^Cart\s+\d+$/ })).toContainText('1');
    await pageB.getByRole('button', { name: /^Cart\s+\d+$/ }).click();
    await expect(pageB.getByRole('dialog', { name: 'Your Cart' })).toBeVisible();
    await expect(pageB.getByRole('dialog', { name: 'Your Cart' }).getByText(PRODUCT_NAME, { exact: true })).toBeVisible();
  } finally {
    await contextA.close();
    await contextB.close();
  }
});


test('already-open second browser refreshes cart without writing stale state back', async ({ browser }) => {
  const contextA = await browser.newContext({ extraHTTPHeaders: { 'X-Forwarded-For': '198.51.100.21' } });
  const contextB = await browser.newContext({ extraHTTPHeaders: { 'X-Forwarded-For': '198.51.100.22' } });
  const pageA = await contextA.newPage();
  const pageB = await contextB.newPage();

  try {
    await loginCustomer(pageA, USER_SYNC);
    await loginCustomer(pageB, USER_SYNC, false);
    await pageB.goto(PRODUCT_ROUTE);
    await expect(pageB.getByRole('button', { name: /^Cart\s+0$/ })).toBeVisible();

    let browserBCartPatches = 0;
    pageB.on('request', request => {
      if (request.url().endsWith('/api/account-state/cart') && request.method() === 'PATCH') browserBCartPatches += 1;
    });

    await pageA.goto(PRODUCT_ROUTE);
    const saved = pageA.waitForResponse(r => r.url().endsWith('/api/account-state/cart') && r.request().method() === 'PATCH' && r.status() === 200);
    await addKnownProduct(pageA);
    await saved;

    await pageB.evaluate(() => window.dispatchEvent(new Event('focus')));
    await expect(pageB.getByRole('button', { name: /^Cart\s+1$/ })).toBeVisible();
    await pageB.waitForTimeout(250);
    expect(browserBCartPatches).toBe(0);

    const serverCount = await pageB.evaluate(async () => {
      const response = await fetch('/api/account-state');
      const state = await response.json() as { cart: Array<{ quantity: number }> };
      return state.cart.reduce((sum, line) => sum + line.quantity, 0);
    });
    expect(serverCount).toBe(1);
  } finally {
    await contextA.close();
    await contextB.close();
  }
});


test('guest cart and wishlist migrate into the signed-in account', async ({ page, request }) => {
  const user: E2EUser = {
    name: 'E2E Guest Migration Customer',
    email: 'e2e-guest-migration@example.test',
    phone: '9876543599',
    password: PASSWORD,
  };
  const registered = await request.post('/api/auth/register', { data: {
    name: user.name, email: user.email, phone: user.phone, password: user.password,
    termsAccepted: true, termsVersion: '2026-08-14',
  }});
  expect(registered.status()).toBe(201);

  // Seed legacy guest convenience state directly so this migration test is
  // independent of inventory consumed by earlier full-suite order scenarios.
  await page.goto('/');
  await page.evaluate(() => {
    localStorage.setItem('sd_cart_v2', JSON.stringify([
      { productId: 'sd-prod-001', variantId: 'sd-prod-001-var-1', quantity: 1 },
    ]));
    localStorage.setItem('sd_wishlist_ids', JSON.stringify(['sd-prod-001']));
  });
  await expect.poll(async () => page.evaluate(() => Boolean(
    localStorage.getItem('sd_cart_v2') && localStorage.getItem('sd_wishlist_ids'),
  ))).toBe(true);
  const cartMigrated = page.waitForResponse(r => r.url().endsWith('/api/account-state/cart') && r.request().method() === 'PATCH' && r.status() === 200);
  const wishlistMigrated = page.waitForResponse(r => r.url().endsWith('/api/account-state/wishlist') && r.request().method() === 'PATCH' && r.status() === 200);
  await loginCustomer(page, user, false);
  await Promise.all([cartMigrated, wishlistMigrated]);

  await expect.poll(async () => page.evaluate(() => ({
    cart: localStorage.getItem('sd_cart_v2'),
    wishlist: localStorage.getItem('sd_wishlist_ids'),
  }))).toEqual({ cart: null, wishlist: null });

  await page.goto('/wishlist');
  await expect(page.getByRole('heading', { name: 'Saved Wishlist (1)' })).toBeVisible();
  await page.goto(PRODUCT_ROUTE);
  await expect(page.getByRole('button', { name: /^Cart\s+\d+$/ })).toContainText('1');
});
