import type { Banner, Coupon } from '../types'

export const banners: Banner[] = [
  { id: 'b1', image: 'https://images.unsplash.com/photo-1542838132-92c53300491e?w=1200&q=80', title: 'Fresh Vegetables Daily', subtitle: 'Farm to your door in 10 minutes', link: '/categories/vegetables', bgColor: '#00C853' },
  { id: 'b2', image: 'https://images.unsplash.com/photo-1490474418585-ba9bad8fd0ea?w=1200&q=80', title: 'Fruit Flash Sale 🔥', subtitle: 'Up to 30% off on seasonal fruits', link: '/categories/fruits', bgColor: '#FF6B35' },
  { id: 'b3', image: 'https://images.unsplash.com/photo-1563636619-e9143da7973b?w=1200&q=80', title: 'Dairy Essentials', subtitle: 'Milk, Paneer, Ghee — delivered fresh', link: '/categories/dairy', bgColor: '#2196F3' },
  { id: 'b4', image: 'https://images.unsplash.com/photo-1566478989037-eec170784d0b?w=1200&q=80', title: 'Snack Time Deals', subtitle: 'Stock up on your favourite munchies', link: '/categories/snacks', bgColor: '#FFD400' },
]

export const coupons: Coupon[] = [
  { id: 'c1', code: 'NEWUSER', discount: 50, type: 'flat', minOrder: 200, description: '₹50 off on your first order', validTill: '2025-12-31' },
  { id: 'c2', code: 'FRESH20', discount: 20, type: 'percent', minOrder: 300, maxDiscount: 100, description: '20% off on fresh produce', validTill: '2025-12-31' },
  { id: 'c3', code: 'BLINK10', discount: 10, type: 'percent', minOrder: 150, maxDiscount: 50, description: '10% off on any order', validTill: '2025-12-31' },
  { id: 'c4', code: 'FREEDEL', discount: 30, type: 'flat', minOrder: 250, description: 'Free delivery + ₹30 off', validTill: '2025-12-31' },
]
