import type { Vendor, AdSlot } from '../types'

// Local Neemuch shops + national brands that supply products through the
// platform. Each one pays the platform a commission per sale.
export const vendors: Vendor[] = [
  {
    id: 'vd-pepsico',
    name: 'PepsiCo India (Lay\'s)',
    contactPhone: '+91 98765 11111',
    city: 'National Brand',
    commissionPercent: 8,
    totalSales: 48200,
    totalCommissionEarned: 3856,
    joinedAt: '2025-03-10',
    active: true,
  },
  {
    id: 'vd-coke',
    name: 'Coca-Cola India',
    contactPhone: '+91 98765 22222',
    city: 'National Brand',
    commissionPercent: 6,
    totalSales: 36500,
    totalCommissionEarned: 2190,
    joinedAt: '2025-02-18',
    active: true,
  },
  {
    id: 'vd-gandhi-kirana',
    name: 'Gandhi Nagar Kirana Store',
    contactPhone: '+91 90011 33333',
    city: 'Neemuch',
    commissionPercent: 12,
    totalSales: 18400,
    totalCommissionEarned: 2208,
    joinedAt: '2025-04-02',
    active: true,
  },
  {
    id: 'vd-fresh-mandi',
    name: 'Neemuch Fresh Mandi Suppliers',
    contactPhone: '+91 90011 44444',
    city: 'Neemuch',
    commissionPercent: 10,
    totalSales: 27600,
    totalCommissionEarned: 2760,
    joinedAt: '2025-01-22',
    active: true,
  },
  {
    id: 'vd-station-dairy',
    name: 'Station Road Dairy Co-op',
    contactPhone: '+91 90011 55555',
    city: 'Neemuch',
    commissionPercent: 11,
    totalSales: 15200,
    totalCommissionEarned: 1672,
    joinedAt: '2025-05-14',
    active: true,
  },
]

// Paid placements — vendors pay to feature a banner, a product, or to top
// a category listing for a fixed period. This is the same model Blinkit,
// Zepto, and Swiggy Instamart use to monetize their home feed.
export const adSlots: AdSlot[] = [
  {
    id: 'ad-001',
    type: 'featured_product',
    vendorId: 'vd-pepsico',
    vendorName: 'PepsiCo India (Lay\'s)',
    refId: 's1',
    price: 4500,
    startDate: '2026-06-01',
    endDate: '2026-06-30',
    impressions: 18420,
    clicks: 612,
    status: 'active',
  },
  {
    id: 'ad-002',
    type: 'featured_product',
    vendorId: 'vd-coke',
    vendorName: 'Coca-Cola India',
    refId: 'b1',
    price: 5200,
    startDate: '2026-06-01',
    endDate: '2026-06-30',
    impressions: 21030,
    clicks: 745,
    status: 'active',
  },
  {
    id: 'ad-003',
    type: 'banner',
    vendorId: 'vd-fresh-mandi',
    vendorName: 'Neemuch Fresh Mandi Suppliers',
    refId: 'b2',
    price: 2800,
    startDate: '2026-06-10',
    endDate: '2026-07-10',
    impressions: 9870,
    clicks: 284,
    status: 'active',
  },
  {
    id: 'ad-004',
    type: 'category_top',
    vendorId: 'vd-station-dairy',
    vendorName: 'Station Road Dairy Co-op',
    refId: 'dairy',
    price: 1800,
    startDate: '2026-07-01',
    endDate: '2026-07-31',
    impressions: 0,
    clicks: 0,
    status: 'scheduled',
  },
]

export const getAdRevenueTotal = () =>
  adSlots.reduce((sum, a) => sum + a.price, 0)

export const getActiveAdSlots = () =>
  adSlots.filter(a => a.status === 'active')
