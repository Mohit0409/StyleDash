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

  const isFreeDelivery = subtotal >= CONFIG.FREE_DELIVERY_THRESHOLD;
  const baseDeliveryFee = deliveryMethod === 'express'
    ? CONFIG.EXPRESS_DELIVERY_FEE
    : CONFIG.STANDARD_DELIVERY_FEE;
  const deliveryFee = isFreeDelivery ? 0 : baseDeliveryFee;
  const taxes = Math.round((subtotal - couponDiscount) * CONFIG.TAX_RATE);
  const grandTotal = Math.max(0, subtotal - couponDiscount + deliveryFee + taxes);

  return {
    couponDiscount,
    discountTotal: couponDiscount,
    deliveryFee,
    taxes,
    grandTotal,
  };
};
