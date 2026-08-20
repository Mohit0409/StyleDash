import { afterEach, describe, expect, it, vi } from 'vitest';
import viteConfig from '../../vite.config';
import { authApi } from '../services/authApi';

describe('federated auth API', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it.each([
    ['google', '/api/auth/federated/google'],
    ['phone', '/api/auth/federated/phone'],
  ] as const)('posts the verified %s ID token to its federated endpoint', async (provider, endpoint) => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ success: true, user: { uid: 'u1', name: 'Ada', role: 'customer' }, csrfToken: 'csrf' }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }) as Response);

    await authApi.federated(provider, 'token-123');

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const [input, init] = fetchSpy.mock.calls[0] as [RequestInfo | URL, RequestInit | undefined];
    expect(input).toBe(endpoint);
    expect(init?.method).toBe('POST');
    expect(init?.credentials).toBe('include');
    expect(JSON.parse(String(init?.body))).toEqual({ idToken: 'token-123' });
  });

  it('proxies /api traffic to the StyleDash backend during local development', () => {
    const config = viteConfig as { server?: { proxy?: Record<string, unknown> } };
    const proxy = config.server?.proxy;

    expect(proxy).toBeDefined();
    expect(proxy).toHaveProperty('/api');
    expect(proxy?.['/api']).toMatchObject({
      target: 'http://127.0.0.1:8080',
      changeOrigin: true,
    });
  });
});
