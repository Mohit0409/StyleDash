import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, Zap, ChevronRight, Grid2X2, Trophy } from 'lucide-react';
import { SEO } from '../components/SEO';
import { HomepageMerchandising } from '../components/HomepageMerchandising';
import { ProductCard } from '../components/ProductCard';
import { Product } from '../types';
import { productRepository } from '../repositories/productRepository';
import { BANNERS } from '../data/banners';
import { CONFIG } from '../config';

export const Home: React.FC = () => {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    productRepository.getHomepageProducts().then(data => {
      setProducts(data);
      setLoading(false);
    });
  }, []);

  const topPicks = [...products]
    .sort((first, second) => Number(second.trending) - Number(first.trending) || second.rating - first.rating || second.reviewCount - first.reviewCount)
    .slice(0, 8);
  const topPickIds = new Set(topPicks.map(product => product.id));
  const merchandisingProducts = products.filter(product => !topPickIds.has(product.id));

  return (
    <div className="space-y-10 pb-16 sm:space-y-12">
      <SEO title="Vibe4You - Your look, delivered fast" />

      {/* Hero Section */}
      <section className="relative overflow-hidden bg-neutral-950 px-4 py-8 text-white sm:px-6 sm:py-12 lg:px-8 lg:py-20">
        <div className="mx-auto grid max-w-7xl items-center gap-8 lg:grid-cols-2 lg:gap-12">
          <div className="z-10 space-y-5 sm:space-y-6">
            <div className="inline-flex max-w-full items-center gap-2 rounded-full bg-lime-400 px-3 py-1.5 text-[11px] font-black uppercase tracking-wide text-neutral-950 sm:text-xs sm:tracking-wider">
              <Zap className="w-3.5 h-3.5 fill-neutral-950" /> Same Day Delivery in {CONFIG.SERVICE_CITY}
            </div>

            <h1 className="text-[2.5rem] font-black leading-[0.96] tracking-tight sm:text-6xl sm:leading-none">
              Your look, <br />
              <span className="text-lime-400">delivered fast.</span>
            </h1>

            <p className="max-w-lg text-sm leading-relaxed text-neutral-300 sm:text-base sm:text-neutral-400">
              Trending streetwear, ethnic wear, footwear and last-minute party outfits dispatched from verified local fashion boutiques straight to your doorstep.
            </p>

            <div className="grid grid-cols-2 gap-3 pt-1 sm:flex sm:flex-wrap sm:gap-4 sm:pt-2">
              <Link
                to="/products?dept=women"
                className="inline-flex min-h-11 items-center justify-center rounded-xl bg-lime-400 px-4 py-3 text-sm font-black text-neutral-950 shadow-xl transition-all hover:-translate-y-0.5 hover:bg-lime-300 sm:px-8 sm:py-3.5"
              >
                Shop Women
              </Link>
              <Link
                to="/products?dept=men"
                className="inline-flex min-h-11 items-center justify-center rounded-xl border border-white/30 bg-white/10 px-4 py-3 text-sm font-black text-white transition-all hover:bg-white/20 sm:px-8 sm:py-3.5"
              >
                Shop Men
              </Link>
              <Link
                to="/products?filter=express"
                className="col-span-2 inline-flex min-h-11 items-center justify-center gap-1.5 rounded-xl border border-rose-300/60 px-4 py-3 text-sm font-black text-rose-100 transition-all hover:bg-rose-500/15 sm:col-auto sm:px-6 sm:py-3.5"
              >
                <Zap className="w-4 h-4 fill-white" /> Weekend Express Picks
              </Link>
            </div>

            {/* Quick Specs */}
            <div className="grid grid-cols-3 gap-2 border-t border-neutral-800 pt-5 text-[11px] leading-4 text-neutral-400 sm:gap-4 sm:pt-6 sm:text-xs">
              <div className="rounded-xl bg-white/[0.04] p-3"><strong className="mb-1 block text-sm text-white">Same Day</strong>Fast local delivery</div>
              <div className="rounded-xl bg-white/[0.04] p-3"><strong className="mb-1 block text-sm text-white">Local Stores</strong>Verified local shops</div>
              <Link to="/products?maxPrice=499" className="flex min-h-11 flex-col justify-center rounded-xl bg-white/[0.04] p-3 focus-visible:outline focus-visible:outline-2 focus-visible:outline-lime-400">
                <strong className="mb-1 block text-sm text-white">Budget Picks</strong>Under ₹499
              </Link>
            </div>
          </div>

          {/* Banner Gallery */}
          <div className="group relative">
            <div className="absolute -inset-1 rounded-2xl bg-gradient-to-r from-lime-400 to-emerald-400 opacity-25 blur transition duration-1000 group-hover:opacity-40 sm:rounded-3xl"></div>
            <div className="relative aspect-[16/10] overflow-hidden rounded-2xl border border-neutral-800 shadow-2xl sm:aspect-[4/3] sm:rounded-3xl">
              <img
                src={BANNERS[0].imageUrl}
                alt={BANNERS[0].title}
                fetchPriority="high"
                decoding="async"
                className="h-full w-full object-cover object-center"
              />
              <div className="absolute inset-0 flex flex-col justify-end bg-gradient-to-t from-black/80 via-transparent to-transparent p-4 sm:p-6">
                <span className="text-xs font-bold tracking-wide text-lime-400">Featured collection</span>
                <h2 className="text-xl font-black text-white">{BANNERS[0].title}</h2>
              </div>
            </div>
          </div>
        </div>
      </section>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-16">

        {/* Shop by Department */}
        <section className="space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-black text-neutral-900 dark:text-white sm:text-2xl">Shop by Department</h2>
              <p className="text-xs text-neutral-500">Explore curated collections across all categories</p>
            </div>
            <Link to="/categories" className="inline-flex min-h-11 items-center text-xs font-bold text-lime-600 dark:text-lime-400 hover:underline gap-1">
              All Categories <Grid2X2 className="w-3.5 h-3.5" />
            </Link>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-[repeat(7,minmax(0,1fr))] gap-4">
            {[
              { name: "Men's Fashion", query: 'dept=men', img: 'https://images.unsplash.com/photo-1516826957135-700dedea698c?auto=format&fit=crop&w=500&q=80' },
              { name: "Women's Fashion", query: 'dept=women', img: 'https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?auto=format&fit=crop&w=500&q=80' },
              { name: 'Kids Wear', query: 'dept=kids', img: 'https://images.unsplash.com/photo-1529374255404-311a2a4f1fd9?auto=format&fit=crop&w=500&q=80' },
              { name: 'Footwear', query: 'category=Footwear', img: 'https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=500&q=80' },
              { name: 'Accessories', query: 'category=Accessories', img: 'https://images.unsplash.com/photo-1515562141207-7a88fb7ce338?auto=format&fit=crop&w=500&q=80' },
              { name: 'Beauty & Personal Care', query: 'category=Beauty%20%26%20Personal%20Care', img: 'https://images.unsplash.com/photo-1596462502278-27bfdc403348?auto=format&fit=crop&w=500&q=80' },
              { name: 'Gifts', query: 'category=Gifts', img: 'https://images.unsplash.com/photo-1549465220-1a8b9238cd48?auto=format&fit=crop&w=500&q=80' }
            ].map(item => (
              <Link
                key={item.query}
                to={`/products?${item.query}`}
                className="group relative aspect-square overflow-hidden rounded-2xl border border-neutral-200 shadow-md transition-all duration-300 hover:shadow-xl dark:border-neutral-800 sm:aspect-[3/4]"
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
          <section className="space-y-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="rounded-xl bg-neutral-950 p-2 text-lime-400 dark:bg-lime-400 dark:text-neutral-950"><Trophy className="w-5 h-5" /></div>
                <div><h2 className="text-2xl font-black text-neutral-900 dark:text-white">Top Picks</h2><p className="text-xs text-neutral-500">Customer favourites and highly rated local styles</p></div>
              </div>
              <Link to="/products?sort=rating" className="inline-flex min-h-11 items-center text-xs font-bold text-lime-600 dark:text-lime-400 hover:underline gap-1">View All <ArrowRight className="w-3.5 h-3.5" /></Link>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 sm:gap-6">{topPicks.map(product => <ProductCard key={product.id} product={product} />)}</div>
          </section>
        )}

        <HomepageMerchandising products={merchandisingProducts} fallbackProducts={products} loading={loading} />

      </div>
    </div>
  );
};
