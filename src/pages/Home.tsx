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

  return (
    <div className="space-y-12 pb-16">
      <SEO title="Vibe4You - Your look, delivered fast" />

      {/* Hero Section */}
      <section className="relative overflow-hidden bg-neutral-950 text-white py-16 lg:py-24 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto grid lg:grid-cols-2 gap-12 items-center">
          <div className="space-y-6 z-10">
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-lime-400 text-neutral-950 text-xs font-black uppercase tracking-wider">
              <Zap className="w-3.5 h-3.5 fill-neutral-950" /> FREE Same Day Delivery in {CONFIG.SERVICE_CITY}
            </div>

            <h1 className="text-4xl sm:text-6xl font-black tracking-tight leading-none">
              Your look, <br />
              <span className="text-lime-400">delivered fast.</span>
            </h1>

            <p className="text-neutral-400 text-sm sm:text-base max-w-lg leading-relaxed">
              Trending streetwear, ethnic wear, footwear and last-minute party outfits dispatched from verified local fashion boutiques straight to your doorstep.
            </p>

            <div className="flex flex-wrap gap-4 pt-2">
              <Link
                to="/products?dept=women"
                className="px-8 py-3.5 bg-lime-400 text-neutral-950 font-black rounded-xl text-sm shadow-xl hover:bg-lime-300 transition-all transform hover:-translate-y-0.5"
              >
                Shop Women
              </Link>
              <Link
                to="/products?dept=men"
                className="px-8 py-3.5 bg-neutral-800 text-white font-black rounded-xl text-sm border border-neutral-700 hover:bg-neutral-700 transition-all"
              >
                Shop Men
              </Link>
              <Link
                to="/products?filter=express"
                className="px-6 py-3.5 bg-rose-500 text-white font-black rounded-xl text-sm hover:bg-rose-600 transition-all flex items-center gap-1.5"
              >
                <Zap className="w-4 h-4 fill-white" /> Weekend Express Picks
              </Link>
            </div>

            {/* Quick Specs */}
            <div className="pt-6 border-t border-neutral-800 grid grid-cols-3 gap-4 text-xs text-neutral-400">
              <div><strong className="text-white block text-sm">Free Same Day</strong> Delivery</div>
              <div><strong className="text-white block text-sm">Local Stores</strong> Curated Marketplace</div>
              <div><strong className="text-white block text-sm">7 Days</strong> Easy Size Exchange</div>
            </div>
          </div>

          {/* Banner Gallery */}
          <div className="relative group">
            <div className="absolute -inset-1 bg-gradient-to-r from-lime-400 to-emerald-400 rounded-3xl blur opacity-30 group-hover:opacity-50 transition duration-1000"></div>
            <div className="relative rounded-3xl overflow-hidden aspect-[4/3] shadow-2xl border border-neutral-800">
              <img
                src={BANNERS[0].imageUrl}
                alt={BANNERS[0].title}
                fetchPriority="high"
                decoding="async"
                className="w-full h-full object-cover object-center"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent flex flex-col justify-end p-6">
                <span className="text-xs font-bold text-lime-400 uppercase tracking-widest">Featured Collection</span>
                <h3 className="text-xl font-black text-white">{BANNERS[0].title}</h3>
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
              <h2 className="text-2xl font-black text-neutral-900 dark:text-white">Shop by Department</h2>
              <p className="text-xs text-neutral-500">Explore curated collections across all categories</p>
            </div>
            <Link to="/categories" className="text-xs font-bold text-lime-600 dark:text-lime-400 hover:underline flex items-center gap-1">
              All Categories <Grid2X2 className="w-3.5 h-3.5" />
            </Link>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            {[
              { name: "Men's Fashion", query: 'dept=men', img: 'https://images.unsplash.com/photo-1516826957135-700dedea698c?auto=format&fit=crop&w=500&q=80' },
              { name: "Women's Fashion", query: 'dept=women', img: 'https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?auto=format&fit=crop&w=500&q=80' },
              { name: 'Kids Wear', query: 'dept=kids', img: 'https://images.unsplash.com/photo-1529374255404-311a2a4f1fd9?auto=format&fit=crop&w=500&q=80' },
              { name: 'Footwear', query: 'category=Footwear', img: 'https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=500&q=80' },
              { name: 'Accessories', query: 'category=Accessories', img: 'https://images.unsplash.com/photo-1515562141207-7a88fb7ce338?auto=format&fit=crop&w=500&q=80' },
              { name: 'Beauty & Personal Care', query: 'category=Beauty%20%26%20Personal%20Care', img: 'https://images.unsplash.com/photo-1596462502278-27bfdc403348?auto=format&fit=crop&w=500&q=80' }
            ].map(item => (
              <Link
                key={item.query}
                to={`/products?${item.query}`}
                className="group relative rounded-2xl overflow-hidden aspect-[3/4] shadow-md hover:shadow-xl transition-all duration-300 border border-neutral-200 dark:border-neutral-800"
              >
                <img src={item.img} alt={item.name} loading="lazy" decoding="async" className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" />
                <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/20 to-transparent flex flex-col justify-end p-4">
                  <h3 className="text-white font-extrabold text-sm">{item.name}</h3>
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
              <Link key={price} to={`/products?maxPrice=${price}`} className="rounded-2xl border border-lime-200 bg-lime-50 px-3 py-5 text-center transition-colors hover:bg-lime-100 dark:border-lime-900 dark:bg-lime-950/20 dark:hover:bg-lime-950/40">
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
                <div className="p-2 bg-violet-600 text-white rounded-xl"><Trophy className="w-5 h-5" /></div>
                <div><h2 className="text-2xl font-black text-neutral-900 dark:text-white">Top Picks</h2><p className="text-xs text-neutral-500">Customer favourites and highly rated local styles</p></div>
              </div>
              <Link to="/products?sort=rating" className="text-xs font-bold text-lime-600 dark:text-lime-400 hover:underline flex items-center gap-1">View All <ArrowRight className="w-3.5 h-3.5" /></Link>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 sm:gap-6">{topPicks.map(product => <ProductCard key={product.id} product={product} />)}</div>
          </section>
        )}

        <HomepageMerchandising products={products} loading={loading} />

      </div>
    </div>
  );
};
