import React, { createContext, useContext, useEffect, useState } from 'react';
import { UserProfile } from '../types';
import { authApi } from '../services/authApi';
import { ApiError, clearCsrfToken } from '../services/apiClient';

export type FederatedProvider = 'google' | 'phone';

interface AuthContextType {
  user: UserProfile | null;
  needsProfile: boolean;
  loading: boolean;
  error: string;
  login: (email: string, password: string) => Promise<boolean>;
  register: (name: string, email: string, password: string, phone?: string) => Promise<boolean>;
  federatedLogin: (provider: FederatedProvider, idToken: string) => Promise<boolean>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [needsProfile, setNeedsProfile] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const refresh = async () => {
    try {
      const nextUser = await authApi.me();
      setUser(nextUser);
      setNeedsProfile(Boolean(nextUser.phone && !nextUser.name));
    } catch { clearCsrfToken(); setUser(null); setNeedsProfile(false); }
  };

  useEffect(() => { refresh().finally(() => setLoading(false)); }, []);

  const login = async (email: string, password: string) => {
    setLoading(true); setError('');
    try { const response = await authApi.login(email, password); setUser(response.user); setNeedsProfile(false); return true; }
    catch (cause) { setError(cause instanceof ApiError ? cause.message : 'Login failed.'); return false; }
    finally { setLoading(false); }
  };

  const register = async (name: string, email: string, password: string, phone?: string) => {
    setLoading(true); setError('');
    try { const response = await authApi.register(name, email, password, phone); setUser(response.user); setNeedsProfile(false); return true; }
    catch (cause) { setError(cause instanceof ApiError ? cause.message : 'Registration failed.'); return false; }
    finally { setLoading(false); }
  };

  const federatedLogin = async (provider: FederatedProvider, idToken: string) => {
    setLoading(true); setError('');
    try { const response = await authApi.federated(provider, idToken); setUser(response.user); setNeedsProfile(Boolean(response.needsProfile)); return true; }
    catch (cause) { setError(cause instanceof ApiError ? cause.message : 'Sign in failed.'); return false; }
    finally { setLoading(false); }
  };

  const logout = async () => {
    try { await authApi.logout(); } finally { setUser(null); setNeedsProfile(false); clearCsrfToken(); }
  };

  return <AuthContext.Provider value={{ user, needsProfile, loading, error, login, register, federatedLogin, logout, refresh }}>{children}</AuthContext.Provider>;
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
};
