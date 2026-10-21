import { describe, expect, it } from 'vitest';
import { MOBILE_CATEGORY_SHORTCUTS } from '../data/mobileCategoryShortcuts';

describe('mobile storefront category shortcuts', () => {
  it('keeps the production Watches, Groceries and Nutrition shortcuts', () => {
    const byLabel = Object.fromEntries(MOBILE_CATEGORY_SHORTCUTS.map(item => [item.label, item.href]));
    expect(byLabel.Watches).toBe('/products?search=watch');
    expect(byLabel.Groceries).toBe('/products?category=Groceries');
    expect(byLabel.Nutrition).toBe('/products?category=Health%20%26%20Nutrition');
  });

  it('has unique labels and destinations', () => {
    const labels = MOBILE_CATEGORY_SHORTCUTS.map(item => item.label);
    const urls = MOBILE_CATEGORY_SHORTCUTS.map(item => item.href);
    expect(labels).toHaveLength(9);
    expect(new Set(labels).size).toBe(labels.length);
    expect(new Set(urls).size).toBe(urls.length);
  });
});
