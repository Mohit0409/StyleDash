import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user, needsProfile, loading } = useAuth();
  const location = useLocation();
  const returnPath = `${location.pathname}${location.search}${location.hash}`;
  if (loading) return <div className="min-h-[50vh] flex items-center justify-center text-sm font-bold">Checking your session…</div>;
  if (!user) return <Navigate to="/login" replace state={{ from: returnPath }} />;
  if (needsProfile && location.pathname !== '/profile') return <Navigate to="/profile" replace state={{ from: returnPath }} />;
  return <>{children}</>;
};
