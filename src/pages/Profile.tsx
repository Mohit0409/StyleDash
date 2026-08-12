import React from 'react';
import { Link } from 'react-router-dom';
import { User, MapPin, Package, Heart, Share2, LogOut } from 'lucide-react';
import { SEO } from '../components/SEO';
import { useAuth } from '../context/AuthContext';

export const Profile: React.FC = () => {
  const { user, logout } = useAuth();

  return (
    <div className="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      <SEO title="My Profile - StyleDash" />

      <div className="p-6 bg-white dark:bg-neutral-900 rounded-3xl border border-neutral-200 dark:border-neutral-800 space-y-4 shadow-sm">
        <div className="flex items-center gap-4">
          <div className="w-16 h-16 bg-lime-400 text-neutral-950 font-black text-2xl rounded-2xl flex items-center justify-center">
            {user?.name?.[0] || 'U'}
          </div>
          <div>
            <h2 className="text-xl font-black text-neutral-900 dark:text-white">{user?.name || 'Mohit Jangde'}</h2>
            <p className="text-xs text-neutral-500">{user?.email || 'mohit@example.com'}</p>
            <span className="inline-block mt-1 px-2.5 py-0.5 bg-neutral-100 dark:bg-neutral-800 text-neutral-800 dark:text-neutral-200 text-[10px] font-bold rounded-full uppercase">
              Role: {user?.role || 'admin'}
            </span>
          </div>
        </div>
      </div>

      <div className="space-y-3">
        {[
          { label: 'Order History & Live Dispatch', path: '/orders', icon: Package },
          { label: 'Saved Wishlist', path: '/wishlist', icon: Heart },
          { label: 'Referrals & Wallet (₹100)', path: '/referrals', icon: Share2 },
          { label: 'Admin Portal', path: '/admin', icon: User }
        ].map(item => (
          <Link
            key={item.path}
            to={item.path}
            className="flex items-center justify-between p-4 bg-white dark:bg-neutral-900 rounded-2xl border border-neutral-200 dark:border-neutral-800 text-xs font-bold hover:border-lime-400 transition-colors"
          >
            <div className="flex items-center gap-3">
              <item.icon className="w-4 h-4 text-lime-600 dark:text-lime-400" />
              <span>{item.label}</span>
            </div>
            <span>→</span>
          </Link>
        ))}
      </div>
    </div>
  );
};
