import { test, expect } from '@playwright/test';
import { spawn, spawnSync, type ChildProcess } from 'node:child_process';
import crypto from 'node:crypto';
import { existsSync, mkdirSync, mkdtempSync, rmSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const root = process.cwd();
const onePixelPng = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=', 'base64');
let adminProcess: ChildProcess | undefined;
let runtimeDirectory = '';

const resolvePython = () => {
  const candidates = [
    process.env.STYLEDASH_E2E_PYTHON,
    path.resolve(root, '.venv', 'Scripts', 'python.exe'),
    path.resolve(root, '..', '..', '.venv', 'Scripts', 'python.exe'),
  ].filter((value): value is string => Boolean(value));
  return candidates.find(candidate => existsSync(candidate)) ||
    (process.platform === 'win32' ? 'python' : 'python3');
};

const waitForAdmin = async () => {
  for (let attempt = 0; attempt < 80; attempt += 1) {
    try {
      const response = await fetch('http://127.0.0.1:8081/');
      if (response.ok) return;
    } catch {
      // Retry while the private admin server is starting.
    }
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  throw new Error('Private admin server did not become ready.');
};

test.beforeAll(async () => {
  runtimeDirectory = mkdtempSync(path.join(os.tmpdir(), 'vibe4you-admin-csp-'));
  const dataDirectory = path.join(runtimeDirectory, 'data');
  mkdirSync(dataDirectory, { recursive: true });
  const key = crypto.randomBytes(32).toString('base64').replace(/\+/g, '-').replace(/\//g, '_');
  const env = { ...process.env, RAZORPAY_MODE: 'test', PYTHONUTF8: '1' };
  for (const name of Object.keys(env)) {
    if (name.startsWith('RAZORPAY_') || name.startsWith('STYLEDASH_SMTP_')) delete env[name];
  }
  Object.assign(env, { RAZORPAY_MODE: 'test', STYLEDASH_TOTP_ENCRYPTION_KEY: key });
  adminProcess = spawn(resolvePython(), [
    path.join(root, 'scripts', 'termux-admin-server.py'),
    '--bind', '127.0.0.1', '--port', '8081',
    '--database', path.join(runtimeDirectory, 'styledash.db'),
    '--catalog', path.join(root, 'server', 'payment-data', 'catalog.json'),
    '--settings', path.join(root, 'server', 'payment-data', 'settings.json'),
    '--data-dir', dataDirectory,
    '--assets', path.join(root, 'server', 'admin'),
  ], { cwd: root, env, stdio: ['ignore', 'pipe', 'pipe'] });
  await waitForAdmin();
});

test.afterAll(() => {
  if (adminProcess?.pid && process.platform === 'win32') {
    spawnSync(path.join(process.env.SystemRoot || 'C:\\Windows', 'System32', 'taskkill.exe'),
      ['/pid', String(adminProcess.pid), '/T', '/F'], { stdio: 'ignore', windowsHide: true });
  } else if (adminProcess && adminProcess.exitCode === null) {
    adminProcess.kill('SIGTERM');
  }
  if (runtimeDirectory) rmSync(runtimeDirectory, { recursive: true, force: true });
});

test('selected image preview works under the real private-admin CSP', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop-chromium', 'One Chromium CSP probe is sufficient.');
  const cspErrors: string[] = [];
  page.on('console', message => {
    if (message.type() === 'error' && message.text().includes('Content Security Policy')) {
      cspErrors.push(message.text());
    }
  });

  const response = await page.goto('http://127.0.0.1:8081/');
  expect(response?.status()).toBe(200);
  const policy = response?.headers()['content-security-policy'] || '';
  expect(policy).toContain("img-src 'self' data: https:");
  expect(policy).not.toContain('blob:');

  await page.evaluate(() => {
    const input = document.createElement('input');
    input.id = 'csp-preview-input';
    input.type = 'file';
    const preview = document.createElement('div');
    preview.id = 'csp-preview-root';
    document.body.append(input, preview);
    (window as any).attachImagePreview(input, preview);
  });

  await page.locator('#csp-preview-input').setInputFiles({ name: 'preview.png', mimeType: 'image/png', buffer: onePixelPng });
  const image = page.locator('#csp-preview-root img');
  await expect(image).toBeVisible();
  await expect(image).toHaveAttribute('src', /^data:image\/png;base64,/);
  expect(cspErrors).toEqual([]);
});


test('delivery-zone map draws points and keeps coordinates synchronized', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop-chromium', 'One Chromium map-editor probe is sufficient.');
  const tileReferers: string[] = [];
  await page.route('https://tile.openstreetmap.org/**', async route => {
    tileReferers.push(route.request().headers()['referer'] || '');
    await route.fulfill({ status: 200, contentType: 'image/png', body: onePixelPng });
  });
  const response = await page.goto('http://127.0.0.1:8081/');
  expect(response?.headers()['referrer-policy']).toBe('strict-origin-when-cross-origin');
  await page.waitForLoadState('networkidle');
  await page.evaluate(() => {
    document.getElementById('login-view')!.hidden = true;
    document.getElementById('app-view')!.hidden = false;
    (window as any).renderDeliveryZone({type:'FeatureCollection', enforcementMode:'pincode', features:[]});
  });
  const map = page.locator('#delivery-zone-map');
  await expect(map).toBeVisible();
  await expect.poll(() => tileReferers.length).toBeGreaterThan(0);
  expect(tileReferers.every(referer => referer === 'http://127.0.0.1:8081/')).toBe(true);
  const box = await map.boundingBox();
  expect(box).not.toBeNull();
  const b = box!;
  for (const [x, y] of [[.25,.25],[.75,.25],[.75,.72],[.28,.7]]) {
    await map.click({position:{x:b.width * x, y:b.height * y}});
  }
  await expect(page.locator('.delivery-zone-map-marker')).toHaveCount(4);
  await expect(page.locator('#delivery-zone-boundary')).toHaveValue(/^-?\d+\.\d{6}, -?\d+\.\d{6}/);
  expect((await page.locator('#delivery-zone-boundary').inputValue()).trim().split(/\r?\n/)).toHaveLength(4);
  await page.locator('#delivery-zone-map-undo').click();
  await expect(page.locator('.delivery-zone-map-marker')).toHaveCount(3);
  await page.locator('#delivery-zone-map-clear').click();
  await expect(page.locator('.delivery-zone-map-marker')).toHaveCount(0);
  await expect(page.locator('#delivery-zone-boundary')).toHaveValue('');
});
