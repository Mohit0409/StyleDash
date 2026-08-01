import React, { useRef, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Heart, Star, Plus, Minus, Megaphone } from 'lucide-react'
import { useCart } from '../context/CartContext'
import { useWishlist } from '../context/WishlistContext'
import { useToast } from '../context/ToastContext'
import { trackAddToCart, trackAddToWishlist, trackAdImpression, trackAdClick } from '../firebase/analytics'
import type { Product } from '../types'

interface Props {
  product: Product
}

const ProductCard: React.FC<Props> = ({ product }) => {
  const { items, addItem, updateQty } = useCart()
  const { toggle, has } = useWishlist()
  const { showToast } = useToast()
  const cardRef = useRef<HTMLDivElement>(null)
  const impressionFired = useRef(false)
  const cartItem = items.find(i => i.product.id === product.id)
  const qty = cartItem?.quantity || 0
  const inWishlist = has(product.id)

  // Fire an ad impression once, only when a sponsored card is actually
  // scrolled into view — this is what real ad platforms bill against,
  // not just "rendered in the DOM somewhere off-screen".
  useEffect(() => {
    if (!product.sponsored || !cardRef.current) return
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !impressionFired.current) {
          impressionFired.current = true
          trackAdImpression(`sponsored-${product.id}`, product.vendorId || 'unknown', product.id)
          observer.disconnect()
        }
      },
      { threshold: 0.5 }
    )
    observer.observe(cardRef.current)
    return () => observer.disconnect()
  }, [product.sponsored, product.id, product.vendorId])

  const handleAdd = (e: React.MouseEvent) => {
    e.preventDefault()
    addItem(product)
    trackAddToCart(product, 1)
    if (product.sponsored) trackAdClick(`sponsored-${product.id}`, product.vendorId || 'unknown', product.id)
    showToast(`${product.name} added to cart`, 'success')
  }

  const handleWishlist = (e: React.MouseEvent) => {
    e.preventDefault()
    toggle(product)
    if (!inWishlist) trackAddToWishlist(product)
    showToast(inWishlist ? 'Removed from wishlist' : 'Added to wishlist', inWishlist ? 'info' : 'success')
  }

  return (
    <motion.div
      ref={cardRef}
      whileHover={{ y: -4, boxShadow: '0 20px 40px rgba(0,0,0,0.12)' }}
      transition={{ duration: 0.2 }}
      className={`relative bg-white dark:bg-gray-800 rounded-2xl overflow-hidden shadow-sm border group ${product.sponsored ? 'border-brand-yellow/60' : 'border-gray-100 dark:border-gray-700'}`}
    >
      {/* Sponsored label — required disclosure for paid placements */}
      {product.sponsored && (
        <span className="absolute top-2 left-2 z-10 flex items-center gap-1 bg-brand-dark/90 text-brand-yellow text-[9px] font-bold px-2 py-0.5 rounded-full">
          <Megaphone size={9} /> Sponsored
        </span>
      )}
      {/* Badge */}
      {product.badge && !product.sponsored && (
        <span className="absolute top-2 left-2 z-10 bg-brand-green text-white text-[10px] font-bold px-2 py-0.5 rounded-full">
          {product.badge}
        </span>
      )}
      {product.discount > 0 && (
        <span className="absolute top-2 right-10 z-10 bg-brand-yellow text-brand-dark text-[10px] font-bold px-2 py-0.5 rounded-full">
          {product.discount}% OFF
        </span>
      )}

      {/* Wishlist */}
      <button
        onClick={handleWishlist}
        className="absolute top-2 right-2 z-10 w-7 h-7 flex items-center justify-center rounded-full bg-white dark:bg-gray-700 shadow-sm"
      >
        <Heart
          size={14}
          className={inWishlist ? 'fill-red-500 text-red-500' : 'text-gray-400'}
        />
      </button>

      {/* Image */}
      <div className="relative h-36 bg-gray-50 dark:bg-gray-700 overflow-hidden">
        <img
          src={product.image}
          alt={product.name}
          loading="lazy"
          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
        />
      </div>

      {/* Info */}
      <div className="p-3">
        <p className="text-xs text-gray-400 mb-0.5 capitalize">{product.category}</p>
        <h3 className="font-semibold text-gray-900 dark:text-white text-sm leading-snug line-clamp-2 mb-1">
          {product.name}
        </h3>
        <p className="text-xs text-gray-400 mb-2">{product.weight}{product.unit}</p>

        {/* Rating */}
        <div className="flex items-center gap-1 mb-2">
          <Star size={11} className="fill-amber-400 text-amber-400" />
          <span className="text-xs text-gray-600 dark:text-gray-300">{product.rating}</span>
          <span className="text-xs text-gray-400">({product.reviewCount})</span>
        </div>

        {/* Price + Cart */}
        <div className="flex items-center justify-between">
          <div>
            <span className="font-bold text-gray-900 dark:text-white">₹{product.price}</span>
            {product.originalPrice > product.price && (
              <span className="text-xs text-gray-400 line-through ml-1">₹{product.originalPrice}</span>
            )}
          </div>

          {qty === 0 ? (
            <motion.button
              whileTap={{ scale: 0.9 }}
              onClick={handleAdd}
              className="flex items-center gap-1 bg-brand-yellow hover:bg-yellow-400 text-brand-dark text-xs font-bold px-3 py-1.5 rounded-xl transition-colors"
            >
              <Plus size={12} /> Add
            </motion.button>
          ) : (
            <div className="flex items-center gap-1.5 bg-brand-yellow rounded-xl overflow-hidden">
              <button
                onClick={(e) => { e.preventDefault(); updateQty(product.id, qty - 1) }}
                className="px-2 py-1.5 text-brand-dark hover:bg-yellow-400 transition-colors"
              >
                <Minus size={12} />
              </button>
              <span className="text-brand-dark font-bold text-sm min-w-[16px] text-center">{qty}</span>
              <button
                onClick={(e) => { e.preventDefault(); updateQty(product.id, qty + 1) }}
                className="px-2 py-1.5 text-brand-dark hover:bg-yellow-400 transition-colors"
              >
                <Plus size={12} />
              </button>
            </div>
          )}
        </div>
      </div>
    </motion.div>
  )
}

export default ProductCard
