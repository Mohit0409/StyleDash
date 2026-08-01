import { Coupon } from '../types';

export const MOCK_COUPONS: Coupon[] = [
  {
    code: 'STYLE100',
    discountType: 'fixed',
    value: 100,
    minOrderValue: 499,
    active: true,
    expiryDate: '2026-12-31'
  },
  {
    code: 'FIRST20',
    discountType: 'percentage',
    value: 20,
    minOrderValue: 799,
    maxDiscount: 300,
    active: true,
    expiryDate: '2026-12-31'
  },
  {
    code: 'EXPRESS50',
    discountType: 'fixed',
    value: 50,
    minOrderValue: 299,
    active: true,
    expiryDate: '2026-12-31'
  }
];
