/** Homepage promotional cards. Every target is an internal, accessible public route. */
export interface HomePromoSlide {
  id: string;
  eyebrow: string;
  title: string;
  subtitle: string;
  targetUrl: string;
  ctaLabel?: string;
  imageUrl: string;
  backgroundClassName: string;
}

export const HOME_PROMO_SLIDES: readonly HomePromoSlide[] = [
  {
    id: 'shop-local',
    eyebrow: 'NEEMUCH LOCAL STORES',
    title: 'Discover local shops.',
    subtitle: 'Shop nearby or list your own shop on Vibe4You.',
    targetUrl: '/stores',
    ctaLabel: 'Explore local stores',
    imageUrl: 'https://images.unsplash.com/photo-1441986300917-64674bd600d8?auto=format&fit=crop&w=1400&q=80',
    backgroundClassName: 'bg-stone-900',
  },
  {
    id: 'categories',
    eyebrow: 'ALL CATEGORIES',
    title: 'Find everything you love.',
    subtitle: 'Fashion, groceries, beauty, accessories and more.',
    targetUrl: '/categories',
    ctaLabel: 'Browse categories',
    imageUrl: 'https://images.unsplash.com/photo-1472851294608-062f824d29cc?auto=format&fit=crop&w=1400&q=80',
    backgroundClassName: 'bg-indigo-900',
  },
  {
    id: 'offers',
    eyebrow: 'VIBE4YOU OFFERS',
    title: 'More reasons to smile.',
    subtitle: "Explore today's, weekly and monthly top offers.",
    targetUrl: '/offers',
    ctaLabel: 'Explore offers',
    imageUrl: 'https://images.unsplash.com/photo-1607083206968-13611e3d76db?auto=format&fit=crop&w=1400&q=80',
    backgroundClassName: 'bg-orange-900',
  },
  {
    id: 'new-shops',
    eyebrow: 'NEWLY ADDED STORES',
    title: 'Meet the newest shops.',
    subtitle: 'Fresh local stores, all in one place.',
    targetUrl: '/stores?sort=newest',
    ctaLabel: 'See new shops',
    imageUrl: 'https://images.unsplash.com/photo-1441984904996-e0b6ba687e04?auto=format&fit=crop&w=1400&q=80',
    backgroundClassName: 'bg-emerald-900',
  },
  {
    id: 'beauty',
    eyebrow: 'BEAUTY & CARE',
    title: 'A little everyday glow.',
    subtitle: 'Explore beauty and personal care.',
    targetUrl: '/products?category=Beauty%20%26%20Personal%20Care',
    ctaLabel: 'Shop beauty',
    imageUrl: 'https://images.unsplash.com/photo-1596462502278-27bfdc403348?auto=format&fit=crop&w=1400&q=80',
    backgroundClassName: 'bg-purple-900',
  },
  {
    id: 'budget',
    eyebrow: 'BUDGET-FRIENDLY FINDS',
    title: 'Shop under ₹499.',
    subtitle: 'Browse picks within your budget.',
    targetUrl: '/products?maxPrice=499',
    ctaLabel: 'Shop under ₹499',
    imageUrl: 'https://images.unsplash.com/photo-1515562141207-7a88fb7ce338?auto=format&fit=crop&w=1400&q=80',
    backgroundClassName: 'bg-emerald-900',
  },
];
