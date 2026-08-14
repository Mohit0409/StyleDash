import { apiFetch, apiJson } from './apiClient';
import { ServerOrder } from './paymentApi';
import { UserProfile } from '../types';

export const orderApi = {
  async mine(): Promise<ServerOrder[]> {
    return (await apiFetch<{ success: true; orders: ServerOrder[] }>('/api/orders')).orders;
  },
  async one(id: string): Promise<ServerOrder> {
    return (await apiFetch<{ success: true; order: ServerOrder }>(`/api/orders/${encodeURIComponent(id)}`)).order;
  },
};

export const vendorApplicationApi = {
  submit(payload: Record<string, unknown>) {
    return apiJson<{ success: true; application: { id: string; status: 'pending' } }>('/api/vendor-applications', 'POST', payload);
  },
};

export const profileApi = {
  async get(): Promise<UserProfile> {
    return (await apiFetch<{ success: true; profile: UserProfile }>('/api/profile')).profile;
  },
  async update(payload: Record<string, unknown>): Promise<UserProfile> {
    return (await apiJson<{ success: true; profile: UserProfile }>('/api/profile', 'PATCH', payload)).profile;
  },
};
