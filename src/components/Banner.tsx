import React, { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { banners } from '../data/banners'

const Banner: React.FC = () => {
  const [current, setCurrent] = useState(0)

  useEffect(() => {
    const timer = setInterval(() => setCurrent(p => (p + 1) % banners.length), 4000)
    return () => clearInterval(timer)
  }, [])

  const prev = () => setCurrent(p => (p - 1 + banners.length) % banners.length)
  const next = () => setCurrent(p => (p + 1) % banners.length)

  return (
    <div className="relative rounded-2xl overflow-hidden h-40 md:h-56 shadow-md">
      <AnimatePresence mode="wait">
        <motion.div
          key={current}
          initial={{ opacity: 0, x: 60 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -60 }}
          transition={{ duration: 0.4 }}
          className="absolute inset-0"
        >
          <img
            src={banners[current].image}
            alt={banners[current].title}
            className="w-full h-full object-cover"
          />
          <div className="absolute inset-0 bg-gradient-to-r from-black/60 to-transparent" />
          <div className="absolute bottom-4 left-5">
            <p className="text-white font-bold text-lg md:text-2xl drop-shadow">{banners[current].title}</p>
            <p className="text-white/80 text-xs md:text-sm mt-0.5">{banners[current].subtitle}</p>
          </div>
        </motion.div>
      </AnimatePresence>

      <button onClick={prev} className="absolute left-2 top-1/2 -translate-y-1/2 w-8 h-8 bg-white/20 backdrop-blur-sm rounded-full flex items-center justify-center text-white hover:bg-white/40 transition-colors">
        <ChevronLeft size={16} />
      </button>
      <button onClick={next} className="absolute right-2 top-1/2 -translate-y-1/2 w-8 h-8 bg-white/20 backdrop-blur-sm rounded-full flex items-center justify-center text-white hover:bg-white/40 transition-colors">
        <ChevronRight size={16} />
      </button>

      <div className="absolute bottom-2 right-4 flex gap-1">
        {banners.map((_, i) => (
          <button
            key={i}
            onClick={() => setCurrent(i)}
            className={`h-1.5 rounded-full transition-all duration-300 ${i === current ? 'w-6 bg-brand-yellow' : 'w-1.5 bg-white/50'}`}
          />
        ))}
      </div>
    </div>
  )
}

export default Banner
