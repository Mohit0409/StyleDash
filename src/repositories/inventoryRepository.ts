import { InventoryAvailabilityResponse } from '../types';
import { apiFetch } from '../services/apiClient';

export const inventoryRepository = {
  async getAvailability(variantId?: string, fetcher: typeof fetch = fetch): Promise<InventoryAvailabilityResponse> {
    const query = variantId ? `?variantId=${encodeURIComponent(variantId)}` : '';
    return apiFetch<InventoryAvailabilityResponse>(`/api/inventory/availability${query}`, {}, fetcher);
  },

  async getAvailabilityForProducts(productIds: string[], fetcher: typeof fetch = fetch): Promise<InventoryAvailabilityResponse> {
    const uniqueIds = [...new Set(productIds)];
    if (uniqueIds.length === 0) return { success: true, availability: [] };
    const query = uniqueIds.map(id => `productId=${encodeURIComponent(id)}`).join('&');
    return apiFetch<InventoryAvailabilityResponse>(`/api/inventory/availability?${query}`, {}, fetcher);
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

// One batched product-level request instead of one request per variant.
export const canAddVariantsToCart = async (productId: string, variantIds: string[], fetcher: typeof fetch = fetch): Promise<boolean> => {
  try {
    const { availability } = await inventoryRepository.getAvailabilityForProducts([productId], fetcher);
    const available = new Set(availability.filter(item => item.available === true).map(item => item.variantId));
    return variantIds.every(variantId => available.has(variantId));
  } catch {
    return false;
  }
};

export const canIncreaseCartQuantity = (variantId: string, fetcher: typeof fetch = fetch): Promise<boolean> =>
  canAddVariantToCart(variantId, fetcher);
