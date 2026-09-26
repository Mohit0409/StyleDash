export const CATEGORY_DISPLAY_ORDER = [
  'Clothing & Fashion',
  'Footwear',
  'Accessories',
  'Beauty & Personal Care',
  'Electronics',
  'Gifts',
  'Home & Living',
] as const;

/**
 * Canonical store category choices for the partner/shop-owner application.
 *
 * Store categories intentionally reuse the product catalogue taxonomy above
 * (kept in sync with scripts/store_categories.py on the backend, which is
 * the server-side source of truth). Do not maintain a separate hardcoded
 * list in the partner form.
 */
export const STORE_CATEGORIES = CATEGORY_DISPLAY_ORDER;

export const CATEGORY_DESCRIPTIONS: Record<string, string> = {
  'Clothing & Fashion': 'Clothing for every style and occasion',
  Footwear: 'Shoes, sandals, sliders and more',
  Accessories: 'Jewellery, watches, bags and accessories',
  'Beauty & Personal Care': 'Beauty, grooming and personal care',
  Electronics: 'Electronics and useful gadgets',
  Gifts: 'Gifts for every celebration',
  'Home & Living': 'Home essentials and decor',
};
