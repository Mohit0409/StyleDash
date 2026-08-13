import { apiFetch } from '../services/apiClient';
import { ServiceArea, ServiceabilityApiResponse } from '../types';

export const serviceAreaRepository = {
  async checkPincode(pincode: string, fetcher: typeof fetch = fetch): Promise<ServiceArea> {
    const normalized = pincode.trim();
    if (!/^\d{6}$/.test(normalized)) {
      return { pincode: normalized, serviceable: false };
    }
    const response = await apiFetch<ServiceabilityApiResponse>(
      `/api/serviceability?pincode=${encodeURIComponent(normalized)}`,
      {},
      fetcher,
    );
    return response;
  }
};
