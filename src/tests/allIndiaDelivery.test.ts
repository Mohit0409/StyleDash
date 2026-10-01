import { describe, expect, it } from 'vitest';
import type { CartItem } from '../types';
import { allIndiaCartEligibility } from '../utils/allIndiaDelivery';

const item = (
  vendorId: string,
  overrides: Record<string, unknown> = {},
): CartItem => ({
  lineId: `line-${vendorId}-${Math.random()}`,
  productId: 'product-1',
  variantId: 'variant-1',
  selectedSize: 'M',
  selectedColour: 'Black',
  sku: 'SKU-1',
  quantity: 1,
  unitPrice: 500,
  product: {
    id: 'product-1',
    name: 'Test Product',
    vendorId,
    allIndiaDeliveryAvailable: true,
    allIndiaShippingPayer: 'customer',
    ...overrides,
  },
} as unknown as CartItem);

describe('All India mediator cart eligibility', () => {
  it('requires a non-empty same-shop cart with shop opt-in', () => {
    expect(allIndiaCartEligibility([]).eligible).toBe(false);
    expect(allIndiaCartEligibility([
      item('shop-a'),
      item('shop-a', { id: 'product-2' }),
    ])).toMatchObject({
      eligible: true,
      vendorId: 'shop-a',
      shippingPayer: 'customer',
    });
    expect(allIndiaCartEligibility([
      item('shop-a'),
      item('shop-b', { id: 'product-2' }),
    ])).toMatchObject({
      eligible: false,
      reason: 'All India orders can contain products from only one shop.',
    });
  });

  it('rejects carts when any item is not opted in or shipping policy is inconsistent', () => {
    expect(allIndiaCartEligibility([
      item('shop-a'),
      item('shop-a', { id: 'product-2', allIndiaDeliveryAvailable: false }),
    ])).toMatchObject({
      eligible: false,
      reason: 'This shop has not enabled All India delivery for every item in the cart.',
    });
    expect(allIndiaCartEligibility([
      item('shop-a'),
      item('shop-a', { id: 'product-2', allIndiaShippingPayer: 'shop' }),
    ])).toMatchObject({
      eligible: false,
      reason: 'All India shipping settings are temporarily unavailable.',
    });
  });

  it('keeps Try at Home out of the mediator flow', () => {
    expect(allIndiaCartEligibility([
      { ...item('shop-a'), tryAtHomeVariantIds: ['variant-1', 'variant-2'] },
    ])).toMatchObject({
      eligible: false,
      reason: 'Try at Home is available only for local Neemuch delivery.',
    });
  });
});
