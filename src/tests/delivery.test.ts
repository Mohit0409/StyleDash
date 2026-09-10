import { describe, expect, it } from 'vitest';
import {
  cartExpressEligibility,
  expressCatalogueState,
  isExpressDeliveryAvailable,
  isProductExpressEligible,
} from '../utils/delivery';

const atNoonIst = (isoDate: string) => new Date(`${isoDate}T06:30:00.000Z`);

describe('Weekend Express delivery rules', () => {
  it('uses the Neemuch/India business day deterministically', () => {
    expect(isExpressDeliveryAvailable(atNoonIst('2026-09-07'))).toBe(false); // Monday
    expect(isExpressDeliveryAvailable(atNoonIst('2026-09-04'))).toBe(false); // Friday
    expect(isExpressDeliveryAvailable(atNoonIst('2026-09-05'))).toBe(true); // Saturday
    expect(isExpressDeliveryAvailable(atNoonIst('2026-09-06'))).toBe(true); // Sunday
  });

  it('activates the Express catalogue only on weekends', () => {
    expect(expressCatalogueState('express', atNoonIst('2026-09-04'))).toEqual({
      requested: true, available: false, active: false,
    });
    expect(expressCatalogueState('express', atNoonIst('2026-09-05'))).toEqual({
      requested: true, available: true, active: true,
    });
  });

  it('treats every product as Express-eligible under the site-wide weekend policy', () => {
    expect(isProductExpressEligible({ deliveryType: 'normal' })).toBe(true);
    expect(isProductExpressEligible({ deliveryType: 'express' })).toBe(true);
    expect(isProductExpressEligible({ deliveryType: 'both' })).toBe(true);
    expect(isProductExpressEligible({ expressDelivery: false })).toBe(true);
  });

  it('allows a mixed non-empty cart regardless of stored deliveryType', () => {
    expect(cartExpressEligibility([
      { name: 'Shoes', deliveryType: 'normal' },
      { name: 'Bangles', deliveryType: 'both' },
    ])).toEqual({ eligible: true, ineligibleProductNames: [] });
  });

  it('keeps an empty cart ineligible until there is something to deliver', () => {
    expect(cartExpressEligibility([])).toEqual({ eligible: false, ineligibleProductNames: [] });
  });
});