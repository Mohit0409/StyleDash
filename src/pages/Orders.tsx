import React from 'react'
import { motion } from 'framer-motion'
import { Package, CheckCircle, Truck, Clock } from 'lucide-react'
import { products } from '../data/products'
import type { Order } from '../types'

type MockOrder = {
  id: string
  date: string
  status: Order['status']
  items: { product: typeof products[0]; quantity: number }[]
  total: number
  address: string
}

const mockOrders: MockOrder[] = [
  {
    id: 'NB001234',
    date: '14 June 2025',
    status: 'delivered',
    items: [{ product: products[0], quantity: 2 }, { product: products[20], quantity: 1 }],
    total: 112,
    address: 'Gandhi Nagar, Neemuch – 458441',
  },
  {
    id: 'NB001233',
    date: '12 June 2025',
    status: 'out_for_delivery',
    items: [{ product: products[10], quantity: 3 }, { product: products[30], quantity: 2 }],
    total: 245,
    address: 'Station Road, Neemuch – 458441',
  },
  {
    id: 'NB001232',
    date: '10 June 2025',
    status: 'placed',
    items: [{ product: products[5], quantity: 1 }],
    total: 30,
    address: 'Civil Lines, Neemuch – 458441',
  },
]

const statusConfig: Record<Order['status'], { label: string; color: string; bg: string; step: number }> = {
  placed:            { label: 'Order Placed',      color: 'text-blue-500',        bg: 'bg-blue-50 dark:bg-blue-900/20',    step: 0 },
  packed:            { label: 'Packed',             color: 'text-orange-500',      bg: 'bg-orange-50 dark:bg-orange-900/20', step: 1 },
  out_for_delivery:  { label: 'Out for Delivery',   color: 'text-brand-yellow',    bg: 'bg-yellow-50 dark:bg-yellow-900/20', step: 2 },
  delivered:         { label: 'Delivered',          color: 'text-brand-green',     bg: 'bg-green-50 dark:bg-green-900/20',  step: 3 },
  cancelled:         { label: 'Cancelled',          color: 'text-red-500',         bg: 'bg-red-50 dark:bg-red-900/20',      step: -1 },
}

const steps = ['Placed', 'Packed', 'Out for Delivery', 'Delivered']

const Orders: React.FC = () => (
  <div className="max-w-3xl mx-auto px-4 py-8">
    <h1 className="text-2xl font-black text-gray-900 dark:text-white mb-6">My Orders</h1>

    {mockOrders.length === 0 ? (
      <div className="text-center py-20">
        <Package size={48} className="text-gray-200 dark:text-gray-700 mx-auto mb-3" />
        <p className="text-gray-400 font-medium">No orders yet</p>
      </div>
    ) : (
      <div className="space-y-4">
        {mockOrders.map((order, idx) => {
          const sc = statusConfig[order.status]
          return (
            <motion.div
              key={order.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: idx * 0.1 }}
              className="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 overflow-hidden shadow-sm"
            >
              {/* Header */}
              <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100 dark:border-gray-700">
                <div>
                  <p className="text-sm font-bold text-gray-900 dark:text-white">Order #{order.id}</p>
                  <p className="text-xs text-gray-400 mt-0.5">{order.date} · ₹{order.total}</p>
                </div>
                <span className={`text-xs font-bold px-3 py-1 rounded-full ${sc.bg} ${sc.color}`}>
                  {sc.label}
                </span>
              </div>

              {/* Items */}
              <div className="px-5 py-3 flex gap-3 overflow-x-auto">
                {order.items.map(item => (
                  <div key={item.product.id} className="flex-shrink-0 flex items-center gap-2">
                    <img src={item.product.image} alt="" className="w-12 h-12 rounded-xl object-cover" />
                    <div>
                      <p className="text-xs font-medium text-gray-800 dark:text-gray-200 max-w-[100px] line-clamp-1">{item.product.name}</p>
                      <p className="text-xs text-gray-400">x{item.quantity} · ₹{item.product.price * item.quantity}</p>
                    </div>
                  </div>
                ))}
              </div>

              {/* Progress tracker — only for non-cancelled orders */}
              {order.status !== 'cancelled' && (
                <div className="px-5 pb-4">
                  <div className="flex items-center justify-between">
                    {steps.map((step, i) => {
                      const done = i <= sc.step
                      const active = i === sc.step
                      return (
                        <React.Fragment key={step}>
                          <div className="flex flex-col items-center gap-1">
                            <div className={`w-8 h-8 rounded-full flex items-center justify-center transition-colors ${done ? 'bg-brand-green text-white' : 'bg-gray-100 dark:bg-gray-700 text-gray-400'} ${active ? 'ring-2 ring-brand-green ring-offset-2 dark:ring-offset-gray-800' : ''}`}>
                              {i === 0 && <Clock size={14} />}
                              {i === 1 && <Package size={14} />}
                              {i === 2 && <Truck size={14} />}
                              {i === 3 && <CheckCircle size={14} />}
                            </div>
                            <span className="text-[9px] text-gray-400 font-medium text-center">{step}</span>
                          </div>
                          {i < 3 && (
                            <div className={`flex-1 h-0.5 mx-1 mb-4 transition-colors ${i < sc.step ? 'bg-brand-green' : 'bg-gray-200 dark:bg-gray-700'}`} />
                          )}
                        </React.Fragment>
                      )
                    })}
                  </div>
                </div>
              )}

              <div className="px-5 pb-3 text-xs text-gray-400">📍 {order.address}</div>
            </motion.div>
          )
        })}
      </div>
    )}
  </div>
)

export default Orders
