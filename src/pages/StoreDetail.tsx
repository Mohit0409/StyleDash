import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { MapPin, Zap, Star, Phone, Mail, Store as StoreIcon } from 'lucide-react';
import { SEO } from '../components/SEO';
import { ProductCard } from '../components/ProductCard';
import { vendorRepository } from '../repositories/vendorRepository';
import { productRepository } from '../repositories/productRepository';
import { VendorStore, Product } from '../types';

export const StoreDetail: React.FC = () => {
  const { slug } = useParams<{ slug: string }>();
  const [store, setStore] = useState<VendorStore | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!slug) return;
    vendorRepository.getStoreBySlug(slug).then(s => {
      setStore(s);
      if (s) {
        productRepository.getAllProducts().then(all => {
          setProducts(all.filter(p => p.vendorId === s.id || p.storeSlug === s.slug));
          setLoading(false);
        });
      } else {
        setLoading(false);
      }
    });
  }, [slug]);

  if (loading) {
    return <div className="max-w-7xl mx-auto p-12 text-center text-xs text-neutral-500">Loading Store...</div>;
  }

  if (!store) {
    return (
      <div className="max-w-md mx-auto p-12 text-center space-y-4">
        <h2 className="text-xl font-bold">Store Not Found</h2>
        <Link to="/stores" className="px-6 py-2.5 bg-neutral-950 text-white text-xs font-bold rounded-xl inline-block">
          Browse All Stores
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      <SEO title={`${store.storeName} - Local Store in Neemuch`} description={store.description} />

      {/* Store Cover Banner */}
      <div className="relative rounded-3xl overflow-hidden aspect-[21/9] bg-neutral-900 border border-neutral-200 dark:border-neutral-800 shadow-xl">
        <img src={store.bannerImage} alt={store.storeName} className="w-full h-full object-cover opacity-60" />
        <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/40 to-transparent flex flex-col justify-end p-6 sm:p-10 space-y-2 text-white">
          <div className="flex items-center gap-2">
            <span className="px-3 py-1 bg-lime-400 text-neutral-950 text-xs font-black rounded-full uppercase">{store.category}</span>
            <span className="flex items-center gap-1 text-xs font-bold text-amber-400 bg-black/60 backdrop-blur-md px-2.5 py-1 rounded-full border border-amber-500/30">
              <Star className="w-3.5 h-3.5 fill-amber-400" /> {store.rating} ({store.reviewCount} ratings)
            </span>
          </div>
          <h1 className="text-2xl sm:text-4xl font-black">{store.storeName}</h1>
          <p className="text-xs sm:text-sm text-neutral-300 max-w-xl">{store.description}</p>

          <div className="flex flex-wrap gap-4 text-xs text-neutral-300 pt-2">
            <span className="flex items-center gap-1"><MapPin className="w-4 h-4 text-lime-400" /> {store.address}</span>
            <span className="flex items-center gap-1 text-lime-400 font-bold"><Zap className="w-4 h-4 fill-lime-400" /> 60-min Express Delivery</span>
          </div>
        </div>
      </div>

      {/* Store Inventory Section */}
      <div className="space-y-6">
        <div className="flex items-center justify-between pb-4 border-b border-neutral-200 dark:border-neutral-800">
          <div>
            <h2 className="text-xl font-black text-neutral-900 dark:text-white">Store Inventory Catalogue</h2>
            <p className="text-xs text-neutral-500">Showing {products.length} live items available at {store.storeName}</p>
          </div>
        </div>

        {products.length === 0 ? (
          <div className="p-12 text-center bg-white dark:bg-neutral-900 rounded-3xl border border-neutral-200 dark:border-neutral-800 text-xs text-neutral-500">
            No active products listed for this store yet.
          </div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 sm:gap-6">
            {products.map(p => (
              <ProductCard key={p.id} product={p} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
