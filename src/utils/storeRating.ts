/**
 * Verified store ratings come from the existing public review summary.
 * Never imply a star score exists when there are no verified reviews.
 */
export const getStoreRatingLabel = (rating?: number, reviewCount?: number): string | null => {
  if (typeof rating !== 'number' || !Number.isFinite(rating) || rating < 1 || rating > 5
      || typeof reviewCount !== 'number' || !Number.isSafeInteger(reviewCount) || reviewCount < 1) {
    return null;
  }

  const rounded = Math.round(rating * 10) / 10;
  return `${Number.isInteger(rounded) ? rounded.toFixed(0) : rounded.toFixed(1)}/5`;
};
