import type { Product } from '../types';

export const isExpressDeliveryAvailable = (date = new Date()): boolean => {
  const weekday = new Intl.DateTimeFormat('en-US', {
    timeZone: 'Asia/Kolkata',
    weekday: 'short',
  }).format(date);
  return weekday === 'Sat' || weekday === 'Sun';
};

export const isProductExpressEligible = (
  _product: Pick<Product, 'deliveryType' | 'expressDelivery'>,
): boolean => true;

export interface CartExpressEligibility {
  eligible: boolean;
  ineligibleProductNames: string[];
}

export const cartExpressEligibility = (
  products: Array<Pick<Product, 'name' | 'deliveryType' | 'expressDelivery'>>,
): CartExpressEligibility => {
  return {
    eligible: products.length > 0,
    ineligibleProductNames: [],
  };
};

export const deliveryAvailabilityMessage = (date = new Date()): string =>
  isExpressDeliveryAvailable(date)
    ? 'Normal Delivery and Express Local Delivery are both available this Saturday and Sunday for every product.'
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
