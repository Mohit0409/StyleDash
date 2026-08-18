import { UserProfile } from '../types';
import { apiFetch, apiJson, clearCsrfToken, setCsrfToken } from './apiClient';

interface AuthResponse {
  success: true;
  user: UserProfile;
  csrfToken: string;
  needsProfile?: boolean;
}

interface PasswordResetRequestResponse {
  success: true;
  message: string;
}

const accept = (response: AuthResponse) => {
  setCsrfToken(response.csrfToken);
  return response;
};
export type FederatedProvider = 'google' | 'phone';

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
  async federated(provider: FederatedProvider, idToken: string): Promise<AuthResponse> {
    return accept(await apiJson<AuthResponse>(`/api/auth/federated/${provider}`, 'POST', { idToken }));
  },
  async linkFederated(provider: FederatedProvider, idToken: string): Promise<UserProfile> {
    return (await apiJson<{ success: true; profile: UserProfile }>(`/api/auth/federated/link/${provider}`, 'POST', { idToken })).profile;
  },
  async logout(): Promise<void> {
    await apiJson('/api/auth/logout', 'POST', {});
    clearCsrfToken();
  },
  async changePassword(currentPassword: string, newPassword: string): Promise<void> {
    const response = await apiJson<{ success: true; csrfToken: string }>('/api/auth/change-password', 'POST', { currentPassword, newPassword });
    setCsrfToken(response.csrfToken);
  },
  async requestPasswordReset(email: string): Promise<PasswordResetRequestResponse> {
    return apiJson<PasswordResetRequestResponse>('/api/auth/password-reset/request', 'POST', { email });
  },
  async confirmPasswordReset(token: string, newPassword: string): Promise<void> {
    await apiJson<{ success: true }>('/api/auth/password-reset/confirm', 'POST', { token, newPassword });
  },
};
