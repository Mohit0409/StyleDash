import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import type { Product } from '../types';
import { StoreStatistics } from '../components/StoreStatistics';
import { getStoreStatistics } from '../utils/storeStatistics';

const NOW = Date.parse('2026-10-14T12:00:00.000Z');
const HOUR = 60 * 60 * 1000;
const DAY = 24 * HOUR;

type Listing = Pick<Product, 'id' | 'active' | 'updatedAt'>;

const item = (id: string, updatedAt?: string, active = true): Listing =>
  ({ id, updatedAt, active });

const ago = (milliseconds: number): string => new Date(NOW - milliseconds).toISOString();

describe('public store statistics', () => {
  it('counts only unique active published listings, not size variants or duplicates', () => {
    const result = getStoreStatistics([
      item('a', ago(HOUR)), item('a', ago(5 * DAY)),
      item('b', ago(3 * DAY)), item('hidden', ago(HOUR), false),
      item('no-timestamp'), item('', ago(HOUR)),
    ], NOW);

    expect(result).toEqual({
      productCount: 3,
      updatedLast24Hours: 1,
      updatedLast7Days: 2,
      updatedLast30Days: 2,
      lastProductUpdate: ago(HOUR),
      activityLevel: 'daily',
    });
  });

  it('classifies the most recent published-product update into rolling 24h / 7d / 30d buckets', () => {
    expect(getStoreStatistics([item('a', ago(23 * HOUR))], NOW).activityLevel).toBe('daily');
    expect(getStoreStatistics([item('a', ago(DAY))], NOW).activityLevel).toBe('weekly');
    expect(getStoreStatistics([item('a', ago(7 * DAY - 1))], NOW).activityLevel).toBe('weekly');
    expect(getStoreStatistics([item('a', ago(7 * DAY))], NOW).activityLevel).toBe('monthly');
    expect(getStoreStatistics([item('a', ago(30 * DAY - 1))], NOW).activityLevel).toBe('monthly');
    expect(getStoreStatistics([item('a', ago(30 * DAY))], NOW).activityLevel).toBe('inactive');
  });

  it('counts distinct updated products in each inclusive hierarchy', () => {
    const result = getStoreStatistics([
      item('today', ago(HOUR)),
      item('this-week', ago(2 * DAY)),
      item('this-month', ago(12 * DAY)),
      item('old', ago(50 * DAY)),
    ], NOW);
    expect(result.productCount).toBe(4);
    expect(result.updatedLast24Hours).toBe(1);
    expect(result.updatedLast7Days).toBe(2);
    expect(result.updatedLast30Days).toBe(3);
    expect(result.lastProductUpdate).toBe(ago(HOUR));
  });

  it('does not invent activity from products with missing, malformed or future timestamps', () => {
    const result = getStoreStatistics([
      item('missing'),
      item('invalid', 'not-a-date'),
      item('future', new Date(NOW + DAY).toISOString()),
    ], NOW);
    expect(result.productCount).toBe(3);
    expect(result.updatedLast30Days).toBe(0);
    expect(result.lastProductUpdate).toBeNull();
    expect(result.activityLevel).toBe('unknown');
  });

  it('shows unknown, not inactive, when a new store has no dated listings', () => {
    const result = getStoreStatistics([], NOW);
    expect(result.productCount).toBe(0);
    expect(result.activityLevel).toBe('unknown');
  });

  it('prefers the most recent valid timestamp for duplicate product IDs', () => {
    const result = getStoreStatistics([
      item('x', ago(3 * DAY)),
      item('x', ago(HOUR)),
      item('x', 'garbage'),
      item('x', new Date(NOW + DAY).toISOString()),
    ], NOW);
    expect(result.productCount).toBe(1);
    expect(result.updatedLast24Hours).toBe(1);
    expect(result.activityLevel).toBe('daily');
  });

  it('renders only the compact trigger when collapsed and keeps all details hidden', () => {
    const markup = renderToStaticMarkup(
      <StoreStatistics
        storeId="test-store"
        products={[item('one', ago(HOUR)), item('two', ago(3 * DAY))]}
        publishedProductCount={110}
        rating={4.35}
        reviewCount={12}
      />,
    );
    expect(markup).toContain('data-testid="store-stat-trigger"');
    expect(markup).toContain('aria-label="Show store statistics"');
    expect(markup).toContain('aria-expanded="false"');
    expect(markup).not.toContain('data-testid="store-stat-panel"');
    expect(markup).not.toContain('Published products');
    expect(markup).not.toContain('Store Reviews');
    expect(markup).not.toContain('110');
  });
});
