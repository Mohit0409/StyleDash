import type { Product } from '../types';

export const isExpressDeliveryAvailable = (date = new Date()): boolean => {
  const weekday = new Intl.DateTimeFormat('en-US', {
    timeZone: 'Asia/Kolkata',
    weekday: 'short',
  }).format(date);
  return weekday === 'Sat' || weekday === 'Sun';
};

export const isProductExpressEligible = (
  product: Pick<Product, 'deliveryType' | 'expressDelivery'>,
): boolean => {
  if (product.deliveryType === 'normal') return false;
  if (product.deliveryType === 'express' || product.deliveryType === 'both') return true;
  return product.expressDelivery === true;
};

export interface CartExpressEligibility {
  eligible: boolean;
  ineligibleProductNames: string[];
}

export const cartExpressEligibility = (
  products: Array<Pick<Product, 'name' | 'deliveryType' | 'expressDelivery'>>,
): CartExpressEligibility => {
  const ineligibleProductNames = [...new Set(
    products.filter(product => !isProductExpressEligible(product)).map(product => product.name),
  )];
  return {
    eligible: products.length > 0 && ineligibleProductNames.length === 0,
    ineligibleProductNames,
  };
};

export const deliveryAvailabilityMessage = (date = new Date()): string =>
  isExpressDeliveryAvailable(date)
    ? 'Local delivery is selected. Express Local Delivery is also available this weekend for eligible items.'
    : 'Local delivery is selected. Express Local Delivery is unavailable Monday–Friday.';

export interface ExpressCatalogueState {
  requested: boolean;
  available: boolean;
  active: boolean;
}

export const expressCatalogueState = (filterBadge: string, date = new Date()): ExpressCatalogueState => {
  const requested = filterBadge === 'express';
  const available = isExpressDeliveryAvailable(date);
  return { requested, available, active: requested && available };
};
