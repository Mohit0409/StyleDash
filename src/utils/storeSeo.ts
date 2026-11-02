import type { VendorStore } from '../types';

const ORIGIN = 'https://vibe4you.in';

export const buildStoreSeo = (store: VendorStore) => {
  const city = store.city?.trim() || 'Neemuch';
  const name = store.storeName.trim();
  const category = String(store.category || '').trim();
  const storeDescription = (store.description || '').trim();
  const url = `${ORIGIN}/store/${store.slug}`;
  const opening = `Explore ${name}, a local ${category || 'retail'} store in ${city}, on Vibe4You.`;
  const description = `${opening} ${storeDescription || 'Browse available products from this store.'}`.trim().slice(0, 180);
  const address: Record<string, string> = {
    '@type': 'PostalAddress',
    addressLocality: city,
    addressRegion: 'Madhya Pradesh',
    addressCountry: 'IN',
  };
  if (store.address?.trim()) address.streetAddress = store.address.trim();
  if (store.pincode?.trim()) address.postalCode = store.pincode.trim();

  return {
    title: `${name} | Local ${category || 'Shop'} Store in ${city} | Vibe4You`,
    description,
    image: store.logoImage || store.bannerImage,
    // An empty catalogue provides no purchase choices and is excluded from the sitemap.
    noIndex: store.productCount === 0,
    jsonLd: {
      '@context': 'https://schema.org',
      '@type': 'Store',
      '@id': `${url}#store`,
      name,
      url,
      description: storeDescription || opening,
      address,
    },
  };
};
