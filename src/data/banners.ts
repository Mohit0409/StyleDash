import { AdSlot } from '../types';

export const BANNERS: AdSlot[] = [
  {
    id: 'banner-1',
    title: 'Summer Streetwear Collection — Shop Current Deals',
    type: 'banner',
    imageUrl: 'https://images.unsplash.com/photo-1483985988355-763728e1935b?auto=format&fit=crop&w=1200&q=80',
    targetUrl: '/products?filter=sale',
    vendorId: 'v-urban-style',
    impressions: 1240,
    clicks: 185,
    active: true,
    startDate: '2026-08-01',
    endDate: '2026-08-31'
  },
  {
    id: 'banner-2',
    title: 'Weekend Express Fashion Delivery in Neemuch',
    type: 'banner',
    imageUrl: 'https://images.unsplash.com/photo-1490481651871-ab68de25d43d?auto=format&fit=crop&w=1200&q=80',
    targetUrl: '/products?filter=express',
    impressions: 2100,
    clicks: 340,
    active: true,
    startDate: '2026-08-01',
    endDate: '2026-08-31'
  }
];
