import { afterEach, describe, expect, it, vi } from 'vitest';
import { publicStoreApi } from '../services/businessApi';
import { vendorRepository } from '../repositories/vendorRepository';

afterEach(() => { vi.restoreAllMocks(); });

describe('vendor repository', () => {
  it('merges ACTIVE server stores and resolves their storefront slug', async () => {
    const liveStore = {
      id: 'application-live-1', slug: 'local-shop-ation-live-1', storeName: 'Royals',
      category: 'Clothing & Fashion' as const, description: 'A real approved local shop.',
      address: 'Neemuch city', city: 'Neemuch', pincode: '458441', deliveryMinutes: 60,
      active: true, approved: true, createdAt: '2026-08-22T00:00:00Z',
    };
    vi.spyOn(publicStoreApi, 'active').mockResolvedValue([liveStore]);

    const stores = await vendorRepository.getAllStores();
    expect(stores.some(store => store.id === liveStore.id)).toBe(true);
    await expect(vendorRepository.getStoreBySlug(liveStore.slug)).resolves.toMatchObject({
      id: liveStore.id, storeName: 'Royals', active: true, approved: true,
    });
  });
});
