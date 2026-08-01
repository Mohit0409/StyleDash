import React, { useState } from 'react'
import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import {
  BarChart2, ShoppingBag, Users, Package,
  TrendingUp, ArrowUpRight, ArrowDownRight, Eye,
  Edit2, Trash2, Plus, Search, IndianRupee, Megaphone,
  Store, Truck
} from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import { products, getCommissionPercent } from '../../data/products'
import { categories } from '../../data/categories'
import { vendors, adSlots, getAdRevenueTotal } from '../../data/vendors'

const stats = [
  { label: 'Total Revenue', value: '₹1,24,560', change: '+12.5%', up: true, icon: <TrendingUp size={20} />, color: 'text-brand-green', bg: 'bg-green-50 dark:bg-green-900/20' },
  { label: 'Orders Today', value: '84', change: '+8.2%', up: true, icon: <ShoppingBag size={20} />, color: 'text-blue-500', bg: 'bg-blue-50 dark:bg-blue-900/20' },
  { label: 'Total Products', value: String(products.length), change: '+5', up: true, icon: <Package size={20} />, color: 'text-purple-500', bg: 'bg-purple-50 dark:bg-purple-900/20' },
  { label: 'Active Users', value: '1,247', change: '-2.1%', up: false, icon: <Users size={20} />, color: 'text-orange-500', bg: 'bg-orange-50 dark:bg-orange-900/20' },
]

const recentOrders = [
  { id: 'NB0091', customer: 'Rahul Sharma', amount: '₹245', status: 'delivered', time: '10 min ago' },
  { id: 'NB0090', customer: 'Priya Verma', amount: '₹128', status: 'out_for_delivery', time: '22 min ago' },
  { id: 'NB0089', customer: 'Amit Patel', amount: '₹560', status: 'packed', time: '35 min ago' },
  { id: 'NB0088', customer: 'Sunita Joshi', amount: '₹89', status: 'placed', time: '51 min ago' },
  { id: 'NB0087', customer: 'Deepak Gupta', amount: '₹312', status: 'delivered', time: '1 hr ago' },
]

const statusBadge: Record<string, string> = {
  placed: 'bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400',
  packed: 'bg-orange-100 text-orange-600 dark:bg-orange-900/30 dark:text-orange-400',
  out_for_delivery: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
  delivered: 'bg-green-100 text-green-600 dark:bg-green-900/30 dark:text-green-400',
}

const statusLabel: Record<string, string> = {
  placed: 'Placed',
  packed: 'Packed',
  out_for_delivery: 'On the way',
  delivered: 'Delivered',
}

type Tab = 'overview' | 'earnings' | 'products' | 'categories' | 'orders' | 'users'

const AdminDashboard: React.FC = () => {
  const { user, isAdmin } = useAuth()
  const navigate = useNavigate()
  const [tab, setTab] = useState<Tab>('overview')
  const [search, setSearch] = useState('')

  if (!user || !isAdmin) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-4">
        <div className="text-5xl">🔒</div>
        <h2 className="text-xl font-bold text-gray-900 dark:text-white">Admin Access Required</h2>
        <p className="text-gray-400 text-sm">Sign in with admin@neemuchblink.in</p>
        <button onClick={() => navigate('/profile')} className="bg-brand-yellow text-brand-dark font-bold px-5 py-2.5 rounded-xl">
          Go to Login
        </button>
      </div>
    )
  }

  const filteredProducts = products.filter(p =>
    p.name.toLowerCase().includes(search.toLowerCase()) ||
    p.category.includes(search.toLowerCase())
  )

  // --- Revenue calculations ---
  // Mock "this month's" sales-by-product so commission math has something
  // real to multiply against. In production, replace `unitsSoldMock` with
  // an aggregation query over the `orders` Firestore collection.
  const unitsSoldMock = (productId: string) => {
    const seed = productId.split('').reduce((a, c) => a + c.charCodeAt(0), 0)
    return 8 + (seed % 40) // deterministic-but-varied mock between 8 and 47
  }

  const vendorCommissionRevenue = products.reduce((sum, p) => {
    const units = unitsSoldMock(p.id)
    const commission = (p.price * units * getCommissionPercent(p)) / 100
    return sum + commission
  }, 0)

  const adRevenueTotal = getAdRevenueTotal()
  const deliveryFeeRevenueMock = 18420 // sum of ₹30 fees on sub-₹300 orders this month
  const totalPlatformRevenue = vendorCommissionRevenue + adRevenueTotal + deliveryFeeRevenueMock

  const topEarningProducts = [...products]
    .map(p => ({ product: p, units: unitsSoldMock(p.id), commission: (p.price * unitsSoldMock(p.id) * getCommissionPercent(p)) / 100 }))
    .sort((a, b) => b.commission - a.commission)
    .slice(0, 8)

  const tabs: { key: Tab; label: string }[] = [
    { key: 'overview', label: 'Overview' },
    { key: 'earnings', label: 'Earnings' },
    { key: 'products', label: 'Products' },
    { key: 'categories', label: 'Categories' },
    { key: 'orders', label: 'Orders' },
    { key: 'users', label: 'Users' },
  ]

  return (
    <div className="max-w-7xl mx-auto px-4 py-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-black text-gray-900 dark:text-white">Admin Dashboard</h1>
          <p className="text-sm text-gray-400">Welcome back, {user.name}</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="bg-brand-green/10 text-brand-green text-xs font-bold px-3 py-1.5 rounded-full">● Live</span>
          <button className="bg-brand-yellow text-brand-dark font-bold text-sm px-4 py-2 rounded-xl flex items-center gap-1.5 hover:bg-yellow-400 transition-colors">
            <Plus size={14} /> Add Product
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-gray-100 dark:bg-gray-800 p-1 rounded-xl mb-6 overflow-x-auto">
        {tabs.map(t => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`flex-shrink-0 text-sm font-semibold px-4 py-2 rounded-lg transition-colors ${tab === t.key ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-white shadow-sm' : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'}`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Overview Tab */}
      {tab === 'overview' && (
        <div className="space-y-6">
          {/* Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {stats.map((s, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.07 }}
                className="bg-white dark:bg-gray-800 rounded-2xl p-4 border border-gray-100 dark:border-gray-700"
              >
                <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${s.bg} ${s.color} mb-3`}>
                  {s.icon}
                </div>
                <p className="text-xs text-gray-400 mb-1">{s.label}</p>
                <p className="text-xl font-black text-gray-900 dark:text-white">{s.value}</p>
                <div className={`flex items-center gap-1 mt-1 text-xs font-semibold ${s.up ? 'text-brand-green' : 'text-red-500'}`}>
                  {s.up ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />}
                  {s.change}
                </div>
              </motion.div>
            ))}
          </div>

          {/* Revenue Chart (placeholder) */}
          <div className="bg-white dark:bg-gray-800 rounded-2xl p-5 border border-gray-100 dark:border-gray-700">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-bold text-gray-900 dark:text-white">Revenue This Week</h3>
              <BarChart2 size={18} className="text-gray-400" />
            </div>
            <div className="flex items-end gap-2 h-32">
              {[40, 70, 55, 85, 60, 90, 75].map((h, i) => (
                <div key={i} className="flex-1 flex flex-col items-center gap-1">
                  <div
                    className="w-full rounded-t-lg bg-brand-yellow/80 hover:bg-brand-yellow transition-colors"
                    style={{ height: `${h}%` }}
                  />
                  <span className="text-[9px] text-gray-400">{['M', 'T', 'W', 'T', 'F', 'S', 'S'][i]}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Recent Orders */}
          <div className="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-100 dark:border-gray-700 flex items-center justify-between">
              <h3 className="font-bold text-gray-900 dark:text-white">Recent Orders</h3>
              <button onClick={() => setTab('orders')} className="text-xs text-brand-green font-semibold hover:underline">View all</button>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="bg-gray-50 dark:bg-gray-700/50">
                    {['Order ID', 'Customer', 'Amount', 'Status', 'Time', 'Action'].map(h => (
                      <th key={h} className="text-left text-xs font-semibold text-gray-500 dark:text-gray-400 px-5 py-2.5">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {recentOrders.map((order, i) => (
                    <tr key={i} className="border-t border-gray-50 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors">
                      <td className="px-5 py-3 text-sm font-bold text-gray-900 dark:text-white">#{order.id}</td>
                      <td className="px-5 py-3 text-sm text-gray-700 dark:text-gray-300">{order.customer}</td>
                      <td className="px-5 py-3 text-sm font-semibold text-gray-900 dark:text-white">{order.amount}</td>
                      <td className="px-5 py-3">
                        <span className={`text-xs font-bold px-2.5 py-1 rounded-full ${statusBadge[order.status]}`}>
                          {statusLabel[order.status]}
                        </span>
                      </td>
                      <td className="px-5 py-3 text-xs text-gray-400">{order.time}</td>
                      <td className="px-5 py-3">
                        <button className="text-gray-400 hover:text-brand-yellow transition-colors"><Eye size={14} /></button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Earnings Tab — how the platform actually makes money */}
      {tab === 'earnings' && (
        <div className="space-y-6">
          {/* Revenue breakdown cards */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="bg-white dark:bg-gray-800 rounded-2xl p-4 border border-gray-100 dark:border-gray-700">
              <div className="w-10 h-10 rounded-xl bg-purple-50 dark:bg-purple-900/20 text-purple-500 flex items-center justify-center mb-3">
                <Store size={20} />
              </div>
              <p className="text-xs text-gray-400 mb-1">Vendor Commission</p>
              <p className="text-2xl font-black text-gray-900 dark:text-white">₹{Math.round(vendorCommissionRevenue).toLocaleString('en-IN')}</p>
              <p className="text-xs text-gray-400 mt-1">From {vendors.length} active vendors this month</p>
            </motion.div>

            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.07 }} className="bg-white dark:bg-gray-800 rounded-2xl p-4 border border-gray-100 dark:border-gray-700">
              <div className="w-10 h-10 rounded-xl bg-pink-50 dark:bg-pink-900/20 text-pink-500 flex items-center justify-center mb-3">
                <Megaphone size={20} />
              </div>
              <p className="text-xs text-gray-400 mb-1">Ad & Sponsorship Revenue</p>
              <p className="text-2xl font-black text-gray-900 dark:text-white">₹{adRevenueTotal.toLocaleString('en-IN')}</p>
              <p className="text-xs text-gray-400 mt-1">{adSlots.filter(a => a.status === 'active').length} active paid placements</p>
            </motion.div>

            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.14 }} className="bg-white dark:bg-gray-800 rounded-2xl p-4 border border-gray-100 dark:border-gray-700">
              <div className="w-10 h-10 rounded-xl bg-blue-50 dark:bg-blue-900/20 text-blue-500 flex items-center justify-center mb-3">
                <Truck size={20} />
              </div>
              <p className="text-xs text-gray-400 mb-1">Delivery Fee Revenue</p>
              <p className="text-2xl font-black text-gray-900 dark:text-white">₹{deliveryFeeRevenueMock.toLocaleString('en-IN')}</p>
              <p className="text-xs text-gray-400 mt-1">₹30 fee on orders under ₹300</p>
            </motion.div>
          </div>

          {/* Total */}
          <div className="bg-brand-dark rounded-2xl p-6 text-white flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-400 mb-1">Total Platform Revenue (This Month)</p>
              <p className="text-3xl font-black flex items-center gap-1"><IndianRupee size={22} />{Math.round(totalPlatformRevenue).toLocaleString('en-IN')}</p>
            </div>
            <div className="flex items-center gap-1 text-brand-green text-sm font-bold">
              <ArrowUpRight size={16} /> +14.8% vs last month
            </div>
          </div>

          {/* Ad slots table */}
          <div className="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-100 dark:border-gray-700 flex items-center justify-between">
              <h3 className="font-bold text-gray-900 dark:text-white">Paid Placements (Ads)</h3>
              <button className="bg-brand-yellow text-brand-dark font-bold text-xs px-3 py-1.5 rounded-lg flex items-center gap-1 hover:bg-yellow-400 transition-colors">
                <Plus size={12} /> New Ad Slot
              </button>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="bg-gray-50 dark:bg-gray-700/50">
                    {['Vendor', 'Type', 'Price Paid', 'Impressions', 'Clicks', 'CTR', 'Status'].map(h => (
                      <th key={h} className="text-left text-xs font-semibold text-gray-500 dark:text-gray-400 px-4 py-3">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {adSlots.map(slot => {
                    const ctr = slot.impressions > 0 ? ((slot.clicks / slot.impressions) * 100).toFixed(1) : '—'
                    const statusColor = slot.status === 'active'
                      ? 'bg-green-100 text-green-600 dark:bg-green-900/30 dark:text-green-400'
                      : slot.status === 'scheduled'
                      ? 'bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400'
                      : 'bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400'
                    return (
                      <tr key={slot.id} className="border-t border-gray-50 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors">
                        <td className="px-4 py-3 text-sm font-medium text-gray-900 dark:text-white">{slot.vendorName}</td>
                        <td className="px-4 py-3 text-xs capitalize text-gray-500 dark:text-gray-400">{slot.type.replace('_', ' ')}</td>
                        <td className="px-4 py-3 text-sm font-bold text-gray-900 dark:text-white">₹{slot.price.toLocaleString('en-IN')}</td>
                        <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-300">{slot.impressions.toLocaleString('en-IN')}</td>
                        <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-300">{slot.clicks.toLocaleString('en-IN')}</td>
                        <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-300">{ctr}{ctr !== '—' && '%'}</td>
                        <td className="px-4 py-3">
                          <span className={`text-xs font-bold px-2.5 py-1 rounded-full capitalize ${statusColor}`}>{slot.status}</span>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Vendors table */}
          <div className="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-100 dark:border-gray-700 flex items-center justify-between">
              <h3 className="font-bold text-gray-900 dark:text-white">Vendor Commission Partners</h3>
              <button className="bg-brand-yellow text-brand-dark font-bold text-xs px-3 py-1.5 rounded-lg flex items-center gap-1 hover:bg-yellow-400 transition-colors">
                <Plus size={12} /> Onboard Vendor
              </button>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="bg-gray-50 dark:bg-gray-700/50">
                    {['Vendor', 'Location', 'Commission %', 'Total Sales', 'Commission Earned', 'Status'].map(h => (
                      <th key={h} className="text-left text-xs font-semibold text-gray-500 dark:text-gray-400 px-4 py-3">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {vendors.map(v => (
                    <tr key={v.id} className="border-t border-gray-50 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors">
                      <td className="px-4 py-3 text-sm font-medium text-gray-900 dark:text-white">{v.name}</td>
                      <td className="px-4 py-3 text-xs text-gray-500 dark:text-gray-400">{v.city}</td>
                      <td className="px-4 py-3 text-sm font-bold text-brand-green">{v.commissionPercent}%</td>
                      <td className="px-4 py-3 text-sm text-gray-700 dark:text-gray-300">₹{v.totalSales.toLocaleString('en-IN')}</td>
                      <td className="px-4 py-3 text-sm font-bold text-gray-900 dark:text-white">₹{v.totalCommissionEarned.toLocaleString('en-IN')}</td>
                      <td className="px-4 py-3">
                        <span className={`text-xs font-bold px-2.5 py-1 rounded-full ${v.active ? 'bg-green-100 text-green-600 dark:bg-green-900/30 dark:text-green-400' : 'bg-gray-100 text-gray-500'}`}>
                          {v.active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Top earning products by commission */}
          <div className="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-100 dark:border-gray-700">
              <h3 className="font-bold text-gray-900 dark:text-white">Top Commission-Earning Products</h3>
              <p className="text-xs text-gray-400 mt-0.5">Estimated units sold this month × commission rate</p>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="bg-gray-50 dark:bg-gray-700/50">
                    {['Product', 'Units Sold', 'Commission %', 'Commission Earned'].map(h => (
                      <th key={h} className="text-left text-xs font-semibold text-gray-500 dark:text-gray-400 px-4 py-3">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {topEarningProducts.map(({ product: p, units, commission }) => (
                    <tr key={p.id} className="border-t border-gray-50 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors">
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          <img src={p.image} alt="" className="w-9 h-9 rounded-lg object-cover flex-shrink-0" />
                          <span className="text-sm font-medium text-gray-900 dark:text-white line-clamp-1 max-w-[160px]">{p.name}</span>
                          {p.sponsored && <Megaphone size={11} className="text-brand-yellow flex-shrink-0" />}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-300">{units}</td>
                      <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-300">{getCommissionPercent(p)}%</td>
                      <td className="px-4 py-3 text-sm font-bold text-brand-green">₹{Math.round(commission).toLocaleString('en-IN')}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Products Tab */}
      {tab === 'products' && (
        <div>
          <div className="flex items-center gap-3 mb-4">
            <div className="relative flex-1 max-w-xs">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder="Search products..."
                className="w-full pl-8 pr-3 py-2 text-sm bg-gray-100 dark:bg-gray-800 rounded-xl focus:outline-none focus:ring-2 focus:ring-brand-yellow dark:text-white"
              />
            </div>
            <button className="bg-brand-yellow text-brand-dark font-bold text-sm px-4 py-2 rounded-xl flex items-center gap-1.5 hover:bg-yellow-400 transition-colors">
              <Plus size={14} /> Add Product
            </button>
          </div>
          <div className="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="bg-gray-50 dark:bg-gray-700/50">
                    {['Product', 'Category', 'Price', 'Stock', 'Rating', 'Actions'].map(h => (
                      <th key={h} className="text-left text-xs font-semibold text-gray-500 dark:text-gray-400 px-4 py-3">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filteredProducts.slice(0, 20).map((p, i) => (
                    <tr key={p.id} className="border-t border-gray-50 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors">
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          <img src={p.image} alt="" className="w-10 h-10 rounded-xl object-cover flex-shrink-0" />
                          <div>
                            <p className="text-sm font-medium text-gray-900 dark:text-white line-clamp-1 max-w-[140px]">{p.name}</p>
                            <p className="text-xs text-gray-400">{p.weight}{p.unit}</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-sm capitalize text-gray-600 dark:text-gray-300">{p.category}</td>
                      <td className="px-4 py-3">
                        <p className="text-sm font-bold text-gray-900 dark:text-white">₹{p.price}</p>
                        {p.originalPrice > p.price && (
                          <p className="text-xs text-gray-400 line-through">₹{p.originalPrice}</p>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${p.inStock ? 'bg-green-100 text-green-600 dark:bg-green-900/30 dark:text-green-400' : 'bg-red-100 text-red-500'}`}>
                          {p.inStock ? 'In Stock' : 'Out'}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-300">⭐ {p.rating}</td>
                      <td className="px-4 py-3">
                        <div className="flex gap-2">
                          <button className="text-gray-400 hover:text-brand-yellow transition-colors"><Edit2 size={14} /></button>
                          <button className="text-gray-400 hover:text-red-500 transition-colors"><Trash2 size={14} /></button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Categories Tab */}
      {tab === 'categories' && (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
          {categories.map((c, i) => (
            <motion.div
              key={c.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
              className="bg-white dark:bg-gray-800 rounded-2xl p-4 border border-gray-100 dark:border-gray-700 flex items-center gap-4"
            >
              <img src={c.image} alt="" className="w-14 h-14 rounded-xl object-cover flex-shrink-0" />
              <div className="flex-1">
                <p className="font-bold text-gray-900 dark:text-white">{c.name}</p>
                <p className="text-xs text-gray-400">{c.productCount}+ products</p>
              </div>
              <div className="flex gap-2">
                <button className="text-gray-400 hover:text-brand-yellow transition-colors"><Edit2 size={14} /></button>
                <button className="text-gray-400 hover:text-red-500 transition-colors"><Trash2 size={14} /></button>
              </div>
            </motion.div>
          ))}
          <motion.button
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="border-2 border-dashed border-gray-200 dark:border-gray-700 rounded-2xl p-4 flex flex-col items-center justify-center gap-2 text-gray-400 hover:border-brand-yellow hover:text-brand-yellow transition-colors min-h-[80px]"
          >
            <Plus size={20} />
            <span className="text-sm font-medium">Add Category</span>
          </motion.button>
        </div>
      )}

      {/* Orders Tab */}
      {tab === 'orders' && (
        <div className="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="bg-gray-50 dark:bg-gray-700/50">
                  {['Order ID', 'Customer', 'Amount', 'Status', 'Time', 'Action'].map(h => (
                    <th key={h} className="text-left text-xs font-semibold text-gray-500 dark:text-gray-400 px-5 py-3">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {[...recentOrders, ...recentOrders].map((order, i) => (
                  <tr key={i} className="border-t border-gray-50 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors">
                    <td className="px-5 py-3 text-sm font-bold text-gray-900 dark:text-white">#{order.id}-{i}</td>
                    <td className="px-5 py-3 text-sm text-gray-700 dark:text-gray-300">{order.customer}</td>
                    <td className="px-5 py-3 text-sm font-semibold">{order.amount}</td>
                    <td className="px-5 py-3">
                      <span className={`text-xs font-bold px-2.5 py-1 rounded-full ${statusBadge[order.status]}`}>
                        {statusLabel[order.status]}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-xs text-gray-400">{order.time}</td>
                    <td className="px-5 py-3 flex gap-2">
                      <button className="text-gray-400 hover:text-brand-yellow transition-colors"><Eye size={14} /></button>
                      <button className="text-gray-400 hover:text-red-500 transition-colors"><Trash2 size={14} /></button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Users Tab */}
      {tab === 'users' && (
        <div className="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="bg-gray-50 dark:bg-gray-700/50">
                  {['User', 'Email', 'Orders', 'Spent', 'Joined', 'Action'].map(h => (
                    <th key={h} className="text-left text-xs font-semibold text-gray-500 dark:text-gray-400 px-5 py-3">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {['Rahul Sharma', 'Priya Verma', 'Amit Patel', 'Sunita Joshi', 'Deepak Gupta'].map((name, i) => (
                  <tr key={i} className="border-t border-gray-50 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors">
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-2">
                        <div className="w-8 h-8 rounded-full bg-brand-yellow flex items-center justify-center text-brand-dark font-bold text-sm">
                          {name[0]}
                        </div>
                        <span className="text-sm font-medium text-gray-900 dark:text-white">{name}</span>
                      </div>
                    </td>
                    <td className="px-5 py-3 text-sm text-gray-500">{name.toLowerCase().replace(' ', '.')}@gmail.com</td>
                    <td className="px-5 py-3 text-sm font-medium text-gray-700 dark:text-gray-300">{5 + i * 3}</td>
                    <td className="px-5 py-3 text-sm font-semibold text-gray-900 dark:text-white">₹{(i + 1) * 348}</td>
                    <td className="px-5 py-3 text-xs text-gray-400">Jun 2025</td>
                    <td className="px-5 py-3">
                      <button className="text-gray-400 hover:text-brand-yellow transition-colors"><Eye size={14} /></button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

export default AdminDashboard
