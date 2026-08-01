import React from 'react'
import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import type { Category } from '../types'

interface Props {
  category: Category
  index?: number
}

const CategoryCard: React.FC<Props> = ({ category, index = 0 }) => {
  const navigate = useNavigate()

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05 }}
      whileHover={{ y: -6, scale: 1.03 }}
      onClick={() => navigate(`/products?category=${category.slug}`)}
      className="cursor-pointer group"
    >
      <div className="relative rounded-2xl overflow-hidden shadow-sm border border-gray-100 dark:border-gray-700 bg-white dark:bg-gray-800">
        <div className="relative h-32 overflow-hidden">
          <img
            src={category.image}
            alt={category.name}
            loading="lazy"
            className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-500"
          />
          <div
            className="absolute inset-0 opacity-60"
            style={{ background: `linear-gradient(135deg, ${category.color}88, transparent)` }}
          />
          <div className="absolute top-2 left-2 text-3xl">{category.icon}</div>
        </div>
        <div className="p-3">
          <h3 className="font-semibold text-sm text-gray-900 dark:text-white">{category.name}</h3>
          <p className="text-xs text-gray-400 mt-0.5">{category.productCount}+ items</p>
        </div>
      </div>
    </motion.div>
  )
}

export default CategoryCard
