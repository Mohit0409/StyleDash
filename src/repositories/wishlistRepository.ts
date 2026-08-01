import { db, isFirebaseConfigured } from '../firebase/config';
import { doc, getDoc, setDoc } from 'firebase/firestore';

const WISHLIST_KEY = 'sd_wishlist_ids';

export const wishlistRepository = {
  async getWishlist(userId: string): Promise<string[]> {
    if (isFirebaseConfigured && db && userId !== 'guest') {
      try {
        const snap = await getDoc(doc(db, 'wishlists', userId));
        if (snap.exists()) {
          return snap.data().productIds || [];
        }
      } catch { /* Fall back to the local wishlist. */ }
    }
    const local = localStorage.getItem(WISHLIST_KEY);
    if (local) {
      try { return JSON.parse(local); } catch { /* Ignore malformed local wishlist data. */ }
    }
    return [];
  },

  async saveWishlist(userId: string, productIds: string[]): Promise<void> {
    localStorage.setItem(WISHLIST_KEY, JSON.stringify(productIds));
    if (isFirebaseConfigured && db && userId !== 'guest') {
      try {
        await setDoc(doc(db, 'wishlists', userId), { productIds, updatedAt: new Date().toISOString() });
      } catch { /* The local wishlist remains available. */ }
    }
  }
};
