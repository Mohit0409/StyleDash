import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { CalendarDays, Clock3, Tag } from 'lucide-react';
import { SEO } from '../components/SEO';
import { ProductCard } from '../components/ProductCard';
import { ProductPagination } from '../components/ProductPagination';
import { useProductPagination } from '../hooks/useProductPagination';
import { productRepository } from '../repositories/productRepository';
import type { Product } from '../types';
import { selectRotatingOffers, type RotatingOfferSection } from '../utils/rotatingOffers';

const PERIOD_INFO = {
  today: {
    icon: Clock3,
    intro: 'A fresh daily selection of currently discounted products.',
  },
  week: {
    icon: CalendarDays,
    intro: "This week's highlights from the local marketplace."
  },
  month: {
    icon: Tag,
    intro: 'Our current monthly selection of savings from local stores.',
  },
} as const;

const OfferProductGrid: React.FC<{ section: RotatingOfferSection }> = ({ section }) => {
  const pagination = useProductPagination(section.products, 8, `${section.period}Page`, true, `offers-${section.period}`);
  return (
    <div className="space-y-3" data-testid={`offers-products-${section.period}`}>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 sm:gap-5">
        {pagination.items.map(item => <ProductCard key={item.id} product={item} />)}
      </div>
      <ProductPagination {...pagination} onPageChange={pagination.changePage}
        label={`${section.period} offers`} testId={`offers-${section.period}-pagination`} />
    </div>
  );
};

export const Offers: React.FC = () => {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);

  useEffect(() => {
    let active = true;
    productRepository.getAllProducts()
      .then(items => { if (active) setProducts(items); })
      .catch(() => { if (active) setLoadFailed(true); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  // Present eight verified discounts per page and 24 rotating picks per period.
  const sections = useMemo(() => selectRotatingOffers(products, new Date(), 24), [products]);
  const hasOffers = sections.some(section => section.products.length > 0);

  return (
    <main className="mx-auto max-w-7xl space-y-8 px-4 py-8 pb-16 sm:px-6 lg:px-8" data-testid="offers-page">
      <SEO title="Today's, Weekly & Monthly Top Offers - Vibe4You" />
      <header className="relative overflow-hidden rounded-3xl bg-neutral-950 px-6 py-9 text-white sm:px-10 sm:py-12">
        <div className="relative z-10 max-w-2xl space-y-3">
          <span className="inline-block rounded-full bg-lime-400 px-3 py-1 text-xs font-black uppercase tracking-widest text-neutral-950">
            Vibe4You Offers
          </span>
          <h1 className="text-3xl font-black leading-tight sm:text-5xl">Great finds. Better prices.</h1>
          <p className="text-sm leading-relaxed text-neutral-200 sm:text-base">
            Explore today's, weekly and monthly top offers from local shops.
            Every price comes from the current Vibe4You catalogue.
          </p>
        </div>
        <div className="pointer-events-none absolute -right-16 -top-24 h-72 w-72 rounded-full bg-lime-400/20 blur-3xl" />
      </header>

      <nav aria-label="Browse offer periods" className="flex flex-wrap gap-2">
        {sections.map(section => (
          <a key={section.period} href={`#offers-${section.period}`}
            className="inline-flex min-h-11 items-center rounded-full border border-neutral-200 bg-white px-4 text-xs font-extrabold text-neutral-800 transition-colors hover:bg-lime-100 dark:border-neutral-700 dark:bg-neutral-900 dark:text-white dark:hover:bg-neutral-800">
            {section.title}
          </a>
        ))}
      </nav>

      <p className="max-w-3xl text-xs leading-relaxed text-neutral-500 dark:text-neutral-400">
        Our picks refresh on an India-time daily, weekly and monthly schedule.
        These are rotating selections of discounted products—not time-limited promotions.
        Discounts and stock may change; verify the current price on the product page.
      </p>

      {loading && (
        <p role="status" className="rounded-2xl bg-neutral-100 p-8 text-center text-sm font-semibold text-neutral-600 dark:bg-neutral-900 dark:text-neutral-300">
          Loading current offers…
        </p>
      )}
      {!loading && loadFailed && (
        <div role="alert" className="rounded-2xl border border-rose-200 bg-rose-50 p-6 text-sm font-semibold text-rose-800 dark:border-rose-900 dark:bg-rose-950/30 dark:text-rose-200">
          Offers could not be loaded. Please refresh or explore the full catalogue.
        </div>
      )}
      {!loading && !loadFailed && !hasOffers && (
        <div className="rounded-2xl border border-neutral-200 p-8 text-center dark:border-neutral-800">
          <p className="font-bold text-neutral-800 dark:text-neutral-100">No verified discounted products are available right now.</p>
          <Link to="/products" className="mt-3 inline-flex min-h-11 items-center text-sm font-extrabold text-lime-700 hover:underline dark:text-lime-400">
            Explore all products
          </Link>
        </div>
      )}

      {!loading && !loadFailed && hasOffers && sections.map(section => {
        const Icon = PERIOD_INFO[section.period].icon;
        return (
          <section id={`offers-${section.period}`} key={section.period} aria-labelledby={`offers-heading-${section.period}`}
            className="scroll-mt-24 space-y-5" data-testid={`offers-section-${section.period}`}>
            <div className="flex items-start gap-3">
              <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-lime-100 text-lime-800 dark:bg-lime-950/40 dark:text-lime-300">
                <Icon className="h-5 w-5" aria-hidden="true" />
              </div>
              <div>
                <h2 id={`offers-heading-${section.period}`} className="text-xl font-black text-neutral-900 dark:text-white sm:text-2xl">
                  {section.title}
                </h2>
                <p className="mt-1 text-xs text-neutral-500 dark:text-neutral-400 sm:text-sm">
                  {PERIOD_INFO[section.period].intro}
                </p>
              </div>
            </div>
            {section.products.length ? (
              <OfferProductGrid section={section} />
            ) : (
              <p className="rounded-2xl border border-neutral-200 p-5 text-sm text-neutral-600 dark:border-neutral-800 dark:text-neutral-300">
                No additional offers in this selection. Explore the other periods or browse all products.
              </p>
            )}
          </section>
        );
      })}

      <Link to="/products" className="inline-flex min-h-11 items-center rounded-full bg-neutral-900 px-5 py-3 text-sm font-bold text-white transition-colors hover:bg-neutral-700 dark:bg-lime-400 dark:text-neutral-950">
        View all products
      </Link>
    </main>
  );
};
