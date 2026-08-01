import React from 'react'
import { Outlet } from 'react-router-dom'
import { motion } from 'framer-motion'
import Navbar from '../components/Navbar'
import Footer from '../components/Footer'
import CartDrawer from '../components/CartDrawer'
import FloatingCartButton from '../components/FloatingCartButton'

const MainLayout: React.FC = () => (
  <div className="min-h-screen bg-gray-50 dark:bg-gray-950 font-sans transition-colors duration-300">
    <Navbar />
    <CartDrawer />
    <FloatingCartButton />
    <motion.main
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      <Outlet />
    </motion.main>
    <Footer />
  </div>
)

export default MainLayout
