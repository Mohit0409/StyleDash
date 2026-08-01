import React from 'react'
import { motion } from 'framer-motion'
import { Heart } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import ProductCard from '../components/ProductCard'
import { useWishlist } from '../context/WishlistContext'

const Wishlist: React.FC = () => {
  const { items } = useWishlist()
  const navigate = useNavigate()

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <div className="flex items-center gap-2 mb-6">
        <Heart size={20} className="text-red-500 fill-red-500" />
        <h1 className="text-2xl font-black text-gray-900 dark:text-white">Wishlist</h1>
        <span className="bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300 text-sm font-bold px-2.5 py-0.5 rounded-full">{items.length}</span>
      </div>

      {items.length === 0 ? (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-center py-20">
          <Heart size={56} className="text-gray-200 dark:text-gray-700 mx-auto mb-3" />
          <p className="text-gray-400 font-medium mb-4">Your wishlist is empty</p>
          <button
            onClick={() => navigate('/products')}
            className="bg-brand-yellow text-brand-dark font-bold px-5 py-2.5 rounded-xl hover:bg-yellow-400 transition-colors"
          >
            Discover Products
          </button>
        </motion.div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
          {items.map((p, i) => (
            <motion.div key={p.id} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}>
              <ProductCard product={p} />
            </motion.div>
          ))}
        </div>
      )}
    </div>
  )
}

export default Wishlist
