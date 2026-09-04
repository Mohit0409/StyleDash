import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, Gem, MapPin, Sparkles, Store, TrendingUp, UserRound, UsersRound, WalletCards, Zap } from 'lucide-react';
import { ProductCard } from './ProductCard';
import { StoreImage } from './StoreImage';
import { vendorRepository } from '../repositories/vendorRepository';
import type { Product, VendorStore } from '../types';
import { buildHomepageSections, selectHomepageStores, type HomeMerchSectionId } from '../utils/homeMerchandising';

interface HomepageMerchandisingProps {
  products: Product[];
  loading: boolean;
}

const iconFor = (id: HomeMerchSectionId) => {
  if (id === 'express') return <Zap className="h-5 w-5" />;
  if (id === 'new' || id === 'beauty') return <Sparkles className="h-5 w-5" />;
  if (id === 'trending') return <TrendingUp className="h-5 w-5" />;
  if (id === 'under499') return <WalletCards className="h-5 w-5" />;
  if (id === 'women') return <UsersRound className="h-5 w-5" />;
  if (id === 'men') return <UserRound className="h-5 w-5" />;
  return <Gem className="h-5 w-5" />;
};
const rowClass = 'flex snap-x snap-mandatory gap-4 overflow-x-auto pb-2 pr-2 sm:gap-5';
const cardWrapClass = 'min-w-[72%] snap-start sm:min-w-[44%] md:min-w-[31%] lg:min-w-[23%] xl:min-w-[19%]';

export const HomepageMerchandising: React.FC<HomepageMerchandisingProps> = ({ products, loading }) => {
  const sections = useMemo(() => buildHomepageSections(products, 5), [products]);
  const [stores, setStores] = useState<VendorStore[]>([]);

  useEffect(() => {
    let active = true;
    vendorRepository.getAllStores()
      .then(items => { if (active) setStores(selectHomepageStores(items, 5)); })
      .catch(() => { if (active) setStores([]); });
    return () => { active = false; };
  }, []);

  if (loading) {
    return (
      <section aria-label="Loading local styles" className="space-y-5">
        <div className="h-8 w-56 animate-pulse rounded bg-neutral-200 dark:bg-neutral-800" />
        <div className={rowClass}>
          {[0, 1, 2, 3].map(index => (
            <div key={index} className={`${cardWrapClass} aspect-[3/4] animate-pulse rounded-2xl bg-neutral-200 dark:bg-neutral-800`} />
          ))}
        </div>
      </section>
    );
  }
  return (
    <div className="space-y-14 sm:space-y-16" data-testid="homepage-merchandising">
      {sections.map(section => (
        <section key={section.id} aria-labelledby={`home-${section.id}`} className="space-y-5">
          <div className="flex items-end justify-between gap-4">
            <div className="flex min-w-0 items-start gap-3">
              <div className="mt-0.5 rounded-xl bg-neutral-950 p-2 text-lime-400 dark:bg-lime-400 dark:text-neutral-950">
                {iconFor(section.id)}
              </div>
              <div className="min-w-0">
                <h2 id={`home-${section.id}`} className="text-xl font-black text-neutral-900 dark:text-white sm:text-2xl">{section.title}</h2>
                <p className="mt-1 text-xs text-neutral-500 sm:text-sm">{section.subtitle}</p>
              </div>
            </div>
            <Link to={section.href} className="inline-flex shrink-0 items-center gap-1 text-xs font-black text-lime-700 hover:underline dark:text-lime-400 sm:text-sm">
              View All <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>

          <div className={rowClass} data-home-section={section.id}>
            {section.products.map(product => (
              <div key={product.id} className={cardWrapClass}>
                <ProductCard product={product} />
              </div>
            ))}
          </div>
        </section>
      ))}
      {stores.length > 0 && (
        <section aria-labelledby="home-local-stores" className="space-y-5">
          <div className="flex items-end justify-between gap-4">
            <div className="flex items-start gap-3">
              <div className="mt-0.5 rounded-xl bg-neutral-950 p-2 text-lime-400 dark:bg-lime-400 dark:text-neutral-950"><Store className="h-5 w-5" /></div>
              <div>
                <h2 id="home-local-stores" className="text-xl font-black text-neutral-900 dark:text-white sm:text-2xl">Local Stores</h2>
                <p className="mt-1 text-xs text-neutral-500 sm:text-sm">Shop directly from verified neighbourhood stores in Neemuch</p>
              </div>
            </div>
            <Link to="/stores" className="inline-flex shrink-0 items-center gap-1 text-xs font-black text-lime-700 hover:underline dark:text-lime-400 sm:text-sm">
              View All <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>

          <div className={rowClass} data-home-section="stores">
            {stores.map(store => (
              <Link key={store.id} to={`/store/${store.slug}`} className={`${cardWrapClass} group overflow-hidden rounded-2xl border border-neutral-200 bg-white shadow-sm transition hover:-translate-y-0.5 hover:shadow-lg dark:border-neutral-800 dark:bg-neutral-900`}>
                <StoreImage src={store.bannerImage} alt={store.storeName} storeName={store.storeName} kind="cover" loading="lazy" decoding="async" className="aspect-[16/9] w-full object-cover" />
                <div className="space-y-2 p-4">
                  <h3 className="truncate font-black text-neutral-900 dark:text-white">{store.storeName}</h3>
                  <p className="line-clamp-2 text-xs text-neutral-500">{store.description}</p>
                  <p className="flex items-center gap-1 text-xs font-bold text-neutral-500"><MapPin className="h-3.5 w-3.5 text-lime-600" />{store.city}</p>
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}
    </div>
  );
};
