import { CONFIG } from '../config';
import { Coupon } from '../types';

interface CartTotalsInput {
  subtotal: number;
  appliedCoupon: Coupon | null;
  deliveryMethod: 'express' | 'standard';
}

export interface CartTotals {
  couponDiscount: number;
  discountTotal: number;
  deliveryFee: number;
  taxes: number;
  grandTotal: number;
}

export const calculateCartTotals = ({
  subtotal,
  appliedCoupon,
  deliveryMethod,
}: CartTotalsInput): CartTotals => {
  let couponDiscount = 0;
  if (appliedCoupon && subtotal >= appliedCoupon.minOrderValue) {
    if (appliedCoupon.discountType === 'fixed') {
      couponDiscount = appliedCoupon.value;
    } else {
      couponDiscount = (subtotal * appliedCoupon.value) / 100;
      if (appliedCoupon.maxDiscount) {
        couponDiscount = Math.min(couponDiscount, appliedCoupon.maxDiscount);
      }
    }
  }

  const deliveryFee = deliveryMethod === 'express'
    ? CONFIG.EXPRESS_DELIVERY_FEE
    : CONFIG.STANDARD_DELIVERY_FEE;
  const taxableMerchandiseTotal = Math.max(0, subtotal - couponDiscount);
  const taxes = Math.round(
    (taxableMerchandiseTotal * CONFIG.TAX_RATE) / (1 + CONFIG.TAX_RATE),
  );
  const grandTotal = taxableMerchandiseTotal + deliveryFee;

  return {
    couponDiscount,
    discountTotal: couponDiscount,
    deliveryFee,
    taxes,
    grandTotal,
  };
};
