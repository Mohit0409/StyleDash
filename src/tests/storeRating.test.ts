import { describe, expect, it } from 'vitest';
import { getStoreRatingLabel } from '../utils/storeRating';

describe('verified public store rating labels', () => {
  it('shows compact /5 scores without unnecessary decimals', () => {
    expect(getStoreRatingLabel(5, 2)).toBe('5/5');
    expect(getStoreRatingLabel(4, 1)).toBe('4/5');
    expect(getStoreRatingLabel(4.5, 8)).toBe('4.5/5');
    expect(getStoreRatingLabel(4.25, 10)).toBe('4.3/5');
  });

  it('does not invent ratings for unrated or malformed stores', () => {
    expect(getStoreRatingLabel(5, 0)).toBeNull();
    expect(getStoreRatingLabel(0, 12)).toBeNull();
    expect(getStoreRatingLabel(6, 2)).toBeNull();
    expect(getStoreRatingLabel(3, -1)).toBeNull();
    expect(getStoreRatingLabel(NaN, 2)).toBeNull();
    expect(getStoreRatingLabel(Infinity, 2)).toBeNull();
    expect(getStoreRatingLabel(undefined, undefined)).toBeNull();
    expect(getStoreRatingLabel(4, 1.5)).toBeNull();
  });
});
