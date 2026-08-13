import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { SlidersHorizontal } from 'lucide-react';
import { SEO } from '../components/SEO';
import { ProductCard } from '../components/ProductCard';
import { FilterSidebar } from '../components/FilterSidebar';
import { Product } from '../types';
import { productRepository } from '../repositories/productRepository';

export const Products: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [mobileFilterOpen, setMobileFilterOpen] = useState(false);

  // Search parameters state
  const department = searchParams.get('dept') || 'all';
  const brand = searchParams.get('brand') || 'all';
  const size = searchParams.get('size') || 'all';
  const maxPrice = Number(searchParams.get('maxPrice')) || 4999;
  const sortBy = searchParams.get('sort') || 'recommended';
  const searchQuery = searchParams.get('search') || '';
  const filterBadge = searchParams.get('filter') || '';

  useEffect(() => {
    productRepository.getAllProducts().then(data => {
      setProducts(data);
      setLoading(false);
    });
  }, []);

  const updateParam = (key: string, value: string) => {
    const newParams = new URLSearchParams(searchParams);
    if (value && value !== 'all') {
      newParams.set(key, value);
    } else {
      newParams.delete(key);
    }
    setSearchParams(newParams);
  };

  const handleClearAll = () => {
    setSearchParams(new URLSearchParams());
  };

  // Filter products logic
  const filteredProducts = products.filter(p => {
    if (department !== 'all' && p.department !== department) return false;
    if (brand !== 'all' && p.brand !== brand) return false;
    if (size !== 'all' && !p.variants.some(v => v.size === size && v.available === true)) return false;
    if (p.price > maxPrice) return false;

    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      const matchName = p.name.toLowerCase().includes(q);
      const matchBrand = p.brand.toLowerCase().includes(q);
      const matchCategory = p.category.toLowerCase().includes(q);
      const matchTag = p.tags.some(t => t.toLowerCase().includes(q));
      if (!matchName && !matchBrand && !matchCategory && !matchTag) return false;
    }

    if (filterBadge === 'express' && !p.expressDelivery) return false;
    if (filterBadge === 'new' && !p.newArrival) return false;
    if (filterBadge === 'sale' && p.discount === 0) return false;

    return true;
  });

  // Sorting logic
  const sortedProducts = [...filteredProducts].sort((a, b) => {
    if (sortBy === 'price-asc') return a.price - b.price;
    if (sortBy === 'price-desc') return b.price - a.price;
    if (sortBy === 'rating') return b.rating - a.rating;
    if (sortBy === 'newest') return (b.newArrival ? 1 : 0) - (a.newArrival ? 1 : 0);
    if (sortBy === 'discount') return b.discount - a.discount;
    return 0; // recommended
  });

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      <SEO title="Browse Fashion Catalogue - StyleDash" />

      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-neutral-200 dark:border-neutral-800">
        <div>
          <h1 className="text-2xl sm:text-3xl font-black text-neutral-900 dark:text-white capitalize">
            {searchQuery ? `Search results for "${searchQuery}"` : `${department} Fashion Catalogue`}
          </h1>
          <p className="text-xs text-neutral-500 mt-1">
            Showing <strong>{sortedProducts.length}</strong> available items for 60-minute delivery in Neemuch
          </p>
        </div>

        {/* Mobile Filter Trigger Button */}
        <button
          onClick={() => setMobileFilterOpen(true)}
          className="lg:hidden flex items-center justify-center gap-2 px-4 py-2.5 bg-neutral-950 dark:bg-lime-400 text-white dark:text-neutral-950 font-bold text-xs rounded-xl"
        >
          <SlidersHorizontal className="w-4 h-4" /> Filter & Sort
        </button>
      </div>

      <div className="flex gap-8 items-start">
        {/* Filter Sidebar */}
        <FilterSidebar
          department={department}
          setDepartment={(d) => updateParam('dept', d)}
          category=""
          setCategory={() => {}}
          brand={brand}
          setBrand={(b) => updateParam('brand', b)}
          size={size}
          setSize={(s) => updateParam('size', s)}
          maxPrice={maxPrice}
          setMaxPrice={(p) => updateParam('maxPrice', p.toString())}
          sortBy={sortBy}
          setSortBy={(s) => updateParam('sort', s)}
          onClearAll={handleClearAll}
          isOpenMobile={mobileFilterOpen}
          onCloseMobile={() => setMobileFilterOpen(false)}
        />

        {/* Catalogue Product Grid */}
        <div className="flex-1 min-w-0">
          {loading ? (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-6">
              {[1, 2, 3, 4, 6].map(i => (
                <div key={i} className="aspect-[3/4] bg-neutral-200 dark:bg-neutral-800 rounded-2xl animate-pulse" />
              ))}
            </div>
          ) : sortedProducts.length === 0 ? (
            <div className="text-center py-20 bg-white dark:bg-neutral-900 rounded-3xl border border-neutral-200 dark:border-neutral-800 p-8">
              <h3 className="font-extrabold text-lg text-neutral-900 dark:text-white mb-2">No matching products found</h3>
              <p className="text-xs text-neutral-500 mb-6">Try relaxing your search terms or clearing filters to view more items.</p>
              <button
                onClick={handleClearAll}
                className="px-6 py-2.5 bg-neutral-950 dark:bg-lime-400 text-white dark:text-neutral-950 font-bold text-xs rounded-xl"
              >
                Clear All Filters
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4 sm:gap-6">
              {sortedProducts.map(p => (
                <ProductCard key={p.id} product={p} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
