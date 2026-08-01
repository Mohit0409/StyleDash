import React, { Suspense, lazy } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from './context/ThemeContext';
import { AuthProvider } from './context/AuthContext';
import { CartProvider } from './context/CartContext';
import { WishlistProvider } from './context/WishlistContext';
import { ToastProvider } from './context/ToastContext';
import { ReferralProvider } from './context/ReferralContext';
import { MainLayout } from './layouts/MainLayout';

const Home = lazy(() => import('./pages/Home').then(m => ({ default: m.Home })));
const Products = lazy(() => import('./pages/Products').then(m => ({ default: m.Products })));
const ProductDetail = lazy(() => import('./pages/ProductDetail').then(m => ({ default: m.ProductDetail })));
const Categories = lazy(() => import('./pages/Categories').then(m => ({ default: m.Categories })));
const Wishlist = lazy(() => import('./pages/Wishlist').then(m => ({ default: m.Wishlist })));
const Checkout = lazy(() => import('./pages/Checkout').then(m => ({ default: m.Checkout })));
const OrderSuccess = lazy(() => import('./pages/OrderSuccess').then(m => ({ default: m.OrderSuccess })));
const Orders = lazy(() => import('./pages/Orders').then(m => ({ default: m.Orders })));
const Profile = lazy(() => import('./pages/Profile').then(m => ({ default: m.Profile })));
const Referrals = lazy(() => import('./pages/Referrals').then(m => ({ default: m.Referrals })));
const AdminDashboard = lazy(() => import('./pages/AdminDashboard').then(m => ({ default: m.AdminDashboard })));
const NotFound = lazy(() => import('./pages/NotFound').then(m => ({ default: m.NotFound })));
const Help = lazy(() => import('./pages/Help').then(m => ({ default: m.Help })));
const Returns = lazy(() => import('./pages/Returns').then(m => ({ default: m.Returns })));
const Privacy = lazy(() => import('./pages/Privacy').then(m => ({ default: m.Privacy })));
const Terms = lazy(() => import('./pages/Terms').then(m => ({ default: m.Terms })));

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <ThemeProvider>
        <AuthProvider>
          <CartProvider>
            <WishlistProvider>
              <ToastProvider>
                <ReferralProvider>
                  <Suspense fallback={
                    <div className="h-screen w-full flex items-center justify-center text-sm font-bold text-neutral-500">
                      Loading StyleDash...
                    </div>
                  }>
                    <Routes>
                      <Route element={<MainLayout />}>
                        <Route index element={<Home />} />
                        <Route path="products" element={<Products />} />
                        <Route path="product/:slug" element={<ProductDetail />} />
                        <Route path="categories" element={<Categories />} />
                        <Route path="wishlist" element={<Wishlist />} />
                        <Route path="checkout" element={<Checkout />} />
                        <Route path="order-success/:orderId" element={<OrderSuccess />} />
                        <Route path="orders" element={<Orders />} />
                        <Route path="profile" element={<Profile />} />
                        <Route path="referrals" element={<Referrals />} />
                        <Route path="admin" element={<AdminDashboard />} />
                        <Route path="help" element={<Help />} />
                        <Route path="returns" element={<Returns />} />
                        <Route path="privacy" element={<Privacy />} />
                        <Route path="terms" element={<Terms />} />
                        <Route path="*" element={<NotFound />} />
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
  );
};

export default App;
