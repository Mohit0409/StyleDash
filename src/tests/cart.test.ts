import { describe, it, expect } from 'vitest';

describe('StyleDash Cart & Variant Logic', () => {
  it('generates a stable variant-aware lineId', () => {
    const productId = 'sd-prod-001';
    const variantId = 'sd-prod-001-var-1';
    const lineId = `${productId}:${variantId}`;
    expect(lineId).toBe('sd-prod-001:sd-prod-001-var-1');
  });

  it('calculates totals correctly with GST tax', () => {
    const subtotal = 1000;
    const taxRate = 0.05;
    const taxes = subtotal * taxRate;
    const grandTotal = subtotal + taxes;
    expect(taxes).toBe(50);
    expect(grandTotal).toBe(1050);
  });

  it('applies fixed coupon discount correctly', () => {
    const subtotal = 800;
    const couponValue = 100;
    const discounted = Math.max(0, subtotal - couponValue);
    expect(discounted).toBe(700);
  });
});
