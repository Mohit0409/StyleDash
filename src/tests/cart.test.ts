import { describe, it, expect } from 'vitest';
import { calculateCartTotals } from '../context/cartTotals';
import { Coupon } from '../types';

describe('StyleDash Cart & Variant Logic', () => {
  it('generates a stable variant-aware lineId', () => {
    const productId = 'sd-prod-001';
    const variantId = 'sd-prod-001-var-1';
    const lineId = `${productId}:${variantId}`;
    expect(lineId).toBe('sd-prod-001:sd-prod-001-var-1');
  });

  it('calculates production totals with GST and delivery', () => {
    expect(calculateCartTotals({
      subtotal: 1000,
      appliedCoupon: null,
      deliveryMethod: 'express',
    })).toEqual({
      couponDiscount: 0,
      discountTotal: 0,
      deliveryFee: 0,
      taxes: 50,
      grandTotal: 1050,
    });
  });

  it('keeps coupon behavior without a client wallet discount', () => {
    const coupon: Coupon = {
      code: 'STYLE100',
      discountType: 'fixed',
      value: 100,
      minOrderValue: 499,
      active: true,
      expiryDate: '2026-12-31',
    };

    expect(calculateCartTotals({
      subtotal: 800,
      appliedCoupon: coupon,
      deliveryMethod: 'standard',
    })).toEqual({
      couponDiscount: 100,
      discountTotal: 100,
      deliveryFee: 49,
      taxes: 35,
      grandTotal: 784,
    });
  });

  it('ignores stale wallet-shaped browser data', () => {
    const staleInput = {
      subtotal: 800,
      appliedCoupon: null,
      deliveryMethod: 'standard' as const,
      walletDiscount: 800,
    };

    expect(calculateCartTotals(staleInput).grandTotal).toBe(889);
  });
});
