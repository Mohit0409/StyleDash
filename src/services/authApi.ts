import { UserProfile } from '../types';
import { apiFetch, apiJson, clearCsrfToken, setCsrfToken } from './apiClient';

interface AuthResponse {
  success: true;
  user: UserProfile;
  csrfToken: string;
}

const accept = (response: AuthResponse) => {
  setCsrfToken(response.csrfToken);
  return response;
};

export const authApi = {
  async me(): Promise<UserProfile> {
    const response = await apiFetch<AuthResponse>('/api/auth/me');
    return accept(response).user;
  },
  async login(email: string, password: string): Promise<AuthResponse> {
    return accept(await apiJson<AuthResponse>('/api/auth/login', 'POST', { email, password }));
  },
  async register(name: string, email: string, password: string, phone?: string): Promise<AuthResponse> {
    return accept(await apiJson<AuthResponse>('/api/auth/register', 'POST', { name, email, password, phone }));
  },
  async logout(): Promise<void> {
    await apiJson('/api/auth/logout', 'POST', {});
    clearCsrfToken();
  },
  async changePassword(currentPassword: string, newPassword: string): Promise<void> {
    const response = await apiJson<{ success: true; csrfToken: string }>('/api/auth/change-password', 'POST', { currentPassword, newPassword });
    setCsrfToken(response.csrfToken);
  },
};
