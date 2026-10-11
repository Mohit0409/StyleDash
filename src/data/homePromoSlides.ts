/**
 * Homepage promotional cards. These are evergreen category links, not sale offers.
 * Keep targets internal, live and verifiable; do not advertise unverified discounts.
 */
export interface HomePromoSlide {
  id: string;
  eyebrow: string;
  title: string;
  subtitle: string;
  targetUrl: string;
  imageUrl: string;
  backgroundClassName: string;
}

export const HOME_PROMO_SLIDES: readonly HomePromoSlide[] = [
  {
    id: 'shop-local',
    eyebrow: 'SHOP LOCAL IN NEEMUCH',
    title: 'Your city. Your style.',
    subtitle: 'Discover products from local shops.',
    targetUrl: '/stores',
    imageUrl: 'https://images.unsplash.com/photo-1490481651871-ab68de25d43d?auto=format&fit=crop&w=1400&q=80',
    backgroundClassName: 'bg-indigo-900',
  },
  {
    id: 'womens-fashion',
    eyebrow: "WOMEN'S FASHION",
    title: 'Find your next favourite.',
    subtitle: 'Looks for every mood and moment.',
    targetUrl: '/products?dept=women',
    imageUrl: 'https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?auto=format&fit=crop&w=1400&q=80',
    backgroundClassName: 'bg-fuchsia-900',
  },
  {
    id: 'mens-fashion',
    eyebrow: "MEN'S FASHION",
    title: 'Style starts here.',
    subtitle: 'Explore everyday and occasion wear.',
    targetUrl: '/products?dept=men',
    imageUrl: 'https://images.unsplash.com/photo-1516826957135-700dedea698c?auto=format&fit=crop&w=1400&q=80',
    backgroundClassName: 'bg-slate-900',
  },
  {
    id: 'footwear',
    eyebrow: 'FOOTWEAR PICKS',
    title: 'Step into something new.',
    subtitle: 'Find footwear for every occasion.',
    targetUrl: '/products?category=Footwear',
    imageUrl: 'https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=1400&q=80',
    backgroundClassName: 'bg-rose-900',
  },
  {
    id: 'beauty',
    eyebrow: 'BEAUTY & CARE',
    title: 'A little everyday glow.',
    subtitle: 'Explore beauty and personal care.',
    targetUrl: '/products?category=Beauty%20%26%20Personal%20Care',
    imageUrl: 'https://images.unsplash.com/photo-1596462502278-27bfdc403348?auto=format&fit=crop&w=1400&q=80',
    backgroundClassName: 'bg-purple-900',
  },
  {
    id: 'budget',
    eyebrow: 'BUDGET-FRIENDLY FINDS',
    title: 'Shop under ₹499.',
    subtitle: 'Browse picks within your budget.',
    targetUrl: '/products?maxPrice=499',
    imageUrl: 'https://images.unsplash.com/photo-1515562141207-7a88fb7ce338?auto=format&fit=crop&w=1400&q=80',
    backgroundClassName: 'bg-emerald-900',
  },
];
