import React, { createContext, useContext, useState, useEffect } from 'react';
import { wishlistRepository } from '../repositories/wishlistRepository';
import { useAuth } from './AuthContext';

interface WishlistContextType {
  wishlistIds: string[];
  toggleWishlist: (productId: string) => void;
  isInWishlist: (productId: string) => boolean;
}

const WishlistContext = createContext<WishlistContextType | undefined>(undefined);

export const WishlistProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user } = useAuth();
  const userId = user ? user.uid : 'guest';
  const [wishlistIds, setWishlistIds] = useState<string[]>([]);

  useEffect(() => {
    wishlistRepository.getWishlist(userId).then(ids => setWishlistIds(ids));
  }, [userId]);

  const toggleWishlist = (productId: string) => {
    setWishlistIds(prev => {
      const next = prev.includes(productId)
        ? prev.filter(id => id !== productId)
        : [...prev, productId];
      wishlistRepository.saveWishlist(userId, next);
      return next;
    });
  };

  const isInWishlist = (productId: string) => wishlistIds.includes(productId);

  return (
    <WishlistContext.Provider value={{ wishlistIds, toggleWishlist, isInWishlist }}>
      {children}
    </WishlistContext.Provider>
  );
};

export const useWishlist = () => {
  const context = useContext(WishlistContext);
  if (!context) throw new Error('useWishlist must be used within WishlistProvider');
  return context;
};
