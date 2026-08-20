import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Store, MapPin, Zap, Star, ChevronRight, PlusCircle } from 'lucide-react';
import { SEO } from '../components/SEO';
import { vendorRepository } from '../repositories/vendorRepository';
import { VendorStore } from '../types';
import { CONFIG } from '../config';

export const Stores: React.FC = () => {
  const [stores, setStores] = useState<VendorStore[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    vendorRepository.getAllStores().then(s => {
      setStores(s.filter(item => item.approved && item.active));
      setLoading(false);
    });
  }, []);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      <SEO title="Local Partner Stores in Neemuch - StyleDash" />

      {/* Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-8 bg-neutral-950 text-white rounded-3xl relative overflow-hidden shadow-xl">
        <div className="space-y-2 z-10 max-w-xl">
          <span className="text-xs font-black text-lime-400 uppercase tracking-widest">Multi-Store Quick-Commerce Marketplace</span>
          <h1 className="text-2xl sm:text-3xl font-black">Local Boutiques & Partner Stores in {CONFIG.SERVICE_CITY}</h1>
          <p className="text-xs text-neutral-400">
            Shop directly from verified neighbourhood clothing, ethnic wear, and footwear stores with 60-minute doorstep dispatch.
          </p>
        </div>

        <Link
          to="/partner"
          className="z-10 px-6 py-3 bg-lime-400 text-neutral-950 font-black text-xs uppercase tracking-wider rounded-xl hover:bg-lime-300 transition-colors flex items-center gap-2 whitespace-nowrap self-start md:self-auto"
        >
          <PlusCircle className="w-4 h-4" />
          <span>List Your Store on StyleDash</span>
        </Link>
      </div>

      {/* Stores Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {stores.map(store => (
          <div key={store.id} className="group bg-white dark:bg-neutral-900 rounded-3xl border border-neutral-200 dark:border-neutral-800 overflow-hidden shadow-sm hover:shadow-xl transition-all duration-300 flex flex-col">
            <div className="relative aspect-[16/9] bg-neutral-100 dark:bg-neutral-800 overflow-hidden">
              <img src={store.bannerImage} alt={store.storeName} loading="lazy" decoding="async" className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" />
              <div className="absolute top-3 left-3 bg-neutral-950/80 backdrop-blur-md text-white text-[10px] font-black px-2.5 py-1 rounded-full border border-neutral-700">
                {store.category}
              </div>
            </div>

            <div className="p-6 flex-1 flex flex-col justify-between space-y-4">
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <h3 className="font-extrabold text-base text-neutral-900 dark:text-white line-clamp-1">{store.storeName}</h3>
                  <span className="flex items-center gap-1 text-xs font-bold text-amber-500 bg-amber-50 dark:bg-amber-950/40 px-2 py-0.5 rounded-full border border-amber-200 dark:border-amber-800">
                    <Star className="w-3 h-3 fill-amber-400" /> {store.rating}
                  </span>
                </div>

                <p className="text-xs text-neutral-500 line-clamp-2">{store.description}</p>

                <div className="pt-2 text-xs text-neutral-500 space-y-1">
                  <p className="flex items-center gap-1"><MapPin className="w-3.5 h-3.5 text-lime-600" /> {store.address}</p>
                  <p className="flex items-center gap-1 font-bold text-emerald-600 dark:text-emerald-400">
                    <Zap className="w-3.5 h-3.5 fill-emerald-400" /> {store.deliveryMinutes}-Min Express Dispatch
                  </p>
                </div>
              </div>

              <Link
                to={`/store/${store.slug}`}
                className="w-full py-2.5 bg-neutral-950 dark:bg-lime-400 text-white dark:text-neutral-950 text-xs font-extrabold rounded-xl hover:bg-neutral-800 dark:hover:bg-lime-300 transition-colors flex items-center justify-center gap-1"
              >
                <span>Visit Storefront</span>
                <ChevronRight className="w-4 h-4" />
              </Link>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
