import { PRODUCT_CATEGORY_TAXONOMY } from './catalogTaxonomy';

/** Exact published production category vocabulary, keeping original order for UI. */
export const CATEGORY_DISPLAY_ORDER = PRODUCT_CATEGORY_TAXONOMY.map(item => item.name);
export const STORE_CATEGORIES = CATEGORY_DISPLAY_ORDER;

export interface CategoryItem {
  id: string;
  name: string;
  slug: string;
  department: string;
  subcategories: string[];
}

/** Full local taxonomy for category/subcategory browsing and shop product forms. */
export const CATEGORIES: CategoryItem[] = PRODUCT_CATEGORY_TAXONOMY.map((item, index) => ({
  id: String(index + 1),
  name: item.name,
  slug: item.name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, ''),
  department: 'all',
  subcategories: [...item.subcategories],
}));

export const CATEGORY_DESCRIPTIONS: Record<string, string> = {
  'Clothing & Fashion': 'Clothing for every style and occasion',
  Footwear: 'Shoes, sandals, sliders and more',
  Accessories: 'Jewellery, watches, bags and accessories',
  'Beauty & Personal Care': 'Beauty, grooming and personal care',
  Electronics: 'Electronics and useful gadgets',
  Gifts: 'Gifts for every celebration',
  'Home & Living': 'Home essentials and decor',
  Groceries: 'Food, pantry and household essentials',
  'Health & Pharmacy': 'Health and personal-care essentials',
  'Health & Nutrition': 'Nutrition and wellness products',
  'Baby Care': 'Baby care and feeding essentials',
  'Pet Supplies': 'Pet food, toys and care accessories',
  'Mobile Accessories': 'Covers, chargers and phone accessories',
  'Automotive Accessories': 'Car and two-wheeler accessories',
  'Toys & Games': 'Toys, educational games and activities',
  'Stationery & Books': 'School, office and reading essentials',
  'Sports & Fitness': 'Sports equipment and fitness accessories',
  'Hardware & Tools': 'Tools and home repair essentials',
  'General Store': 'Everyday supplies and useful products',
};
