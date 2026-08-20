import React, { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { Header } from '../components/Header';
import { Footer } from '../components/Footer';
import { CartDrawer } from '../components/CartDrawer';
import { LocationSelector } from '../components/LocationSelector';
import { NavigationScrollPolicy } from '../components/NavigationScrollPolicy';

export const MainLayout: React.FC = () => {
  const [isCartOpen, setIsCartOpen] = useState(false);
  const [isLocationOpen, setIsLocationOpen] = useState(false);

  return (
    <div className="min-h-screen flex flex-col bg-neutral-50 dark:bg-neutral-950 text-neutral-900 dark:text-neutral-100 transition-colors">
      <NavigationScrollPolicy />
      <Header
        onOpenCart={() => setIsCartOpen(true)}
        onOpenLocation={() => setIsLocationOpen(true)}
      />

      <main className="flex-1">
        <Outlet />
      </main>

      <Footer />

      <CartDrawer isOpen={isCartOpen} onClose={() => setIsCartOpen(false)} />
      <LocationSelector isOpen={isLocationOpen} onClose={() => setIsLocationOpen(false)} />
    </div>
  );
};
