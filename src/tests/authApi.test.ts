import { afterEach, describe, expect, it, vi } from 'vitest';
import { authApi } from '../services/authApi';

describe('federated auth API', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('posts the federated provider and id token to the backend', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ success: true, user: { uid: 'u1', name: 'Ada', role: 'customer' }, csrfToken: 'csrf' }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }) as Response);

    await authApi.federated('google', 'token-123');

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const [input, init] = fetchSpy.mock.calls[0] as [RequestInfo | URL, RequestInit | undefined];
    expect(input).toBe('/api/auth/federated/google');
    expect(init?.method).toBe('POST');
    expect(JSON.parse(String(init?.body))).toEqual({ idToken: 'token-123' });
  });
});
