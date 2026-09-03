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

const USER_A: E2EUser = {
  name: 'E2E Commerce Customer A',
  email: 'e2e-commerce-a@example.test',
  phone: '9876543210',
  password: PASSWORD,
};

const USER_B: E2EUser = {
  name: 'E2E Commerce Customer B',
  email: 'e2e-commerce-b@example.test',
  phone: '9876543211',
  password: PASSWORD,
};

test.beforeAll(async () => {
  const api = await playwrightRequest.newContext({
    baseURL: 'http://127.0.0.1:4173',
    extraHTTPHeaders: { 'X-Forwarded-For': '198.51.100.12' },
  });

  try {
    for (const user of [USER_A, USER_B]) {
      const response = await api.post('/api/auth/register', {
        data: {
          name: user.name,
          email: user.email,
          phone: user.phone,
          password: user.password,
        },
      });

      if (response.status() === 409) {
        const login = await api.post('/api/auth/login', {
          data: { email: user.email, password: user.password },
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
) {
  await page.goto('/login');

  await page.getByPlaceholder('Email').fill(user.email);
  await page
    .getByPlaceholder('Password (8+ characters)')
    .fill(user.password);

  await page.getByRole('button', { name: 'Login' }).click();

  await expect(page).toHaveURL(/\/profile$/);
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

  // Account A's scoped data can exist in localStorage,
  // but must not be visible to account B.
  const scopedKeys = await page.evaluate(() =>
    Object.keys(localStorage).filter(
      key => key.startsWith('sd_wishlist_ids:'),
    ),
  );

  expect(scopedKeys.length).toBeGreaterThanOrEqual(1);
});
