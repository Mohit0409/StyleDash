import React from 'react';
import { Link } from 'react-router-dom';
import { SEO } from '../components/SEO';
import { CATEGORIES } from '../data/categories';

export const Categories: React.FC = () => {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      <SEO title="Fashion Categories - Vibe4You" />
      <h1 className="text-2xl sm:text-3xl font-black text-neutral-900 dark:text-white">All Fashion Categories</h1>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
        {CATEGORIES.map(cat => (
          <div key={cat.id} className="p-6 bg-white dark:bg-neutral-900 rounded-3xl border border-neutral-200 dark:border-neutral-800 space-y-3 shadow-sm">
            <span className="text-[10px] font-black uppercase tracking-widest text-lime-600 dark:text-lime-400">{cat.department}</span>
            <h3 className="font-extrabold text-lg text-neutral-900 dark:text-white">{cat.name}</h3>
            <div className="flex flex-wrap gap-2 pt-2">
              {cat.subcategories.map(sub => (
                <Link
                  key={sub}
                  to={`/products?dept=${encodeURIComponent(cat.department)}&category=${encodeURIComponent(cat.name)}&subcategory=${encodeURIComponent(sub)}`}
                  className="px-2.5 py-1 rounded-lg bg-neutral-100 dark:bg-neutral-800 text-neutral-700 dark:text-neutral-300 text-xs font-bold hover:bg-lime-400 hover:text-neutral-950 transition-colors"
                >
                  {sub}
                </Link>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
