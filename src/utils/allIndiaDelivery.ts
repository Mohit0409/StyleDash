import type { CartItem } from '../types';

export interface AllIndiaCartEligibility {
  eligible: boolean;
  vendorId: string | null;
  shippingPayer: 'shop' | 'customer' | null;
  reason: string;
}

export const allIndiaCartEligibility = (items: CartItem[]): AllIndiaCartEligibility => {
  if (!items.length) {
    return { eligible: false, vendorId: null, shippingPayer: null, reason: 'Your cart is empty.' };
  }
  if (items.some(item => item.tryAtHomeVariantIds?.length)) {
    return {
      eligible: false,
      vendorId: null,
      shippingPayer: null,
      reason: 'Try at Home is available only for local Neemuch delivery.',
    };
  }

  const vendorId = items[0].product.vendorId;
  if (!vendorId || items.some(item => item.product.vendorId !== vendorId)) {
    return {
      eligible: false,
      vendorId: null,
      shippingPayer: null,
      reason: 'All India orders can contain products from only one shop.',
    };
  }

  if (items.some(item => item.product.allIndiaDeliveryAvailable !== true)) {
    return {
      eligible: false,
      vendorId,
      shippingPayer: null,
      reason: 'This shop has not enabled All India delivery for every item in the cart.',
    };
  }

  const shippingPayer = items[0].product.allIndiaShippingPayer;
  if (
    (shippingPayer !== 'shop' && shippingPayer !== 'customer')
    || items.some(item => item.product.allIndiaShippingPayer !== shippingPayer)
  ) {
    return {
      eligible: false,
      vendorId,
      shippingPayer: null,
      reason: 'All India shipping settings are temporarily unavailable.',
    };
  }

  return { eligible: true, vendorId, shippingPayer, reason: '' };
};
