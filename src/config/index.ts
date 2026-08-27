export const CONFIG = {
  BRAND_NAME: import.meta.env.VITE_BRAND_NAME || 'Vibe4You',
  TAGLINE: 'Your City. Your Shops. Your Style.',
  SUPPORTING_MESSAGE: 'Local fashion from trusted stores across your city, delivered fast.',
  SERVICE_CITY: import.meta.env.VITE_SERVICE_CITY || 'Neemuch',
  DEFAULT_PINCODE: import.meta.env.VITE_DEFAULT_PINCODE || '458441',
  EXPRESS_DELIVERY_MINUTES: Number(import.meta.env.VITE_EXPRESS_DELIVERY_MINUTES) || 60,
  FREE_DELIVERY_THRESHOLD: Number(import.meta.env.VITE_FREE_DELIVERY_THRESHOLD) || 999,
  STANDARD_DELIVERY_FEE: 49,
  EXPRESS_DELIVERY_FEE: 79,
  TAX_RATE: 0.05, // 5% GST

  // Current operating details for the limited-area launch.
  // Keep these centralized so the proprietor/grievance contacts can be changed once.
  LEGAL: {
    PROPRIETOR_NAME: 'Mohit Jangd',
    GRIEVANCE_OFFICER: 'Swapnil',
    ADDRESS: 'Alkaloid Colony, Neemuch, Madhya Pradesh 458441, India',
    SUPPORT_EMAIL: 'styledashsupport@gmail.com',
    SUPPORT_PHONE: '+91 8963942394',
    SUPPORT_HOURS: '9:00 AM-9:00 PM IST',
    RETURN_SUPPORT_HOURS: '9:00 AM-1:00 PM IST',
    POLICY_EFFECTIVE_DATE: '14 August 2026',
    EXCHANGE_WINDOW_DAYS: 7,
    ISSUE_REPORT_WINDOW_DAYS: 2,
    RETURN_PICKUP_FEE: 50,
    EXCHANGE_PICKUP_FEE: 50,
    REFUND_TIMELINE_DAYS: 7,
  },
};
