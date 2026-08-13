let csrfToken = '';

export const setCsrfToken = (value: string) => { csrfToken = value; };
export const clearCsrfToken = () => { csrfToken = ''; };

export class ApiError extends Error {
  constructor(message: string, public code = 'request_failed', public status = 0) {
    super(message);
    this.name = 'ApiError';
  }
}

export async function apiFetch<T>(
  endpoint: string,
  init: RequestInit = {},
  fetcher: typeof fetch = fetch,
): Promise<T> {
  const headers = new Headers(init.headers);
  const method = (init.method || 'GET').toUpperCase();
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method) && csrfToken) headers.set('X-CSRF-Token', csrfToken);
  let response: Response;
  try {
    response = await fetcher(endpoint, { ...init, headers, credentials: 'include' });
  } catch {
    throw new ApiError('The StyleDash server is unavailable.', 'server_unavailable');
  }
  let payload: T & { error?: string; code?: string };
  try {
    payload = await response.json();
  } catch {
    throw new ApiError('The server returned an invalid response.', 'invalid_response', response.status);
  }
  if (!response.ok) throw new ApiError(payload.error || 'Request failed.', payload.code, response.status);
  return payload;
}

export function apiJson<T>(endpoint: string, method: string, body: unknown): Promise<T> {
  return apiFetch<T>(endpoint, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}
