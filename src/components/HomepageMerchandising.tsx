import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, ChevronLeft, ChevronRight, Gem, MapPin, Sparkles, Store, TrendingUp, UserRound, UsersRound, WalletCards, Zap } from 'lucide-react';
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
const storeRailClass = 'flex w-full snap-x snap-mandatory gap-4 overflow-x-auto overscroll-x-contain pb-3 pr-4 scroll-smooth sm:gap-5';
const storeCardClass = 'group flex h-[21rem] basis-[82%] shrink-0 snap-start flex-col overflow-hidden rounded-2xl border border-neutral-200 bg-white shadow-sm transition hover:-translate-y-0.5 hover:shadow-lg dark:border-neutral-800 dark:bg-neutral-900 sm:basis-[47%] md:basis-[31%] lg:basis-[24%]';

export const HomepageMerchandising: React.FC<HomepageMerchandisingProps> = ({ products, loading }) => {
  const sections = useMemo(() => buildHomepageSections(products, 5), [products]);
  const [stores, setStores] = useState<VendorStore[]>([]);
  const storesRailRef = useRef<HTMLDivElement>(null);

  const scrollStores = (direction: -1 | 1) => {
    const rail = storesRailRef.current;
    if (!rail) return;
    rail.scrollBy({ left: direction * Math.max(rail.clientWidth * 0.82, 280), behavior: 'smooth' });
  };

  useEffect(() => {
    let active = true;
    vendorRepository.getAllStores()
      .then(items => { if (active) setStores(selectHomepageStores(items)); })
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
            <div className="flex shrink-0 items-center gap-2">
              <div className="hidden items-center gap-1 md:flex" aria-label="Local Stores carousel controls">
                <button type="button" onClick={() => scrollStores(-1)} aria-label="Previous local stores" className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-neutral-200 bg-white text-neutral-700 transition hover:border-neutral-400 hover:text-neutral-950 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-200">
                  <ChevronLeft className="h-4 w-4" />
                </button>
                <button type="button" onClick={() => scrollStores(1)} aria-label="Next local stores" className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-neutral-200 bg-white text-neutral-700 transition hover:border-neutral-400 hover:text-neutral-950 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-200">
                  <ChevronRight className="h-4 w-4" />
                </button>
              </div>
              <Link to="/stores" className="inline-flex shrink-0 items-center gap-1 text-xs font-black text-lime-700 hover:underline dark:text-lime-400 sm:text-sm">
                View All <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            </div>
          </div>

          <div ref={storesRailRef} className={storeRailClass} data-home-section="stores" data-testid="local-stores-rail">
            {stores.map(store => (
              <Link key={store.id} to={`/store/${store.slug}`} className={storeCardClass} data-store-card>
                <StoreImage src={store.bannerImage} alt={store.storeName} storeName={store.storeName} kind="cover" loading="lazy" decoding="async" className="h-40 w-full shrink-0 object-cover" />
                <div className="flex min-h-0 flex-1 flex-col gap-2 p-4">
                  <h3 className="line-clamp-2 min-h-10 text-base font-black leading-5 text-neutral-900 dark:text-white">{store.storeName}</h3>
                  <div className="flex items-center gap-2 text-[10px] font-bold text-neutral-600 dark:text-neutral-300">
                    <span className="max-w-[58%] truncate rounded-full bg-neutral-100 px-2 py-1 dark:bg-neutral-800">{store.category}</span>
                    <span className="shrink-0 rounded-full bg-lime-100 px-2 py-1 text-lime-800 dark:bg-lime-950 dark:text-lime-300">~{store.deliveryMinutes} min delivery</span>
                  </div>
                  <p className="line-clamp-2 min-h-8 text-xs leading-4 text-neutral-500">{store.description}</p>
                  <p className="mt-auto flex min-w-0 items-center gap-1 text-xs font-bold text-neutral-500"><MapPin className="h-3.5 w-3.5 shrink-0 text-lime-600" /><span className="truncate">{store.city}</span></p>
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}
    </div>
  );
};
