import { accountStateApi } from '../services/accountStateApi';

const GUEST_WISHLIST_KEY = 'sd_wishlist_ids';
const scopedWishlistKey = (userId: string): string => `sd_wishlist_ids:${userId}`;

const readKey = (key: string): string[] => {
  const local = localStorage.getItem(key);
  if (!local) return [];
  try {
    const parsed = JSON.parse(local);
    return Array.isArray(parsed)
      ? [...new Set(parsed.filter((id): id is string => typeof id === 'string' && id.length > 0))].slice(0, 200)
      : [];
  } catch {
    return [];
  }
};

export const wishlistRepository = {
  async getWishlist(userId: string): Promise<string[]> {
    if (userId === 'guest') return readKey(GUEST_WISHLIST_KEY);

    const state = await accountStateApi.get();
    const scopedLegacy = readKey(scopedWishlistKey(userId));
    const guestLegacy = readKey(GUEST_WISHLIST_KEY);
    const legacy = [...scopedLegacy, ...guestLegacy];
    if (legacy.length === 0) return state.wishlist;

    const merged = [...new Set([...state.wishlist, ...legacy])].slice(0, 200);
    await accountStateApi.saveWishlist(merged);
    localStorage.removeItem(scopedWishlistKey(userId));
    localStorage.removeItem(GUEST_WISHLIST_KEY);
    return merged;
  },

  async saveWishlist(userId: string, productIds: string[]): Promise<void> {
    const normalized = [...new Set(productIds)].slice(0, 200);
    if (userId === 'guest') {
      localStorage.setItem(GUEST_WISHLIST_KEY, JSON.stringify(normalized));
      return;
    }
    await accountStateApi.saveWishlist(normalized);
  },
};
