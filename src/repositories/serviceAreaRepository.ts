import { apiFetch } from '../services/apiClient';
import {
  DeliveryCoordinates,
  ServiceArea,
  ServiceabilityApiResponse,
} from '../types';

const validCoordinates = ({ latitude, longitude }: DeliveryCoordinates) =>
  Number.isFinite(latitude)
  && latitude >= -90
  && latitude <= 90
  && Number.isFinite(longitude)
  && longitude >= -180
  && longitude <= 180;

const unsupported = (pincode: string): ServiceArea => ({
  pincode,
  serviceable: false,
});

export const serviceAreaRepository = {
  async checkPincode(pincode: string, fetcher: typeof fetch = fetch): Promise<ServiceArea> {
    const normalized = pincode.trim();
    if (!/^\d{6}$/.test(normalized)) return unsupported(normalized);
    return apiFetch<ServiceabilityApiResponse>(
      `/api/serviceability?pincode=${encodeURIComponent(normalized)}`,
      {},
      fetcher,
    );
  },
  async checkLocation(
    pincode: string,
    coordinates: DeliveryCoordinates,
    fetcher: typeof fetch = fetch,
  ): Promise<ServiceArea> {
    const normalized = pincode.trim();
    if (!/^\d{6}$/.test(normalized) || !validCoordinates(coordinates)) {
      return unsupported(normalized);
    }
    const query = new URLSearchParams({
      pincode: normalized,
      latitude: String(coordinates.latitude),
      longitude: String(coordinates.longitude),
    });
    return apiFetch<ServiceabilityApiResponse>(
      `/api/serviceability?${query.toString()}`,
      {},
      fetcher,
    );
  },
};
