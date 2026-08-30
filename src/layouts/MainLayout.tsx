import React, { lazy, Suspense, useState } from 'react';
import { Outlet } from 'react-router-dom';
import { Header } from '../components/Header';
import { Footer } from '../components/Footer';
import { NavigationScrollPolicy } from '../components/NavigationScrollPolicy';

const CartDrawer = lazy(() => import('../components/CartDrawer').then(m => ({ default: m.CartDrawer })));
const LocationSelector = lazy(() => import('../components/LocationSelector').then(m => ({ default: m.LocationSelector })));

export const MainLayout: React.FC = () => {
  const [isCartOpen, setIsCartOpen] = useState(false);
  const [isLocationOpen, setIsLocationOpen] = useState(false);

  return (
    <div className="min-h-screen flex flex-col bg-neutral-50 dark:bg-neutral-950 text-neutral-900 dark:text-neutral-100 transition-colors">
      <NavigationScrollPolicy />
      <a href="#main-content" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[100] focus:rounded-lg focus:bg-white focus:px-4 focus:py-2 focus:font-bold focus:text-neutral-950 focus:shadow-xl">Skip to main content</a>
      <Header
        onOpenCart={() => setIsCartOpen(true)}
        onOpenLocation={() => setIsLocationOpen(true)}
      />

      <main id="main-content" tabIndex={-1} className="flex-1">
        <Outlet />
      </main>

      <Footer />

      <Suspense fallback={null}>
        {isCartOpen && <CartDrawer isOpen onClose={() => setIsCartOpen(false)} />}
        {isLocationOpen && <LocationSelector isOpen onClose={() => setIsLocationOpen(false)} />}
      </Suspense>
    </div>
  );
};
