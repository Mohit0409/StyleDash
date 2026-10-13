import React, { useEffect, useRef, useState } from 'react';
const HOME_RAIL_PAGE_SIZE = 5;
import { Link } from 'react-router-dom';
import { ArrowRight, ChevronLeft, ChevronRight } from 'lucide-react';
import type { Product } from '../types';
import { ProductCard } from './ProductCard';

export const HOME_PRODUCT_CARD_WRAP_CLASS =
  'w-[58%] min-w-0 flex-none snap-start sm:w-[42%] md:w-[30%] lg:w-[22%] xl:w-[18%]';

interface HomepageProductSectionProps {
  id?: string;
  title: string;
  subtitle: string;
  href: string;
  products: Product[];
  icon: React.ReactNode;
  testId?: string;
  priorityCount?: number;
}

export const HomepageProductSection: React.FC<HomepageProductSectionProps> = ({
  id,
  title,
  subtitle,
  href,
  products,
  icon,
  testId,
  priorityCount = 0,
}) => {
  const railRef = useRef<HTMLDivElement>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const pageCount = Math.ceil(products.length / HOME_RAIL_PAGE_SIZE);

  useEffect(() => { setCurrentPage(1); }, [products]);

  const goToPage = (page: number) => {
    const rail = railRef.current;
    if (!rail || page < 1 || page > pageCount) return;
    const cards = Array.from(rail.querySelectorAll<HTMLElement>('[data-home-product-card]'));
    const target = cards[(page - 1) * HOME_RAIL_PAGE_SIZE];
    if (!target || !cards[0]) return;
    rail.scrollTo({ left: target.offsetLeft - cards[0].offsetLeft, behavior: 'smooth' });
    setCurrentPage(page);
  };

  const trackSwipePage = () => {
    const rail = railRef.current;
    if (!rail) return;
    const cards = Array.from(rail.querySelectorAll<HTMLElement>('[data-home-product-card]'));
    if (!cards.length) return;
    const left = rail.scrollLeft + cards[0].offsetLeft;
    let closest = 0;
    cards.forEach((card, index) => {
      if (Math.abs(card.offsetLeft - left) < Math.abs(cards[closest].offsetLeft - left)) closest = index;
    });
    const page = Math.floor(closest / HOME_RAIL_PAGE_SIZE) + 1;
    setCurrentPage(previous => previous === page ? previous : page);
  };

  const scrollRail = (direction: -1 | 1) => {
    const rail = railRef.current;
    if (!rail) return;
    rail.scrollBy({
      left: direction * Math.max(rail.clientWidth * 0.82, 240),
      behavior: 'smooth',
    });
  };

  return (
    <section aria-labelledby={id ? `home-${id}` : undefined} className="space-y-5">
      <div className="flex items-end justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <div className="mt-0.5 rounded-xl bg-neutral-950 p-2 text-lime-400 dark:bg-lime-400 dark:text-neutral-950">
            {icon}
          </div>
          <div className="min-w-0">
            <h2 id={id ? `home-${id}` : undefined} className="text-xl font-black text-neutral-900 dark:text-white sm:text-2xl">
              {title}
            </h2>
            <p className="mt-1 text-xs text-neutral-500 sm:text-sm">{subtitle}</p>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-1.5 sm:gap-2">
          {products.length > 1 && (
            <div className="hidden items-center gap-1 sm:flex" aria-label={`${title} carousel controls`}>
              <button
                type="button"
                onClick={() => scrollRail(-1)}
                aria-label={`Previous ${title}`}
                className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-full border border-neutral-200 bg-white text-neutral-700 transition hover:border-neutral-400 hover:text-neutral-950 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-200"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <button
                type="button"
                onClick={() => scrollRail(1)}
                aria-label={`Next ${title}`}
                className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-full border border-neutral-200 bg-white text-neutral-700 transition hover:border-neutral-400 hover:text-neutral-950 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-200"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          )}
          <Link
            to={href}
            className="inline-flex min-h-11 items-center gap-1 text-xs font-black text-lime-700 hover:underline dark:text-lime-400 sm:text-sm"
          >
            View All <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      </div>

      <div
        ref={railRef}
        onScroll={trackSwipePage}
        aria-label={`${title} horizontal product slider`}
        className="flex w-full snap-x snap-mandatory gap-3 overflow-x-auto overscroll-x-contain pb-3 pr-4 scroll-smooth sm:gap-4"
        data-home-section={id}
        data-testid={testId}
      >
        {products.map((product, index) => (
          <div key={product.id} className={HOME_PRODUCT_CARD_WRAP_CLASS} data-home-product-card>
            <ProductCard product={product} priority={index < priorityCount} />
          </div>
        ))}
      </div>
      {pageCount > 1 && (
        <nav aria-label={title + ' product pages'} data-testid={testId ? testId + '-pagination' : undefined}
          className="flex flex-wrap items-center justify-center gap-2">
          <span className="mr-2 text-xs font-semibold text-neutral-500 dark:text-neutral-400">
            Page {currentPage} of {pageCount}
          </span>
          {Array.from({ length: pageCount }, (_, index) => index + 1).map(page => (
            <button key={page} type="button" aria-label={title + ' page ' + page}
              aria-current={currentPage === page ? 'page' : undefined}
              onClick={() => goToPage(page)}
              className={'inline-flex min-h-11 min-w-11 items-center justify-center rounded-xl border px-3 text-xs font-bold transition-colors ' +
                (currentPage === page
                  ? 'border-neutral-950 bg-neutral-950 text-white dark:border-lime-400 dark:bg-lime-400 dark:text-neutral-950'
                  : 'border-neutral-200 bg-white text-neutral-700 hover:border-lime-500 dark:border-neutral-700 dark:bg-neutral-900 dark:text-white')}>
              {page}
            </button>
          ))}
        </nav>
      )}
    </section>
  );
};
