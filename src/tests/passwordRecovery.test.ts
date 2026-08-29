import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { authApi } from '../services/authApi';

const jsonResponse = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
  status,
  headers: { 'Content-Type': 'application/json' },
});

afterEach(() => vi.unstubAllGlobals());

describe('password recovery API', () => {
  it('requests reset instructions through the generic public endpoint', async () => {
    const fetcher = vi.fn<typeof fetch>(async () => jsonResponse({
      success: true,
      message: 'If an account exists, reset instructions will be sent shortly.',
    }));
    vi.stubGlobal('fetch', fetcher);

    await expect(authApi.requestPasswordReset('customer@example.test')).resolves.toMatchObject({ success: true });

    const [endpoint, request] = fetcher.mock.calls[0] as Parameters<typeof fetch>;
    expect(endpoint).toBe('/api/auth/password-reset/request');
    expect(JSON.parse(String(request?.body))).toEqual({ email: 'customer@example.test' });
    expect(new Headers(request?.headers).get('X-CSRF-Token')).toBeNull();
  });

  it('submits reset confirmation only with the token and new password', async () => {
    const fetcher = vi.fn<typeof fetch>(async () => jsonResponse({ success: true }));
    vi.stubGlobal('fetch', fetcher);

    await authApi.confirmPasswordReset('test-reset-token', 'new long password 456');

    const [endpoint, request] = fetcher.mock.calls[0] as Parameters<typeof fetch>;
    expect(endpoint).toBe('/api/auth/password-reset/confirm');
    expect(JSON.parse(String(request?.body))).toEqual({ token: 'test-reset-token', newPassword: 'new long password 456' });
  });
});

describe('password recovery routes', () => {
  it('exposes recovery routes and a login link', () => {
    const app = readFileSync(resolve('src/App.tsx'), 'utf8');
    const auth = readFileSync(resolve('src/pages/AuthPage.tsx'), 'utf8');
    expect(app).toContain('path="forgot-password"');
    expect(app).toContain('path="reset-password"');
    expect(auth).toContain('Forgot password?');
  });

  it('keeps reset tokens out of browser storage and removes fragment text after intake', () => {
    const recovery = readFileSync(resolve('src/pages/PasswordRecovery.tsx'), 'utf8');
    expect(recovery).toContain("new URLSearchParams(location.hash.slice(1)).get('token')");
    expect(recovery).toContain("navigate('/reset-password', { replace: true })");
    expect(recovery).not.toContain('location.search');
    expect(recovery).not.toMatch(/localStorage|sessionStorage|console\./);
    expect(recovery).toContain('minLength={8}');
    expect(recovery).toContain('maxLength={256}');
  });
});
