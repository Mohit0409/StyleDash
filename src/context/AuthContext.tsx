import React, { createContext, useContext, useEffect, useState } from 'react';
import { UserProfile } from '../types';
import { authApi } from '../services/authApi';
import { ApiError, clearCsrfToken } from '../services/apiClient';

interface AuthContextType {
  user: UserProfile | null;
  loading: boolean;
  error: string;
  login: (email: string, password: string) => Promise<boolean>;
  register: (name: string, email: string, password: string, phone?: string) => Promise<boolean>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const refresh = async () => {
    try { setUser(await authApi.me()); }
    catch { clearCsrfToken(); setUser(null); }
  };

  useEffect(() => { refresh().finally(() => setLoading(false)); }, []);

  const login = async (email: string, password: string) => {
    setLoading(true); setError('');
    try { setUser((await authApi.login(email, password)).user); return true; }
    catch (cause) { setError(cause instanceof ApiError ? cause.message : 'Login failed.'); return false; }
    finally { setLoading(false); }
  };

  const register = async (name: string, email: string, password: string, phone?: string) => {
    setLoading(true); setError('');
    try { setUser((await authApi.register(name, email, password, phone)).user); return true; }
    catch (cause) { setError(cause instanceof ApiError ? cause.message : 'Registration failed.'); return false; }
    finally { setLoading(false); }
  };

  const logout = async () => {
    try { await authApi.logout(); } finally { setUser(null); clearCsrfToken(); }
  };

  return <AuthContext.Provider value={{ user, loading, error, login, register, logout, refresh }}>{children}</AuthContext.Provider>;
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
};
