import { STORE_CATEGORIES } from '../data/categories';

/**
 * Store category options for the partner application form.
 *
 * Always returns the full canonical store category list. When an existing
 * draft/application carries a legacy value outside the canonical list, that
 * value is kept as the first option so reopening the form never silently
 * resets the saved category.
 */
export const storeCategoryOptions = (current?: string | null): string[] => {
  const options: string[] = [...STORE_CATEGORIES];
  const value = (current || '').trim();
  if (value && !options.includes(value)) {
    options.unshift(value);
  }
  return options;
};
