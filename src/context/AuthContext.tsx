import React, { createContext, useContext, useState, useEffect } from 'react';
import { UserProfile } from '../types';
import { userRepository } from '../repositories/userRepository';

interface AuthContextType {
  user: UserProfile | null;
  loading: boolean;
  login: (email: string, pass: string) => Promise<boolean>;
  register: (name: string, email: string, pass: string) => Promise<boolean>;
  logout: () => void;
  updateProfile: (profile: Partial<UserProfile>) => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    userRepository.getUserProfile('guest-user-id').then(profile => {
      setUser(profile);
      setLoading(false);
    });
  }, []);

  const login = async (email: string): Promise<boolean> => {
    setLoading(true);
    const profile = await userRepository.getUserProfile('user-id');
    if (profile) {
      profile.email = email;
      setUser(profile);
      setLoading(false);
      return true;
    }
    setLoading(false);
    return false;
  };

  const register = async (name: string, email: string): Promise<boolean> => {
    setLoading(true);
    const newProfile: UserProfile = {
      uid: `usr-${Date.now()}`,
      name,
      email,
      role: 'customer',
      addresses: [],
      referralCode: `SD${Math.floor(1000 + Math.random() * 9000)}`,
      walletBalance: 100,
      createdAt: new Date().toISOString()
    };
    await userRepository.saveUserProfile(newProfile);
    setUser(newProfile);
    setLoading(false);
    return true;
  };

  const logout = () => {
    setUser(null);
  };

  const updateProfile = async (updates: Partial<UserProfile>) => {
    if (user) {
      const updated = { ...user, ...updates };
      setUser(updated);
      await userRepository.saveUserProfile(updated);
    }
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, updateProfile }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
};
