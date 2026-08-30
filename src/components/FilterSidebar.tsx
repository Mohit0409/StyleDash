import React, { useEffect } from 'react';
import { X, SlidersHorizontal, RotateCcw } from 'lucide-react';

interface FilterSidebarProps {
  department: string;
  setDepartment: (dept: string) => void;
  category: string;
  setCategory: (cat: string) => void;
  brand: string;
  setBrand: (b: string) => void;
  size: string;
  setSize: (s: string) => void;
  maxPrice: number;
  setMaxPrice: (p: number) => void;
  sortBy: string;
  setSortBy: (s: string) => void;
  onClearAll: () => void;
  isOpenMobile?: boolean;
  onCloseMobile?: () => void;
}

export const FilterSidebar: React.FC<FilterSidebarProps> = ({
  department,
  setDepartment,
  category,
  setCategory,
  brand,
  setBrand,
  size,
  setSize,
  maxPrice,
  setMaxPrice,
  sortBy,
  setSortBy,
  onClearAll,
  isOpenMobile,
  onCloseMobile
}) => {
  useEffect(() => {
    if (!isOpenMobile) return undefined;
    const onKeyDown = (event: KeyboardEvent) => { if (event.key === 'Escape') onCloseMobile?.(); };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [isOpenMobile, onCloseMobile]);

  const content = (
    <div className="space-y-6 text-sm text-neutral-800 dark:text-neutral-200">
      
      {/* Title & Clear */}
      <div className="flex items-center justify-between pb-4 border-b border-neutral-200 dark:border-neutral-800">
        <div className="flex items-center gap-2 font-black text-base text-neutral-900 dark:text-white">
          <SlidersHorizontal className="w-5 h-5 text-lime-500" />
          <span>Filters</span>
        </div>
        <button
          onClick={onClearAll}
          className="text-xs font-bold text-rose-500 hover:underline flex items-center gap-1"
        >
          <RotateCcw className="w-3.5 h-3.5" /> Clear All
        </button>
      </div>

      {/* Sort By */}
      <div>
        <label className="block text-xs font-bold uppercase tracking-wider text-neutral-500 mb-2">Sort By</label>
        <select
          aria-label="Sort products"
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value)}
          className="w-full p-2.5 rounded-xl border border-neutral-300 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-800 font-medium text-xs focus:ring-2 focus:ring-lime-400"
        >
          <option value="recommended">Recommended</option>
          <option value="price-asc">Price: Low to High</option>
          <option value="price-desc">Price: High to Low</option>
          <option value="rating">Highest Rated</option>
          <option value="newest">Newest Drops</option>
          <option value="discount">Biggest Discount</option>
        </select>
      </div>

      {/* Department Filter */}
      <div>
        <label className="block text-xs font-bold uppercase tracking-wider text-neutral-500 mb-2">Department</label>
        <div className="flex flex-wrap gap-2">
          {['all', 'men', 'women', 'kids', 'footwear', 'accessories'].map(d => (
            <button
              key={d}
              onClick={() => setDepartment(d)}
              className={`px-3 py-1.5 rounded-xl text-xs font-bold uppercase border transition-all ${
                department === d
                  ? 'bg-neutral-950 dark:bg-lime-400 text-white dark:text-neutral-950 border-neutral-950 dark:border-lime-400'
                  : 'bg-neutral-100 dark:bg-neutral-800 text-neutral-700 dark:text-neutral-300 border-transparent hover:border-neutral-300'
              }`}
            >
              {d}
            </button>
          ))}
        </div>
      </div>

      {/* Size Filter */}
      <div>
        <label className="block text-xs font-bold uppercase tracking-wider text-neutral-500 mb-2">Size</label>
        <div className="flex flex-wrap gap-1.5">
          {['all', 'S', 'M', 'L', 'XL', 'XXL', 'UK 6', 'UK 7', 'UK 8', 'UK 9'].map(s => (
            <button
              key={s}
              onClick={() => setSize(s)}
              className={`px-2.5 py-1 rounded-lg text-xs font-extrabold border transition-all ${
                size === s
                  ? 'bg-neutral-950 dark:bg-lime-400 text-white dark:text-neutral-950 border-neutral-950 dark:border-lime-400'
                  : 'bg-neutral-100 dark:bg-neutral-800 text-neutral-700 dark:text-neutral-300 border-transparent hover:border-neutral-300'
              }`}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {/* Price Range Slider */}
      <div>
        <div className="flex justify-between items-center mb-2">
          <label className="text-xs font-bold uppercase tracking-wider text-neutral-500">Max Price</label>
          <span className="text-xs font-black text-lime-600 dark:text-lime-400">₹{maxPrice}</span>
        </div>
        <input
          aria-label="Maximum price"
          type="range"
          min={299}
          max={4999}
          step={100}
          value={maxPrice}
          onChange={(e) => setMaxPrice(Number(e.target.value))}
          className="w-full accent-lime-500 cursor-pointer"
        />
        <div className="flex justify-between text-[10px] text-neutral-400 mt-1">
          <span>₹299</span>
          <span>₹4,999</span>
        </div>
      </div>

      {/* Brand Filter */}
      <div>
        <label className="block text-xs font-bold uppercase tracking-wider text-neutral-500 mb-2">Brand</label>
        <div className="space-y-1 max-h-40 overflow-y-auto pr-2 no-scrollbar">
          {['all', 'Roadster', 'HRX', 'Vibe4You Studio', 'Anouk', 'Mast & Harbour', 'Highlander', 'Snitch'].map(b => (
            <label key={b} className="flex items-center gap-2 text-xs font-medium cursor-pointer py-1">
              <input
                type="radio"
                name="brand"
                checked={brand === b}
                onChange={() => setBrand(b)}
                className="accent-lime-500"
              />
              <span className={brand === b ? 'font-bold text-neutral-900 dark:text-white' : ''}>{b === 'all' ? 'All Brands' : b}</span>
            </label>
          ))}
        </div>
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop Sidebar */}
      <div className="hidden lg:block w-64 bg-white dark:bg-neutral-900 p-6 rounded-3xl border border-neutral-200 dark:border-neutral-800 shadow-sm h-fit sticky top-24">
        {content}
      </div>

      {/* Mobile Drawer */}
      {isOpenMobile && (
        <div className="fixed inset-0 z-50 lg:hidden flex bg-black/60 backdrop-blur-sm animate-fade-in">
          <div role="dialog" aria-modal="true" aria-labelledby="mobile-filter-heading" className="w-80 bg-white dark:bg-neutral-900 h-full p-6 overflow-y-auto shadow-2xl flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-6">
                <span id="mobile-filter-heading" className="font-extrabold text-lg text-neutral-900 dark:text-white">Filter & Sort</span>
                <button aria-label="Close filters" onClick={onCloseMobile} className="p-2 rounded-full hover:bg-neutral-100 dark:hover:bg-neutral-800">
                  <X className="w-5 h-5" />
                </button>
              </div>
              {content}
            </div>
            <button
              onClick={onCloseMobile}
              className="mt-6 w-full py-3 bg-neutral-950 dark:bg-lime-400 text-white dark:text-neutral-950 font-bold text-sm rounded-xl"
            >
              Apply Filters
            </button>
          </div>
        </div>
      )}
    </>
  );
};
