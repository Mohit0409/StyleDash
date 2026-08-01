import React, { useState } from 'react'
import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import { User, MapPin, ShoppingBag, Heart, LogOut, ChevronRight, Shield, Gift } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'

const Profile: React.FC = () => {
  const { user, login, logout, loading, isAdmin } = useAuth()
  const { showToast } = useToast()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    await login(email, password)
    showToast('Logged in successfully!', 'success')
  }

  const handleLogout = () => {
    logout()
    showToast('Logged out', 'info')
  }

  if (!user) {
    return (
      <div className="max-w-sm mx-auto px-4 py-16">
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-brand-yellow/20 rounded-2xl flex items-center justify-center mx-auto mb-3">
            <User size={28} className="text-brand-yellow" />
          </div>
          <h1 className="text-2xl font-black text-gray-900 dark:text-white">Welcome Back</h1>
          <p className="text-sm text-gray-400 mt-1">Sign in to track orders and manage your account</p>
        </div>
        <form onSubmit={handleLogin} className="space-y-3">
          <input
            type="email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            placeholder="Email address"
            required
            className="w-full bg-gray-100 dark:bg-gray-800 text-sm rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-brand-yellow dark:text-white"
          />
          <input
            type="password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            placeholder="Password"
            required
            className="w-full bg-gray-100 dark:bg-gray-800 text-sm rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-brand-yellow dark:text-white"
          />
          <motion.button
            whileTap={{ scale: 0.97 }}
            type="submit"
            disabled={loading}
            className="w-full bg-brand-yellow text-brand-dark font-bold py-3.5 rounded-xl hover:bg-yellow-400 transition-colors disabled:opacity-70"
          >
            {loading ? 'Signing in...' : 'Sign In'}
          </motion.button>
        </form>
        <p className="text-xs text-center text-gray-400 mt-4">
          Use <strong>admin@neemuchblink.in</strong> for admin access
        </p>
      </div>
    )
  }

  const menuItems = [
    { icon: <ShoppingBag size={16} />, label: 'My Orders', action: () => navigate('/orders') },
    { icon: <Heart size={16} />, label: 'Wishlist', action: () => navigate('/wishlist') },
    { icon: <Gift size={16} />, label: 'Refer & Earn', action: () => navigate('/referrals') },
    { icon: <MapPin size={16} />, label: 'Saved Addresses', action: () => {} },
    { icon: <Shield size={16} />, label: 'Admin Dashboard', action: () => navigate('/admin'), adminOnly: true },
  ]

  return (
    <div className="max-w-lg mx-auto px-4 py-8">
      {/* Profile card */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-gradient-to-br from-brand-yellow to-brand-green rounded-3xl p-6 text-white mb-6"
      >
        <div className="flex items-center gap-4">
          <div className="w-16 h-16 rounded-2xl overflow-hidden bg-white/20">
            {user.photoURL
              ? <img src={user.photoURL} alt="" className="w-full h-full object-cover" />
              : <div className="w-full h-full flex items-center justify-center text-2xl font-black text-white">{user.name[0]}</div>
            }
          </div>
          <div>
            <h2 className="font-black text-lg">{user.name}</h2>
            <p className="text-white/80 text-sm">{user.email}</p>
            {user.phone && <p className="text-white/70 text-xs">{user.phone}</p>}
          </div>
        </div>
      </motion.div>

      {/* Menu */}
      <div className="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 overflow-hidden">
        {menuItems.filter(m => !m.adminOnly || (m.adminOnly && isAdmin)).map((item, i) => (
          <button
            key={i}
            onClick={item.action}
            className="w-full flex items-center gap-3 px-5 py-4 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors border-b border-gray-100 dark:border-gray-700 last:border-0"
          >
            <span className="text-gray-500 dark:text-gray-400">{item.icon}</span>
            <span className="text-sm font-medium text-gray-800 dark:text-gray-200 flex-1 text-left">{item.label}</span>
            <ChevronRight size={14} className="text-gray-300 dark:text-gray-600" />
          </button>
        ))}
      </div>

      <button
        onClick={handleLogout}
        className="w-full mt-4 flex items-center justify-center gap-2 text-sm font-bold text-red-500 bg-red-50 dark:bg-red-900/20 py-3.5 rounded-2xl hover:bg-red-100 dark:hover:bg-red-900/30 transition-colors"
      >
        <LogOut size={15} /> Sign Out
      </button>
    </div>
  )
}

export default Profile
