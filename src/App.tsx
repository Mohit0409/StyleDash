import React, { Suspense } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { ThemeProvider } from './context/ThemeContext'
import { CartProvider } from './context/CartContext'
import { WishlistProvider } from './context/WishlistContext'
import { AuthProvider } from './context/AuthContext'
import { ToastProvider } from './context/ToastContext'
import { ReferralProvider } from './context/ReferralContext'
import MainLayout from './layouts/MainLayout'
import Home from './pages/Home'
import Categories from './pages/Categories'
import Products from './pages/Products'
import Checkout from './pages/Checkout'
import OrderSuccess from './pages/OrderSuccess'
import Orders from './pages/Orders'
import Profile from './pages/Profile'
import Wishlist from './pages/Wishlist'
import Referrals from './pages/Referrals'
import AdminDashboard from './pages/admin/AdminDashboard'

const Loader: React.FC = () => (
  <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-950">
    <div className="flex flex-col items-center gap-3">
      <div className="w-10 h-10 bg-brand-yellow rounded-xl flex items-center justify-center font-black text-brand-dark animate-bounce">NB</div>
      <p className="text-sm text-gray-400 font-medium">Loading...</p>
    </div>
  </div>
)

const App: React.FC = () => (
  <BrowserRouter>
    <ThemeProvider>
      <AuthProvider>
        <CartProvider>
          <WishlistProvider>
            <ToastProvider>
              <ReferralProvider>
              <Suspense fallback={<Loader />}>
                <Routes>
                  <Route element={<MainLayout />}>
                    <Route index element={<Home />} />
                    <Route path="categories" element={<Categories />} />
                    <Route path="products" element={<Products />} />
                    <Route path="checkout" element={<Checkout />} />
                    <Route path="order-success" element={<OrderSuccess />} />
                    <Route path="orders" element={<Orders />} />
                    <Route path="profile" element={<Profile />} />
                    <Route path="wishlist" element={<Wishlist />} />
                    <Route path="referrals" element={<Referrals />} />
                    <Route path="admin" element={<AdminDashboard />} />
                  </Route>
                </Routes>
              </Suspense>
              </ReferralProvider>
            </ToastProvider>
          </WishlistProvider>
        </CartProvider>
      </AuthProvider>
    </ThemeProvider>
  </BrowserRouter>
)

export default App
