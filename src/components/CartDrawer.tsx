import React, { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, ShoppingCart, Trash2, Plus, Minus, Tag, ArrowRight } from 'lucide-react'
import { useCart } from '../context/CartContext'
import { useNavigate } from 'react-router-dom'
import { coupons } from '../data/banners'
import { useToast } from '../context/ToastContext'
import { trackViewCart, trackApplyCoupon, trackBeginCheckout, trackRemoveFromCart } from '../firebase/analytics'

const CartDrawer: React.FC = () => {
  const { isOpen, setIsOpen, items, updateQty, removeItem, total, clearCart } = useCart()
  const { showToast } = useToast()
  const navigate = useNavigate()
  const [couponInput, setCouponInput] = useState('')
  const [appliedCoupon, setAppliedCoupon] = useState<typeof coupons[0] | null>(null)

  // Track view_cart whenever the drawer is opened with items in it —
  // this is a standard funnel checkpoint between add_to_cart and begin_checkout.
  useEffect(() => {
    if (isOpen && items.length > 0) {
      trackViewCart(total, items.reduce((s, i) => s + i.quantity, 0))
    }
  }, [isOpen]) // eslint-disable-line react-hooks/exhaustive-deps

  const applyCoupon = () => {
    const c = coupons.find(c => c.code.toLowerCase() === couponInput.toLowerCase())
    if (!c) { showToast('Invalid coupon code', 'error'); return }
    if (total < c.minOrder) { showToast(`Minimum order ₹${c.minOrder} required`, 'warning'); return }
    setAppliedCoupon(c)
    trackApplyCoupon(c, total)
    showToast(`Coupon "${c.code}" applied!`, 'success')
  }

  const discount = appliedCoupon
    ? appliedCoupon.type === 'flat'
      ? appliedCoupon.discount
      : Math.min((total * appliedCoupon.discount) / 100, appliedCoupon.maxDiscount || Infinity)
    : 0

  const deliveryFee = total > 300 ? 0 : 30
  const taxes = Math.round((total - discount) * 0.05)
  const grandTotal = total - discount + deliveryFee + taxes

  const checkout = () => {
    trackBeginCheckout(grandTotal, items.reduce((s, i) => s + i.quantity, 0))
    setIsOpen(false)
    navigate('/checkout')
  }

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setIsOpen(false)}
            className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50"
          />
          <motion.div
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 25, stiffness: 200 }}
            className="fixed right-0 top-0 h-full w-full max-w-sm bg-white dark:bg-gray-900 z-50 flex flex-col shadow-2xl"
          >
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100 dark:border-gray-800">
              <div className="flex items-center gap-2">
                <ShoppingCart size={20} className="text-brand-yellow" />
                <span className="font-bold text-gray-900 dark:text-white">Your Cart</span>
                {items.length > 0 && (
                  <span className="bg-brand-yellow text-brand-dark text-xs font-bold px-2 py-0.5 rounded-full">{items.length}</span>
                )}
              </div>
              <button onClick={() => setIsOpen(false)} className="w-8 h-8 flex items-center justify-center rounded-full hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors">
                <X size={18} className="text-gray-600 dark:text-gray-300" />
              </button>
            </div>

            {items.length === 0 ? (
              <div className="flex-1 flex flex-col items-center justify-center gap-4 p-8">
                <ShoppingCart size={56} className="text-gray-200 dark:text-gray-700" />
                <p className="text-gray-400 font-medium">Your cart is empty</p>
                <button
                  onClick={() => { setIsOpen(false); navigate('/products') }}
                  className="bg-brand-yellow text-brand-dark font-bold px-5 py-2.5 rounded-xl hover:bg-yellow-400 transition-colors"
                >
                  Browse Products
                </button>
              </div>
            ) : (
              <>
                {/* Items */}
                <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
                  {items.map(item => (
                    <div key={item.product.id} className="flex items-center gap-3 bg-gray-50 dark:bg-gray-800 rounded-xl p-3">
                      <img src={item.product.image} alt={item.product.name} className="w-14 h-14 rounded-lg object-cover flex-shrink-0" />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-900 dark:text-white line-clamp-1">{item.product.name}</p>
                        <p className="text-xs text-gray-400">{item.product.weight}{item.product.unit}</p>
                        <p className="text-sm font-bold text-gray-900 dark:text-white mt-0.5">₹{item.product.price * item.quantity}</p>
                      </div>
                      <div className="flex flex-col items-end gap-2">
                        <button
                          onClick={() => { trackRemoveFromCart(item.product, item.quantity); removeItem(item.product.id) }}
                          className="text-gray-300 hover:text-red-400 transition-colors"
                        >
                          <Trash2 size={13} />
                        </button>
                        <div className="flex items-center gap-1 bg-brand-yellow rounded-lg">
                          <button onClick={() => updateQty(item.product.id, item.quantity - 1)} className="px-1.5 py-1 text-brand-dark">
                            <Minus size={11} />
                          </button>
                          <span className="text-brand-dark font-bold text-xs px-0.5">{item.quantity}</span>
                          <button onClick={() => updateQty(item.product.id, item.quantity + 1)} className="px-1.5 py-1 text-brand-dark">
                            <Plus size={11} />
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>

                {/* Coupon */}
                <div className="px-4 py-3 border-t border-gray-100 dark:border-gray-800">
                  <div className="flex gap-2">
                    <div className="relative flex-1">
                      <Tag size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                      <input
                        value={couponInput}
                        onChange={e => setCouponInput(e.target.value.toUpperCase())}
                        placeholder="Enter coupon code"
                        className="w-full pl-8 pr-3 py-2 text-xs bg-gray-100 dark:bg-gray-800 rounded-lg border border-transparent focus:border-brand-yellow focus:outline-none dark:text-white"
                      />
                    </div>
                    <button onClick={applyCoupon} className="bg-brand-green text-white text-xs font-bold px-3 py-2 rounded-lg hover:bg-green-600 transition-colors">
                      Apply
                    </button>
                  </div>
                  {appliedCoupon && (
                    <p className="text-xs text-brand-green mt-1.5 font-medium">✓ Saved ₹{Math.round(discount)}!</p>
                  )}
                </div>

                {/* Summary */}
                <div className="px-4 py-3 border-t border-gray-100 dark:border-gray-800 space-y-1.5 text-sm">
                  <div className="flex justify-between text-gray-600 dark:text-gray-400">
                    <span>Subtotal</span><span>₹{total}</span>
                  </div>
                  {discount > 0 && (
                    <div className="flex justify-between text-brand-green">
                      <span>Discount</span><span>-₹{Math.round(discount)}</span>
                    </div>
                  )}
                  <div className="flex justify-between text-gray-600 dark:text-gray-400">
                    <span>Delivery</span><span>{deliveryFee === 0 ? <span className="text-brand-green">Free</span> : `₹${deliveryFee}`}</span>
                  </div>
                  <div className="flex justify-between text-gray-600 dark:text-gray-400">
                    <span>Taxes (5%)</span><span>₹{taxes}</span>
                  </div>
                  <div className="flex justify-between font-bold text-gray-900 dark:text-white pt-1.5 border-t border-gray-100 dark:border-gray-700">
                    <span>Total</span><span>₹{grandTotal}</span>
                  </div>
                </div>

                {/* Checkout */}
                <div className="px-4 pb-6 pt-2">
                  <motion.button
                    whileTap={{ scale: 0.97 }}
                    onClick={checkout}
                    className="w-full bg-brand-yellow hover:bg-yellow-400 text-brand-dark font-bold py-3.5 rounded-xl flex items-center justify-center gap-2 transition-colors"
                  >
                    Proceed to Checkout <ArrowRight size={16} />
                  </motion.button>
                  <button onClick={() => { clearCart(); showToast('Cart cleared', 'info') }} className="w-full text-xs text-gray-400 hover:text-red-400 mt-2 transition-colors">
                    Clear Cart
                  </button>
                </div>
              </>
            )}
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}

export default CartDrawer
