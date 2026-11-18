import { Product } from '../types';

const GENERIC_VARIANT_VALUES = new Set(['default', 'one size', 'standard', 'free']);
const APPAREL_CATEGORIES = new Set(['clothing & fashion', 'footwear']);
const PACK_CATEGORIES = new Set([
  'baby care',
  'beauty & personal care',
  'groceries',
  'health & pharmacy',
  'pet supplies',
  'sports & fitness',
]);

const clean = (value?: string | null): string => (value || '').trim();

export const hasMeaningfulProductText = (value?: string | null): boolean => {
  const normalized = clean(value).toLowerCase();
  return Boolean(normalized)
    && normalized !== 'not specified'
    && normalized !== 'n/a'
    && normalized !== 'na'
    && normalized !== 'none';
};

export const meaningfulCareInstructions = (product: Product): string[] =>
  product.careInstructions
    .map(item => clean(item))
    .filter(hasMeaningfulProductText);

export const isSizedProduct = (product: Product): boolean =>
  APPAREL_CATEGORIES.has(clean(product.category).toLowerCase());

export const variantAttributeLabel = (product: Product): 'Size' | 'Pack / Volume' | 'Option' => {
  if (isSizedProduct(product)) return 'Size';
  if (PACK_CATEGORIES.has(clean(product.category).toLowerCase())) return 'Pack / Volume';
  return 'Option';
};

export const shouldShowVariantChoice = (product: Product): boolean => {
  const values = Array.from(new Set(product.variants.map(variant => clean(variant.size)).filter(Boolean)));
  if (values.length !== 1) return values.length > 1;
  return !GENERIC_VARIANT_VALUES.has(values[0].toLowerCase());
};

export const shouldShowSizeGuide = (product: Product): boolean =>
  isSizedProduct(product) && shouldShowVariantChoice(product);
