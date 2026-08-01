import React, { useState, useMemo, useEffect } from 'react'
import { motion } from 'framer-motion'
import { useSearchParams } from 'react-router-dom'
import { SlidersHorizontal, X } from 'lucide-react'
import ProductCard from '../components/ProductCard'
import { products } from '../data/products'
import { categories } from '../data/categories'
import { trackViewItemList } from '../firebase/analytics'

const getCategoryName = (slug: string) =>
  categories.find(c => c.slug === slug)?.name ?? (slug.charAt(0).toUpperCase() + slug.slice(1))

type SortKey = 'default' | 'price_asc' | 'price_desc' | 'rating' | 'discount'

const Products: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams()
  const [sort, setSort] = useState<SortKey>('default')
  const [maxPrice, setMaxPrice] = useState(500)
  const [showFilters, setShowFilters] = useState(false)

  const search = searchParams.get('search') || ''
  const category = searchParams.get('category') || ''

  const filtered = useMemo(() => {
    let list = [...products]
    if (search) list = list.filter(p => p.name.toLowerCase().includes(search.toLowerCase()) || p.category.includes(search.toLowerCase()))
    if (category) list = list.filter(p => p.category === category || p.tags?.includes(category))
    list = list.filter(p => p.price <= maxPrice)
    switch (sort) {
      case 'price_asc': list.sort((a, b) => a.price - b.price); break
      case 'price_desc': list.sort((a, b) => b.price - a.price); break
      case 'rating': list.sort((a, b) => b.rating - a.rating); break
      case 'discount': list.sort((a, b) => b.discount - a.discount); break
    }
    return list
  }, [search, category, maxPrice, sort])

  const clearFilters = () => {
    setSearchParams({})
    setSort('default')
    setMaxPrice(500)
  }

  // Track which list the user is browsing — feeds GA4's catalog/merchandising reports
  useEffect(() => {
    trackViewItemList(category || (search ? `search:${search}` : 'all'), filtered.length)
  }, [category, search, filtered.length])

  return (
    <div className="max-w-7xl mx-auto px-4 py-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-xl font-black text-gray-900 dark:text-white">
            {search ? `Results for "${search}"` : category ? getCategoryName(category) : 'All Products'}
          </h1>
          <p className="text-xs text-gray-400">{filtered.length} products found</p>
        </div>
        <button
          onClick={() => setShowFilters(p => !p)}
          className="flex items-center gap-2 text-sm font-medium bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 px-3 py-2 rounded-xl hover:border-brand-yellow transition-colors"
        >
          <SlidersHorizontal size={14} /> Filters
        </button>
      </div>

      {/* Category chips */}
      <div className="flex gap-2 overflow-x-auto pb-2 mb-4 scrollbar-hide">
        <button
          onClick={() => setSearchParams({})}
          className={`flex-shrink-0 text-xs font-semibold px-3 py-1.5 rounded-full transition-colors ${!category ? 'bg-brand-yellow text-brand-dark' : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300'}`}
        >
          All
        </button>
        {categories.map(c => (
          <button
            key={c.id}
            onClick={() => setSearchParams({ category: c.slug })}
            className={`flex-shrink-0 text-xs font-semibold px-3 py-1.5 rounded-full transition-colors whitespace-nowrap ${category === c.slug ? 'bg-brand-yellow text-brand-dark' : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300'}`}
          >
            {c.icon} {c.name}
          </button>
        ))}
      </div>

      {/* Filters panel */}
      {showFilters && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-white dark:bg-gray-800 border border-gray-100 dark:border-gray-700 rounded-2xl p-4 mb-4 grid grid-cols-1 sm:grid-cols-3 gap-4"
        >
          {/* Sort */}
          <div>
            <p className="text-xs font-bold text-gray-500 dark:text-gray-400 mb-2 uppercase tracking-wide">Sort By</p>
            <select
              value={sort}
              onChange={e => setSort(e.target.value as SortKey)}
              className="w-full text-sm bg-gray-100 dark:bg-gray-700 rounded-xl px-3 py-2 focus:outline-none dark:text-white"
            >
              <option value="default">Default</option>
              <option value="price_asc">Price: Low to High</option>
              <option value="price_desc">Price: High to Low</option>
              <option value="rating">Top Rated</option>
              <option value="discount">Highest Discount</option>
            </select>
          </div>

          {/* Max Price */}
          <div>
            <p className="text-xs font-bold text-gray-500 dark:text-gray-400 mb-2 uppercase tracking-wide">Max Price: ₹{maxPrice}</p>
            <input
              type="range"
              min={10}
              max={500}
              value={maxPrice}
              onChange={e => setMaxPrice(Number(e.target.value))}
              className="w-full accent-brand-yellow"
            />
            <div className="flex justify-between text-xs text-gray-400 mt-1"><span>₹10</span><span>₹500</span></div>
          </div>

          {/* Reset */}
          <div className="flex items-end">
            <button onClick={clearFilters} className="flex items-center gap-1.5 text-sm text-red-500 hover:text-red-600 font-medium">
              <X size={14} /> Clear all filters
            </button>
          </div>
        </motion.div>
      )}

      {/* Grid */}
      {filtered.length === 0 ? (
        <div className="text-center py-20">
          <p className="text-4xl mb-3">🔍</p>
          <p className="text-lg font-semibold text-gray-400">No products found</p>
          <button onClick={clearFilters} className="mt-4 bg-brand-yellow text-brand-dark font-bold px-4 py-2 rounded-xl text-sm">
            Clear filters
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
          {filtered.map((p, i) => (
            <motion.div key={p.id} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: Math.min(i * 0.02, 0.4) }}>
              <ProductCard product={p} />
            </motion.div>
          ))}
        </div>
      )}
    </div>
  )
}

export default Products
