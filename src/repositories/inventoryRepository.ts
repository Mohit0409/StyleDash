import { InventoryAvailabilityResponse } from '../types';
import { apiFetch } from '../services/apiClient';

export const inventoryRepository = {
  async getAvailability(variantId?: string, fetcher: typeof fetch = fetch): Promise<InventoryAvailabilityResponse> {
    const query = variantId ? `?variantId=${encodeURIComponent(variantId)}` : '';
    return apiFetch<InventoryAvailabilityResponse>(`/api/inventory/availability${query}`, {}, fetcher);
  },
};

export const canAddVariantToCart = async (variantId: string, fetcher: typeof fetch = fetch): Promise<boolean> => {
  try {
    const { availability } = await inventoryRepository.getAvailability(variantId, fetcher);
    return availability.length === 1 && availability[0].available === true;
  } catch {
    return false;
  }
};

export const canIncreaseCartQuantity = (variantId: string, fetcher: typeof fetch = fetch): Promise<boolean> =>
  canAddVariantToCart(variantId, fetcher);
