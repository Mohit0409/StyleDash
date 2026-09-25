import type { VendorStore } from '../types';

export const rankStoresByProductCount = (stores: VendorStore[]): VendorStore[] =>
  [...stores].sort((a, b) =>
    (b.productCount ?? 0) - (a.productCount ?? 0)
    || a.storeName.localeCompare(b.storeName),
  );
