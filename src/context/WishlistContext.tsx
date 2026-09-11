import React, {
  createContext,
  useContext,
  useEffect,
  useState,
} from 'react';
import { wishlistRepository } from '../repositories/wishlistRepository';
import { useAuth } from './AuthContext';

interface WishlistContextType {
  wishlistIds: string[];
  toggleWishlist: (productId: string) => void;
  isInWishlist: (productId: string) => boolean;
}

interface WishlistState {
  ownerId: string;
  ids: string[];
}

const WishlistContext = createContext<WishlistContextType | undefined>(
  undefined,
);

export const WishlistProvider: React.FC<{
  children: React.ReactNode;
}> = ({ children }) => {
  const { user } = useAuth();
  const userId = user ? user.uid : 'guest';

  const [wishlistState, setWishlistState] = useState<WishlistState>({
    ownerId: userId,
    ids: [],
  });

  const wishlistIds =
    wishlistState.ownerId === userId ? wishlistState.ids : [];

  useEffect(() => {
    let cancelled = false;

    void wishlistRepository.getWishlist(userId).then(ids => {
      if (!cancelled) {
        setWishlistState({
          ownerId: userId,
          ids,
        });
      }
    });

    return () => {
      cancelled = true;
    };
  }, [userId]);

  const toggleWishlist = (productId: string) => {
    const currentIds =
      wishlistState.ownerId === userId ? wishlistState.ids : [];

    const next = currentIds.includes(productId)
      ? currentIds.filter(id => id !== productId)
      : [...currentIds, productId];

    setWishlistState({
      ownerId: userId,
      ids: next,
    });

    void wishlistRepository.saveWishlist(userId, next);
  };

  const isInWishlist = (productId: string) =>
    wishlistIds.includes(productId);

  return (
    <WishlistContext.Provider
      value={{
        wishlistIds,
        toggleWishlist,
        isInWishlist,
      }}
    >
      {children}
    </WishlistContext.Provider>
  );
};

export const useWishlist = () => {
  const context = useContext(WishlistContext);

  if (!context) {
    throw new Error(
      'useWishlist must be used within WishlistProvider',
    );
  }

  return context;
};
