import { describe, expect, it } from 'vitest';
import { CONFIG } from '../config';

describe('ordering safety gate', () => {
  it('defaults customer ordering to disabled unless the production build explicitly opts in', () => {
    expect(CONFIG.ORDERING_ENABLED).toBe(false);
  });
});
