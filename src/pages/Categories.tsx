import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { SEO } from '../components/SEO';
import { CATEGORY_DESCRIPTIONS } from '../data/categories';
import { productRepository } from '../repositories/productRepository';
import type { Product } from '../types';
import { buildCatalogueTaxonomy } from '../utils/catalogTaxonomy';

export const Categories: React.FC = () => {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);

  useEffect(() => {
    let active = true;
    productRepository.getAllProducts()
      .then(items => {
        if (active) setProducts(items);
      })
      .catch(() => {
        if (active) setLoadFailed(true);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, []);

  const categories = useMemo(() => buildCatalogueTaxonomy(products), [products]);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      <SEO title="Product Categories - Vibe4You" />
      <div>
        <h1 className="text-2xl sm:text-3xl font-black text-neutral-900 dark:text-white">All Product Categories</h1>
        <p className="mt-2 text-sm text-neutral-600 dark:text-neutral-400">
          Explore products currently available from local shops.
        </p>
      </div>

      {loading && (
        <div role="status" className="py-12 text-center font-bold text-neutral-600 dark:text-neutral-300">
          Loading categories…
        </div>
      )}

      {!loading && loadFailed && (
        <div role="alert" className="rounded-2xl border border-red-200 bg-red-50 p-5 text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
          Categories could not be loaded. Please refresh and try again.
        </div>
      )}

      {!loading && !loadFailed && categories.length === 0 && (
        <div className="rounded-2xl border border-neutral-200 p-8 text-center text-neutral-600 dark:border-neutral-800 dark:text-neutral-300">
          No products are available right now.
        </div>
      )}

      {!loading && !loadFailed && categories.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {categories.map(category => (
            <section key={category.name} className="p-6 bg-white dark:bg-neutral-900 rounded-3xl border border-neutral-200 dark:border-neutral-800 space-y-3 shadow-sm">
              <p className="text-xs font-semibold text-neutral-500 dark:text-neutral-400">
                {CATEGORY_DESCRIPTIONS[category.name] ?? 'Products from local shops'}
              </p>
              <div className="flex items-start justify-between gap-3">
                <h2 className="font-extrabold text-lg text-neutral-900 dark:text-white">{category.name}</h2>
                <span className="shrink-0 rounded-full bg-lime-100 px-2.5 py-1 text-xs font-black text-lime-800 dark:bg-lime-900/50 dark:text-lime-300">
                  {category.count}
                </span>
              </div>
              <div className="flex flex-wrap gap-2 pt-2">
                <Link
                  to={`/products?category=${encodeURIComponent(category.name)}`}
                  className="px-2.5 py-1 rounded-lg bg-neutral-900 text-white dark:bg-white dark:text-neutral-950 text-xs font-bold hover:bg-lime-400 hover:text-neutral-950 transition-colors"
                >
                  All ({category.count})
                </Link>
                {category.subcategories.map(subcategory => (
                  <Link
                    key={subcategory.name}
                    to={`/products?category=${encodeURIComponent(category.name)}&subcategory=${encodeURIComponent(subcategory.name)}`}
                    className="px-2.5 py-1 rounded-lg bg-neutral-100 dark:bg-neutral-800 text-neutral-700 dark:text-neutral-300 text-xs font-bold hover:bg-lime-400 hover:text-neutral-950 transition-colors"
                  >
                    {subcategory.name} ({subcategory.count})
                  </Link>
                ))}
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  );
};
