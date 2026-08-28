import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowRight, Zap, Sparkles, ChevronRight } from 'lucide-react';
import { SEO } from '../components/SEO';
import { ProductCard } from '../components/ProductCard';
import { Product } from '../types';
import { productRepository } from '../repositories/productRepository';
import { BANNERS } from '../data/banners';
import { CONFIG } from '../config';

export const Home: React.FC = () => {
  const navigate = useNavigate();
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    productRepository.getHomepageProducts().then(data => {
      setProducts(data);
      setLoading(false);
    });
  }, []);

  const newDrops = products.filter(p => p.newArrival).slice(0, 8);
  const trending = products.filter(p => p.trending).slice(0, 8);
  const expressPicks = products.filter(p => p.expressDelivery).slice(0, 8);
  const under499 = products.filter(p => p.price <= 499).slice(0, 8);

  return (
    <div className="space-y-12 pb-16">
      <SEO title="Vibe4You - Your look, delivered fast" />

      {/* Hero Section */}
      <section className="relative overflow-hidden bg-neutral-950 text-white py-16 lg:py-24 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto grid lg:grid-cols-2 gap-12 items-center">
          <div className="space-y-6 z-10">
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-lime-400 text-neutral-950 text-xs font-black uppercase tracking-wider">
              <Zap className="w-3.5 h-3.5 fill-neutral-950" /> 60-Minute Fashion Delivery in {CONFIG.SERVICE_CITY}
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
                <Zap className="w-4 h-4 fill-white" /> Express Picks
              </Link>
            </div>

            {/* Quick Specs */}
            <div className="pt-6 border-t border-neutral-800 grid grid-cols-3 gap-4 text-xs text-neutral-400">
              <div><strong className="text-white block text-sm">60 Mins</strong> Hyperlocal Delivery</div>
              <div><strong className="text-white block text-sm">100% Original</strong> Local Stores</div>
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
          </div>

          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            {[
              { name: "Men's Fashion", dept: 'men', img: 'https://images.unsplash.com/photo-1516826957135-700dedea698c?auto=format&fit=crop&w=500&q=80' },
              { name: "Women's Fashion", dept: 'women', img: 'https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?auto=format&fit=crop&w=500&q=80' },
              { name: 'Kids Wear', dept: 'kids', img: 'https://images.unsplash.com/photo-1519238263530-99afd11df2ea?auto=format&fit=crop&w=500&q=80' },
              { name: 'Footwear', dept: 'footwear', img: 'https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=500&q=80' },
              { name: 'Accessories', dept: 'accessories', img: 'https://images.unsplash.com/photo-1523293182086-7651a899d37f?auto=format&fit=crop&w=500&q=80' }
            ].map(item => (
              <Link
                key={item.dept}
                to={`/products?dept=${item.dept}`}
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

        {/* Express Delivery Picks */}
        <section className="space-y-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="p-2 bg-amber-400 text-neutral-950 rounded-xl">
                <Zap className="w-5 h-5 fill-neutral-950" />
              </div>
              <div>
                <h2 className="text-2xl font-black text-neutral-900 dark:text-white">60-Min Express Picks</h2>
                <p className="text-xs text-neutral-500">In stock nearby and ready for immediate dispatch in Neemuch</p>
              </div>
            </div>
            <Link to="/products?filter=express" className="text-xs font-bold text-lime-600 dark:text-lime-400 hover:underline flex items-center gap-1">
              View All <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 sm:gap-6">
            {expressPicks.map(p => (
              <ProductCard key={p.id} product={p} />
            ))}
          </div>
        </section>

        {/* Styles Under 499 */}
        <section className="space-y-6 bg-lime-50 dark:bg-lime-950/20 p-6 sm:p-8 rounded-3xl border border-lime-200 dark:border-lime-900">
          <div className="flex items-center justify-between">
            <div>
              <span className="text-xs font-black uppercase text-lime-700 dark:text-lime-400 tracking-wider">Budget Deals</span>
              <h2 className="text-2xl font-black text-neutral-900 dark:text-white">Styles Under â‚¹499</h2>
            </div>
            <Link to="/products?maxPrice=499" className="text-xs font-bold text-neutral-900 dark:text-white hover:underline flex items-center gap-1">
              Shop All Deals <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 sm:gap-6">
            {under499.map(p => (
              <ProductCard key={p.id} product={p} />
            ))}
          </div>
        </section>

        {/* New Drops */}
        <section className="space-y-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="p-2 bg-emerald-500 text-white rounded-xl">
                <Sparkles className="w-5 h-5" />
              </div>
              <div>
                <h2 className="text-2xl font-black text-neutral-900 dark:text-white">New Drops & Arrivals</h2>
                <p className="text-xs text-neutral-500">Fresh streetwear and seasonal styles added this week</p>
              </div>
            </div>
            <Link to="/products?filter=new" className="text-xs font-bold text-lime-600 dark:text-lime-400 hover:underline flex items-center gap-1">
              View All <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 sm:gap-6">
            {newDrops.map(p => (
              <ProductCard key={p.id} product={p} />
            ))}
          </div>
        </section>

      </div>
    </div>
  );
};
