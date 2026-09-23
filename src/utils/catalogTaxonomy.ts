import { CATEGORY_DISPLAY_ORDER } from '../data/categories';
import type { Product } from '../types';

export interface CatalogueSubcategory {
  name: string;
  count: number;
}

export interface CatalogueCategory {
  name: string;
  count: number;
  subcategories: CatalogueSubcategory[];
}

const compareNames = (left: string, right: string): number =>
  left.localeCompare(right, undefined, { sensitivity: 'base', numeric: true });

export const buildCatalogueTaxonomy = (products: Product[]): CatalogueCategory[] => {
  const categories = new Map<string, { count: number; subcategories: Map<string, number> }>();

  products.forEach(product => {
    if (product.active !== true) return;
    const category = product.category.trim();
    if (!category) return;
    const group = categories.get(category) ?? { count: 0, subcategories: new Map<string, number>() };
    group.count += 1;
    const subcategory = product.subcategory?.trim();
    if (subcategory) {
      group.subcategories.set(subcategory, (group.subcategories.get(subcategory) ?? 0) + 1);
    }
    categories.set(category, group);
  });

  const preferredOrder = new Map<string, number>(
    CATEGORY_DISPLAY_ORDER.map((category, index) => [category, index]),
  );

  return [...categories.entries()]
    .map(([name, group]) => ({
      name,
      count: group.count,
      subcategories: [...group.subcategories.entries()]
        .filter(([, count]) => count > 0)
        .map(([subcategoryName, count]) => ({ name: subcategoryName, count }))
        .sort((left, right) => compareNames(left.name, right.name)),
    }))
    .filter(category => category.count > 0)
    .sort((left, right) => {
      const leftOrder = preferredOrder.get(left.name) ?? Number.MAX_SAFE_INTEGER;
      const rightOrder = preferredOrder.get(right.name) ?? Number.MAX_SAFE_INTEGER;
      return leftOrder - rightOrder || compareNames(left.name, right.name);
    });
};
