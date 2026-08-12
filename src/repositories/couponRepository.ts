import { Coupon } from '../types';
import { MOCK_COUPONS } from '../data/coupons';

export const couponRepository = {
  async getCoupons(): Promise<Coupon[]> {
    return MOCK_COUPONS;
  },
  async validateCoupon(code: string): Promise<Coupon | null> {
    const c = MOCK_COUPONS.find(item => item.code.toUpperCase() === code.toUpperCase() && item.active);
    return c || null;
  }
};
