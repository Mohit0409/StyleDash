import React from 'react'
import { motion } from 'framer-motion'
import CategoryCard from '../components/CategoryCard'
import { categories } from '../data/categories'

const Categories: React.FC = () => (
  <div className="max-w-7xl mx-auto px-4 py-8">
    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
      <h1 className="text-2xl font-black text-gray-900 dark:text-white mb-1">All Categories</h1>
      <p className="text-sm text-gray-400 mb-6">Browse all product categories available in Neemuch</p>
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
        {categories.map((cat, i) => (
          <CategoryCard key={cat.id} category={cat} index={i} />
        ))}
      </div>
    </motion.div>
  </div>
)

export default Categories
