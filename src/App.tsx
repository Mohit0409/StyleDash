import React, { Suspense, lazy } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from './context/ThemeContext';
import { AuthProvider } from './context/AuthContext';
import { CartProvider } from './context/CartContext';
import { WishlistProvider } from './context/WishlistContext';
import { ToastProvider } from './context/ToastContext';
import { MainLayout } from './layouts/MainLayout';
import { ProtectedRoute } from './components/ProtectedRoute';

const Home = lazy(() => import('./pages/Home').then(m => ({ default: m.Home })));
const Products = lazy(() => import('./pages/Products').then(m => ({ default: m.Products })));
const ProductDetail = lazy(() => import('./pages/ProductDetail').then(m => ({ default: m.ProductDetail })));
const Categories = lazy(() => import('./pages/Categories').then(m => ({ default: m.Categories })));
const Stores = lazy(() => import('./pages/Stores').then(m => ({ default: m.Stores })));
const StoreDetail = lazy(() => import('./pages/StoreDetail').then(m => ({ default: m.StoreDetail })));
const VendorOnboarding = lazy(() => import('./pages/VendorOnboarding').then(m => ({ default: m.VendorOnboarding })));
const Wishlist = lazy(() => import('./pages/Wishlist').then(m => ({ default: m.Wishlist })));
const Checkout = lazy(() => import('./pages/Checkout').then(m => ({ default: m.Checkout })));
const OrderSuccess = lazy(() => import('./pages/OrderSuccess').then(m => ({ default: m.OrderSuccess })));
const OrderTracking = lazy(() => import('./pages/OrderTracking').then(m => ({ default: m.OrderTracking })));
const Orders = lazy(() => import('./pages/Orders').then(m => ({ default: m.Orders })));
const Profile = lazy(() => import('./pages/Profile').then(m => ({ default: m.Profile })));
const NotFound = lazy(() => import('./pages/NotFound').then(m => ({ default: m.NotFound })));
const Help = lazy(() => import('./pages/Help').then(m => ({ default: m.Help })));
const Returns = lazy(() => import('./pages/Returns').then(m => ({ default: m.Returns })));
const Privacy = lazy(() => import('./pages/Privacy').then(m => ({ default: m.Privacy })));
const Terms = lazy(() => import('./pages/Terms').then(m => ({ default: m.Terms })));
const AuthPage = lazy(() => import('./pages/AuthPage').then(m => ({ default: m.AuthPage })));
const ForgotPassword = lazy(() => import('./pages/PasswordRecovery').then(m => ({ default: m.ForgotPassword })));
const ResetPassword = lazy(() => import('./pages/PasswordRecovery').then(m => ({ default: m.ResetPassword })));
const PaymentTestProduct = lazy(() => import('./pages/PaymentTestProduct').then(m => ({ default: m.PaymentTestProduct })));

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <ThemeProvider>
        <AuthProvider>
          <CartProvider>
            <WishlistProvider>
              <ToastProvider>
                <Suspense fallback={
                  <div className="h-screen w-full flex items-center justify-center text-sm font-bold text-neutral-500">
                    Loading Vibe4You...
                  </div>
                }>
                  <Routes>
                    <Route element={<MainLayout />}>
                      <Route index element={<Home />} />
                      <Route path="products" element={<Products />} />
                      <Route path="product/:slug" element={<ProductDetail />} />
                      <Route path="categories" element={<Categories />} />
                      <Route path="stores" element={<Stores />} />
                      <Route path="store/:slug" element={<StoreDetail />} />
                      <Route path="partner" element={<ProtectedRoute><VendorOnboarding /></ProtectedRoute>} />
                      <Route path="wishlist" element={<Wishlist />} />
                      <Route path="login" element={<AuthPage mode="login" />} />
                      <Route path="register" element={<AuthPage mode="register" />} />
                      <Route path="forgot-password" element={<ForgotPassword />} />
                      <Route path="reset-password" element={<ResetPassword />} />
                      <Route path="payment-test/styledash-payment-test-item" element={<PaymentTestProduct />} />
                      <Route path="checkout" element={<ProtectedRoute><Checkout /></ProtectedRoute>} />
                      <Route path="order-success/:orderId" element={<ProtectedRoute><OrderSuccess /></ProtectedRoute>} />
                      <Route path="orders/:orderId/track" element={<ProtectedRoute><OrderTracking /></ProtectedRoute>} />
                      <Route path="orders" element={<ProtectedRoute><Orders /></ProtectedRoute>} />
                      <Route path="profile" element={<ProtectedRoute><Profile /></ProtectedRoute>} />
                      <Route path="help" element={<Help />} />
                      <Route path="returns" element={<Returns />} />
                      <Route path="privacy" element={<Privacy />} />
                      <Route path="terms" element={<Terms />} />
                      <Route path="*" element={<NotFound />} />
                    </Route>
                  </Routes>
                </Suspense>
              </ToastProvider>
            </WishlistProvider>
          </CartProvider>
        </AuthProvider>
      </ThemeProvider>
    </BrowserRouter>
  );
};

export default App;
