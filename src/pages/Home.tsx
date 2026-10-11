import React, { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { ChevronLeft, ChevronRight, Grid2X2, Trophy } from 'lucide-react';
import { SEO } from '../components/SEO';
import { HomepageMerchandising } from '../components/HomepageMerchandising';
import { HomepageProductSection } from '../components/HomepageProductSection';
import { Product } from '../types';
import { productRepository } from '../repositories/productRepository';
import { HomepagePromoCarousel } from '../components/HomepagePromoCarousel';

const DEPARTMENT_CATEGORIES = [
  { name: "Men's Fashion", query: 'dept=men', img: 'https://images.unsplash.com/photo-1516826957135-700dedea698c?auto=format&fit=crop&w=500&q=80' },
  { name: "Women's Fashion", query: 'dept=women', img: 'https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?auto=format&fit=crop&w=500&q=80' },
  { name: 'Kids Wear', query: 'dept=kids', img: 'https://images.unsplash.com/photo-1529374255404-311a2a4f1fd9?auto=format&fit=crop&w=500&q=80' },
  { name: 'Footwear', query: 'category=Footwear', img: 'https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=500&q=80' },
  { name: 'Accessories', query: 'category=Accessories', img: 'https://images.unsplash.com/photo-1515562141207-7a88fb7ce338?auto=format&fit=crop&w=500&q=80' },
  { name: 'Beauty & Personal Care', query: 'category=Beauty%20%26%20Personal%20Care', img: 'https://images.unsplash.com/photo-1596462502278-27bfdc403348?auto=format&fit=crop&w=500&q=80' },
  { name: 'Gifts', query: 'category=Gifts', img: 'https://images.unsplash.com/photo-1549465220-1a8b9238cd48?auto=format&fit=crop&w=500&q=80' },
] as const;

export const Home: React.FC = () => {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const categoryRailRef = useRef<HTMLDivElement>(null);

  const scrollCategories = (direction: -1 | 1) => {
    const rail = categoryRailRef.current;
    if (!rail) return;
    rail.scrollBy({ left: direction * Math.max(rail.clientWidth * 0.78, 260), behavior: 'smooth' });
  };

  useEffect(() => {
    productRepository.getHomepageProducts().then(data => {
      setProducts(data);
      setLoading(false);
    });
  }, []);

  const topPicks = [...products]
    .sort((first, second) => Number(second.trending) - Number(first.trending) || second.rating - first.rating || second.reviewCount - first.reviewCount)
    .slice(0, 10);
  const topPickIds = new Set(topPicks.map(product => product.id));
  const merchandisingProducts = products.filter(product => !topPickIds.has(product.id));

  return (
    <div className="space-y-10 pb-16 sm:space-y-12">
      <SEO title="Vibe4You - Your look, delivered fast" />

      <HomepagePromoCarousel />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-16">

        {/* Shop by Department */}
        <section className="space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-black text-neutral-900 dark:text-white sm:text-2xl">Shop by Department</h2>
              <p className="text-xs text-neutral-500">Explore curated collections across all categories</p>
            </div>
            <div className="flex items-center gap-1.5 sm:gap-2">
              <div className="hidden items-center gap-1 sm:flex" aria-label="Department carousel controls">
                <button type="button" onClick={() => scrollCategories(-1)} aria-label="Previous departments" className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-full border border-neutral-200 bg-white text-neutral-700 transition hover:border-neutral-400 hover:text-neutral-950 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-200">
                  <ChevronLeft className="h-4 w-4" />
                </button>
                <button type="button" onClick={() => scrollCategories(1)} aria-label="Next departments" className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-full border border-neutral-200 bg-white text-neutral-700 transition hover:border-neutral-400 hover:text-neutral-950 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-200">
                  <ChevronRight className="h-4 w-4" />
                </button>
              </div>
              <Link to="/categories" className="inline-flex min-h-11 items-center text-xs font-bold text-lime-600 dark:text-lime-400 hover:underline gap-1">
                All Categories <Grid2X2 className="w-3.5 h-3.5" />
              </Link>
            </div>
          </div>

          <div ref={categoryRailRef} className="flex snap-x snap-mandatory gap-3 overflow-x-auto overscroll-x-contain pb-3 pr-4 scroll-smooth sm:gap-4" data-testid="department-category-rail">
            {DEPARTMENT_CATEGORIES.map(item => (
              <Link
                key={item.query}
                to={`/products?${item.query}`}
                className="group relative h-44 basis-[42%] shrink-0 snap-start overflow-hidden rounded-2xl border border-neutral-200 shadow-sm transition-all duration-300 hover:-translate-y-0.5 hover:shadow-xl dark:border-neutral-800 sm:h-52 sm:basis-40 md:h-56 md:basis-44"
              >
                <img src={item.img} alt={item.name} loading="lazy" decoding="async" className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" />
                <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/20 to-transparent flex flex-col justify-end p-4">
                  <h3 className="flex min-h-10 items-end text-sm font-extrabold text-white">{item.name}</h3>
                  <span className="text-[10px] text-lime-400 font-bold flex items-center gap-1 group-hover:translate-x-1 transition-transform">
                    Explore <ChevronRight className="w-3 h-3" />
                  </span>
                </div>
              </Link>
            ))}
          </div>
        </section>

        <section className="space-y-4" aria-labelledby="shop-by-budget">
          <div>
            <span className="text-xs font-black uppercase text-lime-700 dark:text-lime-400 tracking-wider">Easy on the pocket</span>
            <h2 id="shop-by-budget" className="text-2xl font-black text-neutral-900 dark:text-white">Shop by Budget</h2>
          </div>
          <div className="grid grid-cols-3 gap-3 sm:gap-4">
            {[199, 299, 499].map(price => (
              <Link key={price} to={`/products?maxPrice=${price}`} className="rounded-2xl border border-lime-200 bg-lime-50 px-3 py-4 text-center transition-colors hover:bg-lime-100 dark:border-lime-900 dark:bg-lime-950/20 dark:hover:bg-lime-950/40">
                <span className="block text-xs font-bold text-neutral-600 dark:text-neutral-300">Under</span>
                <span className="mt-1 block text-xl font-black text-neutral-900 dark:text-white">₹{price}</span>
              </Link>
            ))}
          </div>
        </section>

        {topPicks.length > 0 && (
          <HomepageProductSection
            id="top-picks"
            title="Top Picks"
            subtitle="Customer favourites and highly rated local styles"
            href="/products?sort=rating"
            products={topPicks}
            icon={<Trophy className="h-5 w-5" />}
            testId="top-picks-rail"
            priorityCount={2}
          />
        )}

        <HomepageMerchandising products={merchandisingProducts} fallbackProducts={products} loading={loading} />

      </div>
    </div>
  );
};
