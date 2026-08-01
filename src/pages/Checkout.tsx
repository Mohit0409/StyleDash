import React, { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import { MapPin, Clock, CreditCard, Smartphone, Banknote, ChevronRight } from 'lucide-react'
import { useCart } from '../context/CartContext'
import { useToast } from '../context/ToastContext'
import { trackPurchase } from '../firebase/analytics'

const slots = ['10:00 AM – 12:00 PM', '12:00 PM – 2:00 PM', '2:00 PM – 4:00 PM', '4:00 PM – 6:00 PM', '6:00 PM – 8:00 PM']

const Checkout: React.FC = () => {
  const { items, total, clearCart } = useCart()
  const { showToast } = useToast()
  const navigate = useNavigate()
  const [address, setAddress] = useState({ name: '', phone: '', line1: '', city: 'Neemuch', pincode: '458441' })
  const [slot, setSlot] = useState(slots[0])
  const [payment, setPayment] = useState<'upi' | 'cod' | 'card'>('upi')
  const [loading, setLoading] = useState(false)

  // Redirect if cart is empty — must be in effect, not during render
  useEffect(() => {
    if (items.length === 0) navigate('/', { replace: true })
  }, [items.length, navigate])

  const deliveryFee = total > 300 ? 0 : 30
  const taxes = Math.round(total * 0.05)
  const grand = total + deliveryFee + taxes

  const placeOrder = async () => {
    if (!address.name || !address.phone || !address.line1) {
      showToast('Please fill all address fields', 'error')
      return
    }
    setLoading(true)
    await new Promise(r => setTimeout(r, 1500))
    const orderId = `NB${Date.now().toString().slice(-6)}`
    const itemCount = items.reduce((s, i) => s + i.quantity, 0)
    trackPurchase(orderId, grand, deliveryFee, taxes, itemCount)
    clearCart()
    showToast('Order placed successfully!', 'success')
    navigate('/order-success', { state: { orderId } })
  }

  if (items.length === 0) return null

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-black text-gray-900 dark:text-white mb-6">Checkout</h1>

      <div className="grid grid-cols-1 md:grid-cols-5 gap-6">
        <div className="md:col-span-3 space-y-5">

          {/* Address */}
          <div className="bg-white dark:bg-gray-800 rounded-2xl p-5 border border-gray-100 dark:border-gray-700">
            <div className="flex items-center gap-2 mb-4">
              <MapPin size={16} className="text-brand-green" />
              <h2 className="font-bold text-gray-900 dark:text-white">Delivery Address</h2>
            </div>
            <div className="grid grid-cols-2 gap-3">
              {[
                { label: 'Full Name', key: 'name', placeholder: 'Your name', colSpan: 1 },
                { label: 'Phone', key: 'phone', placeholder: '+91 9XXXXXXXXX', colSpan: 1 },
                { label: 'Address', key: 'line1', placeholder: 'House no., Street, Area', colSpan: 2 },
                { label: 'City', key: 'city', placeholder: 'City', colSpan: 1 },
                { label: 'Pincode', key: 'pincode', placeholder: '458441', colSpan: 1 },
              ].map(f => (
                <div key={f.key} className={f.colSpan === 2 ? 'col-span-2' : ''}>
                  <label className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1 block">{f.label}</label>
                  <input
                    value={(address as Record<string, string>)[f.key]}
                    onChange={e => setAddress(a => ({ ...a, [f.key]: e.target.value }))}
                    placeholder={f.placeholder}
                    className="w-full text-sm bg-gray-100 dark:bg-gray-700 rounded-xl px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-brand-yellow dark:text-white"
                  />
                </div>
              ))}
            </div>
          </div>

          {/* Slot */}
          <div className="bg-white dark:bg-gray-800 rounded-2xl p-5 border border-gray-100 dark:border-gray-700">
            <div className="flex items-center gap-2 mb-4">
              <Clock size={16} className="text-brand-yellow" />
              <h2 className="font-bold text-gray-900 dark:text-white">Delivery Slot</h2>
            </div>
            <div className="grid grid-cols-2 gap-2">
              {slots.map(s => (
                <button
                  key={s}
                  onClick={() => setSlot(s)}
                  className={`text-xs font-medium px-3 py-2.5 rounded-xl border transition-colors ${slot === s ? 'bg-brand-yellow border-brand-yellow text-brand-dark' : 'border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:border-brand-yellow'}`}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>

          {/* Payment */}
          <div className="bg-white dark:bg-gray-800 rounded-2xl p-5 border border-gray-100 dark:border-gray-700">
            <div className="flex items-center gap-2 mb-4">
              <CreditCard size={16} className="text-blue-500" />
              <h2 className="font-bold text-gray-900 dark:text-white">Payment Method</h2>
            </div>
            <div className="space-y-2">
              {[
                { key: 'upi', icon: <Smartphone size={16} />, label: 'UPI / PhonePe / GPay', sub: 'Pay with any UPI app' },
                { key: 'cod', icon: <Banknote size={16} />, label: 'Cash on Delivery', sub: 'Pay when you receive' },
                { key: 'card', icon: <CreditCard size={16} />, label: 'Debit / Credit Card', sub: 'Visa, Mastercard, RuPay' },
              ].map(m => (
                <button
                  key={m.key}
                  onClick={() => setPayment(m.key as typeof payment)}
                  className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl border transition-colors ${payment === m.key ? 'border-brand-yellow bg-brand-yellow/10' : 'border-gray-200 dark:border-gray-700'}`}
                >
                  <div className={payment === m.key ? 'text-brand-dark' : 'text-gray-400'}>{m.icon}</div>
                  <div className="text-left">
                    <p className="text-sm font-semibold text-gray-900 dark:text-white">{m.label}</p>
                    <p className="text-xs text-gray-400">{m.sub}</p>
                  </div>
                  <div className={`ml-auto w-4 h-4 rounded-full border-2 flex-shrink-0 ${payment === m.key ? 'border-brand-yellow bg-brand-yellow' : 'border-gray-300 dark:border-gray-600'}`} />
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Order Summary */}
        <div className="md:col-span-2">
          <div className="bg-white dark:bg-gray-800 rounded-2xl p-5 border border-gray-100 dark:border-gray-700 sticky top-20">
            <h2 className="font-bold text-gray-900 dark:text-white mb-4">Order Summary</h2>
            <div className="space-y-3 max-h-48 overflow-y-auto mb-4">
              {items.map(item => (
                <div key={item.product.id} className="flex items-center gap-2">
                  <img src={item.product.image} alt="" className="w-10 h-10 rounded-lg object-cover" />
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium text-gray-800 dark:text-gray-200 line-clamp-1">{item.product.name}</p>
                    <p className="text-xs text-gray-400">x{item.quantity}</p>
                  </div>
                  <p className="text-sm font-bold text-gray-900 dark:text-white">₹{item.product.price * item.quantity}</p>
                </div>
              ))}
            </div>
            <div className="border-t border-gray-100 dark:border-gray-700 pt-3 space-y-1.5 text-sm">
              <div className="flex justify-between text-gray-500"><span>Subtotal</span><span>₹{total}</span></div>
              <div className="flex justify-between text-gray-500"><span>Delivery</span><span>{deliveryFee === 0 ? <span className="text-brand-green">Free</span> : `₹${deliveryFee}`}</span></div>
              <div className="flex justify-between text-gray-500"><span>Taxes</span><span>₹{taxes}</span></div>
              <div className="flex justify-between font-bold text-gray-900 dark:text-white text-base pt-1.5 border-t border-gray-100 dark:border-gray-700">
                <span>Total</span><span>₹{grand}</span>
              </div>
            </div>
            <motion.button
              whileTap={{ scale: 0.97 }}
              onClick={placeOrder}
              disabled={loading}
              className="w-full mt-5 bg-brand-yellow hover:bg-yellow-400 text-brand-dark font-bold py-3.5 rounded-xl flex items-center justify-center gap-2 transition-colors disabled:opacity-70"
            >
              {loading ? 'Placing Order...' : <><span>Place Order — ₹{grand}</span><ChevronRight size={16} /></>}
            </motion.button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default Checkout
