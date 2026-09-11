import { apiFetch, apiJson } from './apiClient';

export interface SavedCartLine {
  productId: string;
  variantId: string;
  quantity: number;
}

export interface AccountStateResponse {
  success: true;
  cart: SavedCartLine[];
  wishlist: string[];
}

export const accountStateApi = {
  async get(): Promise<AccountStateResponse> {
    return apiFetch<AccountStateResponse>('/api/account-state');
  },

  async saveCart(items: SavedCartLine[]): Promise<SavedCartLine[]> {
    const response = await apiJson<{ success: true; cart: SavedCartLine[] }>(
      '/api/account-state/cart',
      'PATCH',
      { items },
    );
    return response.cart;
  },

  async saveWishlist(productIds: string[]): Promise<string[]> {
    const response = await apiJson<{ success: true; wishlist: string[] }>(
      '/api/account-state/wishlist',
      'PATCH',
      { productIds },
    );
    return response.wishlist;
  },
};
