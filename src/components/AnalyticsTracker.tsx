import React, { useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import { useCart } from '../context/CartContext';
import { trackEvent, trackPageView } from '../services/analytics';

export const AnalyticsTracker: React.FC = () => {
  const location = useLocation();
  const { items, grandTotal, appliedCoupon } = useCart();
  const checkoutNavigationRef = useRef<string | null>(null);

  useEffect(() => {
    void trackPageView(`${location.pathname}${location.search}`);

    if (location.pathname === '/products') {
      const searchTerm = new URLSearchParams(location.search).get('search')?.trim();
      if (searchTerm) void trackEvent('search', { search_term: searchTerm.slice(0, 100) });
    }
  }, [location.pathname, location.search]);

  useEffect(() => {
    if (location.pathname !== '/checkout' || items.length === 0) return;
    if (checkoutNavigationRef.current === location.key) return;
    checkoutNavigationRef.current = location.key;

    void trackEvent('begin_checkout', {
      currency: 'INR',
      value: grandTotal,
      ...(appliedCoupon?.code ? { coupon: appliedCoupon.code } : {}),
      items: items.map((item) => ({
        item_id: item.productId,
        item_name: item.product.name,
        item_brand: item.product.brand,
        item_category: item.product.category,
        item_variant: [item.selectedSize, item.selectedColour].filter(Boolean).join(' / '),
        affiliation: item.product.storeName || 'Vibe4You',
        price: item.unitPrice,
        quantity: item.quantity,
      })),
    });
  }, [appliedCoupon?.code, grandTotal, items, location.key, location.pathname]);

  return null;
};
