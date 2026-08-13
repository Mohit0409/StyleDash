const WISHLIST_KEY = 'sd_wishlist_ids';

export const wishlistRepository = {
  async getWishlist(_userId: string): Promise<string[]> {
    const local = localStorage.getItem(WISHLIST_KEY);
    if (local) {
      try { return JSON.parse(local); } catch { /* Ignore malformed local wishlist data. */ }
    }
    return [];
  },

  async saveWishlist(_userId: string, productIds: string[]): Promise<void> {
    localStorage.setItem(WISHLIST_KEY, JSON.stringify(productIds));
  }
};
