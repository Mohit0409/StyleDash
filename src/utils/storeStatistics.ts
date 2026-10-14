import type { Product } from '../types';

type StoreListing = Pick<Product, 'id' | 'active' | 'updatedAt'>;

export type StoreActivityLevel = 'daily' | 'weekly' | 'monthly' | 'inactive' | 'unknown';

export interface StoreStatisticsData {
  productCount: number;
  updatedLast24Hours: number;
  updatedLast7Days: number;
  updatedLast30Days: number;
  lastProductUpdate: string | null;
  activityLevel: StoreActivityLevel;
}

const DAY_MS = 24 * 60 * 60 * 1000;

/**
 * Catalogue activity is based on the latest update timestamp of published
 * listings, NOT shop visits, logins, customer activity or business opening hours.
 *
 * Windows are rolling (24h / 7x24h / 30x24h); counts represent distinct
 * currently published products last updated in each period, not edit events.
 * Reject missing, malformed and future timestamps rather than marking
 * stores as recently active on untrusted or unavailable date information.
 */
export const getStoreStatistics = (
  products: readonly StoreListing[],
  nowMs = Date.now(),
): StoreStatisticsData => {
  const latestById = new Map<string, number | null>();

  for (const product of products) {
    if (!product.active || !product.id) continue;
    const timestamp = product.updatedAt ? Date.parse(product.updatedAt) : NaN;
    const validTimestamp = Number.isFinite(timestamp) && timestamp <= nowMs
      ? timestamp : null;

    if (!latestById.has(product.id)) {
      latestById.set(product.id, validTimestamp);
      continue;
    }
    const previous = latestById.get(product.id);
    if (validTimestamp !== null && (previous === null || previous === undefined || validTimestamp > previous)) {
      latestById.set(product.id, validTimestamp);
    }
  }

  let updatedLast24Hours = 0;
  let updatedLast7Days = 0;
  let updatedLast30Days = 0;
  let latestTimestamp: number | null = null;

  for (const timestamp of latestById.values()) {
    if (timestamp === null) continue;
    if (latestTimestamp === null || timestamp > latestTimestamp) latestTimestamp = timestamp;
    const ageMs = nowMs - timestamp;
    if (ageMs < DAY_MS) updatedLast24Hours += 1;
    if (ageMs < 7 * DAY_MS) updatedLast7Days += 1;
    if (ageMs < 30 * DAY_MS) updatedLast30Days += 1;
  }

  const activityLevel: StoreActivityLevel = latestTimestamp === null ? 'unknown'
    : updatedLast24Hours > 0 ? 'daily'
      : updatedLast7Days > 0 ? 'weekly'
        : updatedLast30Days > 0 ? 'monthly' : 'inactive';

  return {
    productCount: latestById.size,
    updatedLast24Hours,
    updatedLast7Days,
    updatedLast30Days,
    lastProductUpdate: latestTimestamp === null ? null : new Date(latestTimestamp).toISOString(),
    activityLevel,
  };
};
