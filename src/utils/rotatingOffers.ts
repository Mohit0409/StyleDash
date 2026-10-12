import type { Product } from '../types';

export type OfferPeriod = 'today' | 'week' | 'month';

export interface RotatingOfferSection {
  period: OfferPeriod;
  title: string;
  periodKey: string;
  products: Product[];
}

const PERIODS: readonly { period: OfferPeriod; title: string }[] = [
  { period: 'today', title: "Today's Top Offers" },
  { period: 'week', title: 'Weekly Top Offers' },
  { period: 'month', title: 'Monthly Top Offers' },
];

// Use Neemuch's local calendar day, not the browsing device's timezone.
export const neemuchCalendarKeys = (now: Date): Record<OfferPeriod, string> => {
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Asia/Kolkata',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(now);
  const value = (key: string) => parts.find(part => part.type === key)?.value ?? '00';
  const year = Number(value('year'));
  const month = Number(value('month'));
  const day = Number(value('day'));
  const localDate = new Date(Date.UTC(year, month - 1, day));
  const weekday = localDate.getUTCDay();
  localDate.setUTCDate(localDate.getUTCDate() - ((weekday + 6) % 7));
  const weekMonday = localDate.toISOString().slice(0, 10);

  return {
    today: `${value('year')}-${value('month')}-${value('day')}`,
    week: weekMonday,
    month: `${value('year')}-${value('month')}`,
  };
};

const stableHash = (text: string): number => {
  let hash = 2166136261;
  for (let i = 0; i < text.length; i += 1) {
    hash ^= text.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
};

export const verifiedDiscountPercent = (product: Product): number => {
  if (!Number.isFinite(product.price) || !Number.isFinite(product.originalPrice)
      || product.price <= 0 || product.originalPrice <= product.price) return 0;
  return Math.round((1 - product.price / product.originalPrice) * 100);
};

const isOfferEligible = (product: Product): boolean =>
  product.active === true
  && verifiedDiscountPercent(product) > 0
  && (product.variants.length === 0
    || product.variants.some(variant => variant.available !== false));

/**
 * These are rotating collections of currently discounted merchandise, NOT
 * price promotions with guaranteed expiry dates. Keep product price and
 * eligibility sourced from the existing live catalogue.
 */
export const selectRotatingOffers = (
  products: Product[],
  now = new Date(),
  maxPerPeriod = 8,
): RotatingOfferSection[] => {
  const keys = neemuchCalendarKeys(now);
  if (!Number.isFinite(maxPerPeriod) || maxPerPeriod <= 0) return PERIODS.map(({ period, title }) => ({ period, title, periodKey: keys[period], products: [] }));
  const used = new Set<string>();
  const eligible = products.filter(isOfferEligible);

  return PERIODS.map(({ period, title }) => {
    const periodKey = keys[period];
    const candidates = eligible
      .filter(product => !used.has(product.id))
      .sort((a, b) => {
        const score = (product: Product) => verifiedDiscountPercent(product) * 100
          + (stableHash(`${periodKey}:${product.id}`) % 100);
        return score(b) - score(a) || a.id.localeCompare(b.id);
      });

    const selected: Product[] = [];
    const shopCounts = new Map<string, number>();
    const limit = Math.max(0, Math.trunc(maxPerPeriod));
    // Prefer variety across stores where enough eligible products exist.
    for (const item of candidates) {
      const shop = item.vendorId || item.storeSlug || item.id;
      if ((shopCounts.get(shop) || 0) >= 2) continue;
      selected.push(item);
      shopCounts.set(shop, (shopCounts.get(shop) || 0) + 1);
      if (selected.length === limit) break;
    }
    if (selected.length < limit) {
      const selectedIds = new Set(selected.map(item => item.id));
      for (const item of candidates) {
        if (selectedIds.has(item.id)) continue;
        selected.push(item);
        if (selected.length === limit) break;
      }
    }
    selected.forEach(item => used.add(item.id));

    return {
      period,
      title,
      periodKey,
      products: selected.map(item => ({
        ...item,
        // Always derive badges from the current verified selling price / MRP.
        discount: verifiedDiscountPercent(item),
      })),
    };
  });
};
