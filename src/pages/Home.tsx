import React from 'react'
import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import { Zap, Clock, ShieldCheck, ChevronRight, Star } from 'lucide-react'
import Banner from '../components/Banner'
import CategoryCard from '../components/CategoryCard'
import ProductCard from '../components/ProductCard'
import { categories } from '../data/categories'
import { products, getFeaturedProducts } from '../data/products'

const fadeUp = {
  initial: { opacity: 0, y: 30 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true },
  transition: { duration: 0.5 }
}

const Home: React.FC = () => {
  const navigate = useNavigate()
  const featured = getFeaturedProducts()
  const trending = products.slice(0, 10)
  const veggies = products.filter(p => p.category === 'vegetables').slice(0, 6)

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 space-y-10">

      {/* Hero */}
      <motion.section
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="relative rounded-3xl overflow-hidden bg-gradient-to-br from-brand-yellow via-yellow-300 to-brand-green p-8 md:p-12"
      >
        <div className="relative z-10 max-w-lg">
          <motion.div
            initial={{ opacity: 0, x: -30 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.1 }}
            className="inline-flex items-center gap-2 bg-white/30 backdrop-blur-sm text-brand-dark text-xs font-bold px-3 py-1.5 rounded-full mb-4"
          >
            <Zap size={12} className="fill-brand-dark" /> 10–20 Min Delivery
          </motion.div>
          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="text-3xl md:text-5xl font-black text-brand-dark leading-tight"
          >
            Neemuch's Fastest<br />
            <span className="text-white drop-shadow">Grocery Delivery</span>
          </motion.h1>
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="mt-3 text-brand-dark/80 text-sm md:text-base leading-relaxed"
          >
            Fresh groceries, vegetables, fruits, dairy, snacks and daily essentials delivered in minutes.
          </motion.p>
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
            className="flex gap-3 mt-6"
          >
            <button
              onClick={() => navigate('/products')}
              className="bg-brand-dark text-white font-bold px-5 py-3 rounded-xl hover:bg-gray-800 transition-colors shadow-lg"
            >
              Order Now
            </button>
            <button
              onClick={() => navigate('/categories')}
              className="bg-white/40 backdrop-blur-sm text-brand-dark font-bold px-5 py-3 rounded-xl hover:bg-white/60 transition-colors"
            >
              Browse Categories
            </button>
          </motion.div>
        </div>

        {/* Decorative scooter */}
        <div className="absolute right-6 bottom-0 text-8xl md:text-9xl opacity-30 select-none pointer-events-none">🛵</div>
        <div className="absolute top-4 right-24 text-4xl opacity-20 animate-bounce select-none pointer-events-none">🥦</div>
        <div className="absolute top-12 right-10 text-3xl opacity-20 animate-spin-slow select-none pointer-events-none">🍎</div>
      </motion.section>

      {/* Trust badges */}
      <div className="grid grid-cols-3 gap-3">
        {[
          { icon: <Zap size={20} className="text-brand-yellow" />, label: '10–20 Min', sub: 'Delivery' },
          { icon: <ShieldCheck size={20} className="text-brand-green" />, label: '100% Fresh', sub: 'Guarantee' },
          { icon: <Clock size={20} className="text-blue-500" />, label: '7 AM – 10 PM', sub: 'Open Daily' },
        ].map((b, i) => (
          <motion.div
            key={i}
            {...fadeUp}
            transition={{ delay: i * 0.1 }}
            className="flex flex-col items-center text-center bg-white dark:bg-gray-800 rounded-2xl p-4 shadow-sm border border-gray-100 dark:border-gray-700"
          >
            {b.icon}
            <p className="font-bold text-sm text-gray-900 dark:text-white mt-1.5">{b.label}</p>
            <p className="text-xs text-gray-400">{b.sub}</p>
          </motion.div>
        ))}
      </div>

      {/* Banner */}
      <motion.section {...fadeUp}>
        <Banner />
      </motion.section>

      {/* Categories */}
      <motion.section {...fadeUp}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-black text-gray-900 dark:text-white">Shop by Category</h2>
          <button onClick={() => navigate('/categories')} className="flex items-center gap-1 text-sm font-semibold text-brand-green hover:underline">
            See all <ChevronRight size={14} />
          </button>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3">
          {categories.slice(0, 10).map((cat, i) => (
            <CategoryCard key={cat.id} category={cat} index={i} />
          ))}
        </div>
      </motion.section>

      {/* Flash Sale */}
      <motion.section {...fadeUp} className="bg-gradient-to-r from-red-500 to-orange-400 rounded-3xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <span className="text-2xl">🔥</span>
          <h2 className="text-xl font-black text-white">Flash Sale</h2>
          <span className="bg-white/20 text-white text-xs font-bold px-2 py-0.5 rounded-full ml-auto">Limited Time</span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
          {products.filter(p => p.discount >= 20).slice(0, 4).map(p => (
            <ProductCard key={p.id} product={p} />
          ))}
        </div>
      </motion.section>

      {/* Best Sellers */}
      <motion.section {...fadeUp}>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Star size={18} className="fill-amber-400 text-amber-400" />
            <h2 className="text-xl font-black text-gray-900 dark:text-white">Best Sellers</h2>
          </div>
          <button onClick={() => navigate('/products')} className="flex items-center gap-1 text-sm font-semibold text-brand-green hover:underline">
            View all <ChevronRight size={14} />
          </button>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
          {featured.slice(0, 10).map(p => <ProductCard key={p.id} product={p} />)}
        </div>
      </motion.section>

      {/* Fresh Vegetables */}
      <motion.section {...fadeUp}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-black text-gray-900 dark:text-white">🥦 Fresh Vegetables</h2>
          <button onClick={() => navigate('/products?category=vegetables')} className="flex items-center gap-1 text-sm font-semibold text-brand-green hover:underline">
            See all <ChevronRight size={14} />
          </button>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
          {veggies.map(p => <ProductCard key={p.id} product={p} />)}
        </div>
      </motion.section>

      {/* Trending */}
      <motion.section {...fadeUp}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-black text-gray-900 dark:text-white">🔥 Trending Now</h2>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
          {trending.map(p => <ProductCard key={p.id} product={p} />)}
        </div>
      </motion.section>

      {/* App CTA */}
      <motion.section
        {...fadeUp}
        className="bg-brand-dark rounded-3xl p-8 text-center text-white"
      >
        <p className="text-3xl mb-2">📱</p>
        <h2 className="text-2xl font-black mb-2">Get the App</h2>
        <p className="text-gray-400 text-sm mb-5">Order faster, track live, get exclusive app deals.</p>
        <div className="flex gap-3 justify-center flex-wrap">
          <button className="flex items-center gap-2 bg-white text-brand-dark font-bold px-4 py-2.5 rounded-xl text-sm hover:bg-gray-100 transition-colors">
            🍎 App Store
          </button>
          <button className="flex items-center gap-2 bg-brand-yellow text-brand-dark font-bold px-4 py-2.5 rounded-xl text-sm hover:bg-yellow-400 transition-colors">
            ▶ Play Store
          </button>
        </div>
      </motion.section>

    </div>
  )
}

export default Home
