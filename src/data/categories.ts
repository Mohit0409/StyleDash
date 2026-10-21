export const CATEGORY_DISPLAY_ORDER = [
  'Clothing & Fashion',
  'Footwear',
  'Accessories',
  'Beauty & Personal Care',
  'Electronics',
  'Gifts',
  'Groceries',
  'Home & Living',
  'Health & Pharmacy',
  'Health & Nutrition',
  'Baby Care',
  'Pet Supplies',
  'Mobile Accessories',
  'Automotive Accessories',
  'Toys & Games',
  'Stationery & Books',
  'Sports & Fitness',
  'Hardware & Tools',
  'General Store',
] as const;

/**
 * Store choices match the production Python category vocabulary.
 * Keep this list aligned with scripts/store_categories.py.
 */
export const STORE_CATEGORIES = CATEGORY_DISPLAY_ORDER;

export const CATEGORY_DESCRIPTIONS: Record<string, string> = {
  'Clothing & Fashion': 'Clothing for every style and occasion',
  'Footwear': 'Shoes, sandals, sliders and more',
  'Accessories': 'Jewellery, watches, bags and accessories',
  'Beauty & Personal Care': 'Beauty, grooming and personal care',
  'Electronics': 'Electronics and useful gadgets',
  'Gifts': 'Gifts for every celebration',
  'Groceries': 'Groceries and everyday essentials',
  'Home & Living': 'Home essentials and decor',
  'Health & Pharmacy': 'Pharmacy and wellness essentials',
  'Health & Nutrition': 'Protein, supplements and nutrition essentials',
  'Baby Care': 'Food, care and essentials for babies',
  'Pet Supplies': 'Pet food and pet care products',
  'Mobile Accessories': 'Phone cases, chargers and other accessories',
  'Automotive Accessories': 'Car and vehicle accessories',
  'Toys & Games': 'Toys, games and gifts for play',
  'Stationery & Books': 'Stationery, books and office supplies',
  'Sports & Fitness': 'Sports, exercise and fitness equipment',
  'Hardware & Tools': 'Hardware, tools and fittings',
  'General Store': 'Assorted products and daily essentials',
};
