import { describe, expect, it } from 'vitest';
import { CONFIG } from '../config';

describe('Vibe4You GA4 configuration', () => {
  it('never silently disables GA4 when the build-time variable is absent', () => {
    expect(CONFIG.ANALYTICS.GOOGLE_MEASUREMENT_ID).toMatch(/^G-[A-Z0-9]{6,}$/);
  });

  it('uses the known Vibe4You property when no valid build override is configured', () => {
    if (!import.meta.env.VITE_GA_MEASUREMENT_ID?.trim()) {
      expect(CONFIG.ANALYTICS.GOOGLE_MEASUREMENT_ID).toBe('G-PSHXB46P50');
    }
  });
});
