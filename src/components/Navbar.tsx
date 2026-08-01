import React, { useState, useEffect } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ShoppingCart, Sun, Moon, Search, MapPin, User, Menu, X, Heart } from 'lucide-react'
import { useTheme } from '../context/ThemeContext'
import { useCart } from '../context/CartContext'
import { useAuth } from '../context/AuthContext'
import { trackSearch } from '../firebase/analytics'

const Navbar: React.FC = () => {
  const { isDark, toggle } = useTheme()
  const { itemCount, setIsOpen } = useCart()
  const { user } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [scrolled, setScrolled] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const [searchVal, setSearchVal] = useState('')

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20)
    window.addEventListener('scroll', onScroll)
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  useEffect(() => { setMobileOpen(false) }, [location])

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (searchVal.trim()) {
      trackSearch(searchVal.trim())
      navigate(`/products?search=${encodeURIComponent(searchVal)}`)
    }
  }

  return (
    <header className={`sticky top-0 z-50 transition-all duration-300 ${scrolled ? 'bg-white/90 dark:bg-gray-900/90 backdrop-blur-md shadow-md' : 'bg-white dark:bg-gray-900'}`}>
      <div className="max-w-7xl mx-auto px-4 h-16 flex items-center gap-3">
        {/* Logo */}
        <Link to="/" className="flex items-center gap-2 flex-shrink-0">
          <div className="w-8 h-8 bg-brand-yellow rounded-xl flex items-center justify-center font-black text-brand-dark text-sm">NB</div>
          <span className="font-extrabold text-lg text-gray-900 dark:text-white hidden sm:block">Neemuch<span className="text-brand-yellow">Blink</span></span>
        </Link>

        {/* Location */}
        <button className="flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400 hover:text-brand-green transition-colors flex-shrink-0 hidden md:flex">
          <MapPin size={13} className="text-brand-green" />
          <span className="font-medium">Neemuch, MP</span>
        </button>

        {/* Search */}
        <form onSubmit={handleSearch} className="flex-1 max-w-xl">
          <div className="relative">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              value={searchVal}
              onChange={e => setSearchVal(e.target.value)}
              placeholder="Search groceries, vegetables..."
              className="w-full pl-9 pr-4 py-2 text-sm bg-gray-100 dark:bg-gray-800 rounded-xl border border-transparent focus:border-brand-yellow focus:outline-none transition-colors dark:text-white"
            />
          </div>
        </form>

        {/* Actions */}
        <div className="flex items-center gap-2 flex-shrink-0">
          <button onClick={toggle} className="w-9 h-9 flex items-center justify-center rounded-xl hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors">
            {isDark ? <Sun size={17} className="text-brand-yellow" /> : <Moon size={17} className="text-gray-600" />}
          </button>

          <Link to="/profile" className="w-9 h-9 hidden sm:flex items-center justify-center rounded-xl hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors">
            {user?.photoURL
              ? <img src={user.photoURL} alt="" className="w-7 h-7 rounded-full" />
              : <User size={17} className="text-gray-600 dark:text-gray-300" />
            }
          </Link>

          <Link to="/wishlist" className="w-9 h-9 hidden sm:flex items-center justify-center rounded-xl hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors">
            <Heart size={17} className="text-gray-600 dark:text-gray-300" />
          </Link>

          <motion.button
            whileTap={{ scale: 0.93 }}
            onClick={() => setIsOpen(true)}
            className="relative flex items-center gap-2 bg-brand-yellow hover:bg-yellow-400 text-brand-dark font-bold text-sm px-3 py-2 rounded-xl transition-colors"
          >
            <ShoppingCart size={16} />
            <span className="hidden sm:block">Cart</span>
            {itemCount > 0 && (
              <span className="absolute -top-1.5 -right-1.5 w-5 h-5 bg-brand-green text-white text-[10px] font-black rounded-full flex items-center justify-center">
                {itemCount}
              </span>
            )}
          </motion.button>

          <button className="sm:hidden w-9 h-9 flex items-center justify-center" onClick={() => setMobileOpen(p => !p)}>
            {mobileOpen ? <X size={20} className="text-gray-700 dark:text-gray-200" /> : <Menu size={20} className="text-gray-700 dark:text-gray-200" />}
          </button>
        </div>
      </div>

      {/* Mobile Nav */}
      {mobileOpen && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="sm:hidden bg-white dark:bg-gray-900 border-t border-gray-100 dark:border-gray-800 px-4 py-3 flex flex-col gap-3"
        >
          <Link to="/categories" className="text-sm font-medium text-gray-700 dark:text-gray-200 py-1">Categories</Link>
          <Link to="/products" className="text-sm font-medium text-gray-700 dark:text-gray-200 py-1">All Products</Link>
          <Link to="/orders" className="text-sm font-medium text-gray-700 dark:text-gray-200 py-1">My Orders</Link>
          <Link to="/wishlist" className="text-sm font-medium text-gray-700 dark:text-gray-200 py-1">Wishlist</Link>
          <Link to="/referrals" className="text-sm font-medium text-gray-700 dark:text-gray-200 py-1">Refer & Earn</Link>
          <Link to="/profile" className="text-sm font-medium text-gray-700 dark:text-gray-200 py-1">Profile</Link>
        </motion.div>
      )}
    </header>
  )
}

export default Navbar
