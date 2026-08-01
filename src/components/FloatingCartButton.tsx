import React from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ShoppingCart } from 'lucide-react'
import { useCart } from '../context/CartContext'

const FloatingCartButton: React.FC = () => {
  const { itemCount, total, setIsOpen } = useCart()

  return (
    <AnimatePresence>
      {itemCount > 0 && (
        <motion.button
          initial={{ y: 80, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: 80, opacity: 0 }}
          whileTap={{ scale: 0.96 }}
          onClick={() => setIsOpen(true)}
          className="fixed bottom-6 left-1/2 -translate-x-1/2 md:hidden z-40 bg-brand-yellow text-brand-dark font-bold px-5 py-3.5 rounded-2xl shadow-xl flex items-center gap-3"
        >
          <div className="w-6 h-6 bg-brand-dark text-brand-yellow rounded-lg flex items-center justify-center text-xs font-black">
            {itemCount}
          </div>
          <span className="text-sm">View Cart</span>
          <span className="text-sm">₹{total}</span>
          <ShoppingCart size={16} />
        </motion.button>
      )}
    </AnimatePresence>
  )
}

export default FloatingCartButton
