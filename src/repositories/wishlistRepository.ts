const LEGACY_GUEST_WISHLIST_KEY = 'sd_wishlist_ids';

const wishlistKey = (userId: string): string =>
  userId === 'guest'
    ? LEGACY_GUEST_WISHLIST_KEY
    : `sd_wishlist_ids:${userId}`;

export const wishlistRepository = {
  async getWishlist(userId: string): Promise<string[]> {
    const local = localStorage.getItem(wishlistKey(userId));

    if (local) {
      try {
        const parsed = JSON.parse(local);
        return Array.isArray(parsed)
          ? parsed.filter((id): id is string => typeof id === 'string')
          : [];
      } catch {
        // Ignore malformed local wishlist data.
      }
    }

    return [];
  },

  async saveWishlist(
    userId: string,
    productIds: string[],
  ): Promise<void> {
    localStorage.setItem(
      wishlistKey(userId),
      JSON.stringify(productIds),
    );
  },
};
