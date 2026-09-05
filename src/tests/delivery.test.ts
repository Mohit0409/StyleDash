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

  it('treats product deliveryType as the canonical Express eligibility', () => {
    expect(isProductExpressEligible({ deliveryType: 'normal' })).toBe(false);
    expect(isProductExpressEligible({ deliveryType: 'express' })).toBe(true);
    expect(isProductExpressEligible({ deliveryType: 'both' })).toBe(true);
    expect(isProductExpressEligible({ expressDelivery: true })).toBe(true);
    expect(isProductExpressEligible({ expressDelivery: false })).toBe(false);
  });

  it('blocks a mixed cart and names the non-Express product', () => {
    const result = cartExpressEligibility([
      { name: 'Express Shoes', deliveryType: 'both' },
      { name: 'Normal Bangles', deliveryType: 'normal' },
    ]);
    expect(result).toEqual({
      eligible: false,
      ineligibleProductNames: ['Normal Bangles'],
    });
  });

  it('allows a non-empty cart when every product is Express-eligible', () => {
    expect(cartExpressEligibility([
      { name: 'Campus Shoes', deliveryType: 'both' },
      { name: 'JQR Shoes', deliveryType: 'express' },
    ]).eligible).toBe(true);
  });
});