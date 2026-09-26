import { Product } from '../types';

const GENERIC_TAGS = new Set(['local-shop']);

/**
 * Deterministic relevance score for Similar Products.
 * Mirrors scripts/styledash_shops.py::_similar_product_score so the offline
 * fallback ranks exactly like the authoritative server endpoint.
 */
export const similarProductScore = (current: Product, candidate: Product): number => {
  let score = 0;
  const subcategory = (current.subcategory || '').trim();
  if (subcategory && subcategory.toLowerCase() === (candidate.subcategory || '').trim().toLowerCase()) score += 100;
  if (current.category && current.category === candidate.category) score += 50;
  if (current.department && current.department === candidate.department) score += 25;
  const brand = (current.brand || '').trim();
  if (brand && brand.toLowerCase() === (candidate.brand || '').trim().toLowerCase()) score += 10;
  const currentTags = new Set((current.tags || []).map(tag => tag.toLowerCase()));
  const candidateTags = new Set((candidate.tags || []).map(tag => tag.toLowerCase()));
  GENERIC_TAGS.forEach(tag => { currentTags.delete(tag); candidateTags.delete(tag); });
  let shared = 0;
  currentTags.forEach(tag => { if (candidateTags.has(tag)) shared += 1; });
  score += Math.min(shared, 5) * 4;
  if (current.price > 0 && candidate.price > 0) {
    const ratio = candidate.price / current.price;
    if (ratio >= 0.8 && ratio <= 1.25) score += 10;
    else if (ratio >= 0.5 && ratio <= 2.0) score += 5;
  }
  return score;
};

/**
 * Ranked similar products: close taxonomy matches first (subcategory, then
 * category, then department), then brand/tags/price proximity, falling back
 * to broader catalogue order when a subcategory is sparse. The current
 * product, duplicates, and inactive products are always excluded. Ordering is
 * deterministic: score desc, then catalogue position, then name, then id.
 */
export const rankSimilarProducts = (
  current: Product,
  catalogue: Product[],
  limit = 8,
): Product[] => {
  const safeLimit = Math.max(1, Math.min(limit, 24));
  const seen = new Set([current.id]);
  const ranked: Array<{ score: number; position: number; name: string; id: string; product: Product }> = [];
  catalogue.forEach((product, position) => {
    if (seen.has(product.id) || product.active === false) return;
    seen.add(product.id);
    ranked.push({
      score: similarProductScore(current, product),
      position,
      name: (product.name || '').toLowerCase(),
      id: product.id,
      product,
    });
  });
  ranked.sort((a, b) =>
    b.score - a.score
    || a.position - b.position
    || (a.name < b.name ? -1 : a.name > b.name ? 1 : 0)
    || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0),
  );
  return ranked.slice(0, safeLimit).map(item => item.product);
};
