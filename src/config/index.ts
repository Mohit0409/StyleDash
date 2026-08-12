export const CONFIG = {
  BRAND_NAME: import.meta.env.VITE_BRAND_NAME || 'StyleDash',
  TAGLINE: 'Your look, delivered fast.',
  SUPPORTING_MESSAGE: 'Fashion essentials and trending styles delivered from nearby stores.',
  SERVICE_CITY: import.meta.env.VITE_SERVICE_CITY || 'Neemuch',
  DEFAULT_PINCODE: import.meta.env.VITE_DEFAULT_PINCODE || '458441',
  EXPRESS_DELIVERY_MINUTES: Number(import.meta.env.VITE_EXPRESS_DELIVERY_MINUTES) || 60,
  FREE_DELIVERY_THRESHOLD: Number(import.meta.env.VITE_FREE_DELIVERY_THRESHOLD) || 999,
  STANDARD_DELIVERY_FEE: 49,
  EXPRESS_DELIVERY_FEE: 79,
  TAX_RATE: 0.05, // 5% GST
};
