import { describe, expect, it, vi } from 'vitest';
import { serviceAreaRepository } from '../repositories/serviceAreaRepository';

const jsonResponse = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

describe('service area repository', () => {
  it('returns a supported response from the backend serviceability endpoint', async () => {
    const fetcher = vi.fn<typeof fetch>(async () => jsonResponse({
      success: true,
      pincode: '458441',
      serviceable: true,
      city: 'Neemuch',
      state: 'Madhya Pradesh',
      expressAvailable: true,
      estimatedDeliveryMinutes: 60,
    }));

    await expect(serviceAreaRepository.checkPincode('458441', fetcher)).resolves.toMatchObject({
      pincode: '458441',
      serviceable: true,
      city: 'Neemuch',
    });

    expect(fetcher).toHaveBeenCalledWith(
      '/api/serviceability?pincode=458441',
      expect.objectContaining({ credentials: 'include' }),
    );
  });

  it('returns an unsupported response without inventing serviceability', async () => {
    const fetcher = vi.fn<typeof fetch>(async () => jsonResponse({
      success: true,
      pincode: '458440',
      serviceable: false,
    }));

    await expect(serviceAreaRepository.checkPincode('458440', fetcher)).resolves.toEqual({
      success: true,
      pincode: '458440',
      serviceable: false,
    });
  });

  it('rejects malformed local input without calling the server', async () => {
    const fetcher = vi.fn<typeof fetch>();

    await expect(serviceAreaRepository.checkPincode('45 8441', fetcher)).resolves.toEqual({
      pincode: '45 8441',
      serviceable: false,
    });

    expect(fetcher).not.toHaveBeenCalled();
  });

  it('surfaces safe HTTP validation errors', async () => {
    const fetcher = vi.fn<typeof fetch>(async () => jsonResponse({
      success: false,
      error: 'A valid 6-digit pincode is required.',
      code: 'invalid_pincode',
    }, 400));

    await expect(serviceAreaRepository.checkPincode('458441', fetcher)).rejects.toMatchObject({
      name: 'ApiError',
      code: 'invalid_pincode',
      status: 400,
    });
  });

  it('fails closed on network errors', async () => {
    const fetcher = vi.fn<typeof fetch>(async () => {
      throw new TypeError('network unavailable');
    });

    await expect(serviceAreaRepository.checkPincode('458441', fetcher)).rejects.toMatchObject({
      name: 'ApiError',
      code: 'server_unavailable',
    });
  });

  it('fails closed on invalid JSON responses', async () => {
    const fetcher = vi.fn<typeof fetch>(async () =>
      new Response('not-json', {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    await expect(serviceAreaRepository.checkPincode('458441', fetcher)).rejects.toMatchObject({
      name: 'ApiError',
      code: 'invalid_response',
      status: 200,
    });
  });
});
