import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e/specs',

  // Shared local SQLite/payment state => deliberately serial.
  fullyParallel: false,
  workers: 1,

  retries: 0,
  timeout: 30_000,
  expect: {
    timeout: 8_000,
  },

  outputDir: 'test-results',

  globalTeardown: './e2e/global-teardown.mjs',

  reporter: [
    ['list'],
    ['html', { outputFolder: 'playwright-report', open: 'never' }],
  ],

  use: {
    baseURL: 'http://127.0.0.1:4173',
    headless: true,

    // Do not create browser videos or traces containing auth/test data.
    video: 'off',
    trace: 'off',
    screenshot: 'only-on-failure',
  },

  webServer: {
    command: 'node e2e/start-server.mjs',
    url: 'http://127.0.0.1:4173/api/health',
    reuseExistingServer: false,
    timeout: 120_000,
  },

  projects: [
    {
      name: 'desktop-chromium',
      testIgnore: /mobile\.spec\.ts/,
      use: {
        ...devices['Desktop Chrome'],
        extraHTTPHeaders: { 'X-Forwarded-For': '198.51.100.10' },
      },
    },
    {
      name: 'mobile-chromium',
      testIgnore: /(serviceability|commerce-desktop)\.spec\.ts/,
      use: {
        ...devices['Pixel 7'],
        extraHTTPHeaders: { 'X-Forwarded-For': '198.51.100.11' },
      },
    },
  ],
});
