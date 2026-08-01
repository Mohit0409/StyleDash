import React, { useEffect, useState, useRef } from 'react'
import { motion } from 'framer-motion'
import { useNavigate, useLocation } from 'react-router-dom'
import { CheckCircle, Clock, Package, Home } from 'lucide-react'

const DELIVERY_SECONDS = 15 * 60 // 15 minutes

const OrderSuccess: React.FC = () => {
  const navigate = useNavigate()
  const location = useLocation()
  // Single counter in seconds — avoids stale closure on minutes state
  const [remaining, setRemaining] = useState(DELIVERY_SECONDS)
  // Use the real order ID generated at purchase time (passed via navigation
  // state from Checkout) so it matches the ID logged in the purchase event.
  // Falls back to a freshly generated one only if the page was opened directly.
  const fallbackId = useRef(`NB${Date.now().toString().slice(-6)}`).current
  const orderId = (location.state as { orderId?: string } | null)?.orderId ?? fallbackId

  useEffect(() => {
    if (remaining <= 0) return
    const timer = setInterval(() => {
      setRemaining(prev => {
        if (prev <= 1) { clearInterval(timer); return 0 }
        return prev - 1
      })
    }, 1000)
    return () => clearInterval(timer)
  }, []) // run once only

  const minutes = Math.floor(remaining / 60)
  const seconds = remaining % 60

  return (
    <div className="max-w-lg mx-auto px-4 py-16 text-center">
      <motion.div
        initial={{ scale: 0 }}
        animate={{ scale: 1 }}
        transition={{ type: 'spring', damping: 12, stiffness: 150 }}
        className="w-24 h-24 bg-brand-green/10 rounded-full flex items-center justify-center mx-auto mb-6"
      >
        <CheckCircle size={48} className="text-brand-green" />
      </motion.div>

      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}>
        <h1 className="text-2xl font-black text-gray-900 dark:text-white mb-2">Order Placed! 🎉</h1>
        <p className="text-gray-400 text-sm">Order ID: <span className="font-bold text-gray-700 dark:text-gray-300">#{orderId}</span></p>

        {/* Countdown Timer */}
        <div className="mt-6 bg-brand-yellow/10 border border-brand-yellow/30 rounded-2xl p-5">
          <Clock size={20} className="text-brand-yellow mx-auto mb-2" />
          <p className="text-sm font-medium text-gray-600 dark:text-gray-300 mb-1">Estimated Delivery In</p>
          <p className="text-3xl font-black text-gray-900 dark:text-white tabular-nums">
            {String(minutes).padStart(2, '0')}:{String(seconds).padStart(2, '0')}
          </p>
          <p className="text-xs text-gray-400 mt-1">
            {remaining === 0 ? '🎉 Your order has arrived!' : 'minutes remaining'}
          </p>
        </div>

        {/* Progress Steps */}
        <div className="mt-6 flex items-center justify-between px-4">
          {[
            { icon: <CheckCircle size={18} />, label: 'Placed', done: true },
            { icon: <Package size={18} />, label: 'Packing', done: false },
            { icon: <span className="text-base">🛵</span>, label: 'On the way', done: false },
            { icon: <Home size={18} />, label: 'Delivered', done: false },
          ].map((step, i) => (
            <React.Fragment key={i}>
              <div className="flex flex-col items-center gap-1">
                <div className={`w-10 h-10 rounded-full flex items-center justify-center text-sm ${step.done ? 'bg-brand-green text-white' : 'bg-gray-100 dark:bg-gray-800 text-gray-400'}`}>
                  {step.icon}
                </div>
                <span className="text-[10px] text-gray-400 font-medium">{step.label}</span>
              </div>
              {i < 3 && <div className="flex-1 h-0.5 bg-gray-200 dark:bg-gray-700 mx-1 mb-4" />}
            </React.Fragment>
          ))}
        </div>

        <div className="flex gap-3 mt-8">
          <button
            onClick={() => navigate('/orders')}
            className="flex-1 bg-brand-dark dark:bg-white text-white dark:text-brand-dark font-bold py-3 rounded-xl hover:opacity-90 transition-opacity"
          >
            Track Order
          </button>
          <button
            onClick={() => navigate('/')}
            className="flex-1 bg-brand-yellow text-brand-dark font-bold py-3 rounded-xl hover:bg-yellow-400 transition-colors"
          >
            Continue Shopping
          </button>
        </div>
      </motion.div>
    </div>
  )
}

export default OrderSuccess
