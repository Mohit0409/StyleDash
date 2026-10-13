import { describe, expect, it } from 'vitest';
import { CONFIG, resolveGoogleMeasurementId } from '../config';

describe('Vibe4You GA4 configuration', () => {
  it('never silently disables GA4 when the build-time variable is absent', () => {
    expect(CONFIG.ANALYTICS.GOOGLE_MEASUREMENT_ID).toMatch(/^(?:G|GT)-[A-Z0-9]{6,}$/i);
  });

  it.each([
    undefined, '', '  ', 'disabled', 'G-', 'G-INVALID*', 'UA-12345-1',
  ])('uses the known Vibe4You ID for missing or malformed override (%s)', (configured) => {
    expect(resolveGoogleMeasurementId(configured)).toBe('G-PSHXB46P50');
  });

  it.each(['G-ABCDEF1234', 'GT-ABCDEF12345'])(
    'honors a valid configured GA tag (%s)', configured => {
      expect(resolveGoogleMeasurementId(`  ${configured}  `)).toBe(configured);
    }
  );

  it('uses the expected property unless a valid override is explicitly provided', () => {
    expect(CONFIG.ANALYTICS.GOOGLE_MEASUREMENT_ID)
      .toBe(resolveGoogleMeasurementId(import.meta.env.VITE_GA_MEASUREMENT_ID));
  });
});
