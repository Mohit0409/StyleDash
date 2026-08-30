import React, { useEffect, useState } from 'react';
import { SEO } from '../components/SEO';
import { ProductCard } from '../components/ProductCard';
import { useWishlist } from '../context/WishlistContext';
import { productRepository } from '../repositories/productRepository';
import { Product } from '../types';

export const Wishlist: React.FC = () => {
  const { wishlistIds } = useWishlist();
  const [products, setProducts] = useState<Product[]>([]);

  useEffect(() => {
    productRepository.getAllProducts().then(all => {
      setProducts(all.filter(p => wishlistIds.includes(p.id)));
    });
  }, [wishlistIds]);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      <SEO title="Saved Wishlist - Vibe4You" noIndex />
      <h1 className="text-2xl sm:text-3xl font-black text-neutral-900 dark:text-white">Saved Wishlist ({products.length})</h1>

      {products.length === 0 ? (
        <div className="p-12 text-center bg-white dark:bg-neutral-900 rounded-3xl border border-neutral-200 dark:border-neutral-800 space-y-3">
          <p className="text-xs text-neutral-500">You haven't saved any fashion items to your wishlist yet.</p>
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          {products.map(p => (
            <ProductCard key={p.id} product={p} />
          ))}
        </div>
      )}
    </div>
  );
};
