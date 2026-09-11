import React, {
  createContext,
  useContext,
  useEffect,
  useRef,
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

const WishlistContext = createContext<WishlistContextType | undefined>(undefined);

export const WishlistProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user, loading: authLoading } = useAuth();
  const userId = user?.uid ?? 'guest';
  const [wishlistState, setWishlistState] = useState<WishlistState>({ ownerId: 'guest', ids: [] });
  const ownerRef = useRef('guest');
  const saveQueueRef = useRef<Promise<void>>(Promise.resolve());

  const wishlistIds = wishlistState.ownerId === userId ? wishlistState.ids : [];

  useEffect(() => {
    if (authLoading) return;
    let cancelled = false;
    ownerRef.current = `loading:${userId}`;
    setWishlistState({ ownerId: `loading:${userId}`, ids: [] });

    void wishlistRepository.getWishlist(userId)
      .then(ids => {
        if (cancelled) return;
        ownerRef.current = userId;
        setWishlistState({ ownerId: userId, ids });
      })
      .catch(() => {
        if (cancelled) return;
        ownerRef.current = userId === 'guest' ? 'guest' : `unavailable:${userId}`;
        setWishlistState({ ownerId: userId, ids: [] });
      });

    return () => { cancelled = true; };
  }, [authLoading, userId]);

  const toggleWishlist = (productId: string) => {
    if (authLoading || ownerRef.current !== userId || wishlistState.ownerId !== userId) return;
    const currentIds = wishlistState.ids;
    const next = currentIds.includes(productId)
      ? currentIds.filter(id => id !== productId)
      : [...currentIds, productId];

    setWishlistState({ ownerId: userId, ids: next });

    if (userId === 'guest') {
      void wishlistRepository.saveWishlist(userId, next).catch(() => undefined);
      return;
    }

    const owner = userId;
    saveQueueRef.current = saveQueueRef.current.catch(() => undefined).then(async () => {
      if (ownerRef.current !== owner) return;
      await wishlistRepository.saveWishlist(owner, next);
    });
  };

  useEffect(() => {
    if (authLoading || userId === 'guest') return;
    const refresh = () => {
      const owner = userId;
      saveQueueRef.current = saveQueueRef.current.catch(() => undefined).then(async () => {
        if (ownerRef.current !== owner) return;
        try {
          const ids = await wishlistRepository.getWishlist(owner);
          if (ownerRef.current === owner) setWishlistState({ ownerId: owner, ids });
        } catch { /* Keep last known wishlist if refresh fails. */ }
      });
    };
    const onVisibility = () => { if (document.visibilityState === 'visible') refresh(); };
    window.addEventListener('focus', refresh);
    document.addEventListener('visibilitychange', onVisibility);
    return () => {
      window.removeEventListener('focus', refresh);
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, [authLoading, userId]);

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
