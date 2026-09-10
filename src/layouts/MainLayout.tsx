import React, { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { Header } from '../components/Header';
import { Footer } from '../components/Footer';
import { NavigationScrollPolicy } from '../components/NavigationScrollPolicy';
import { useToast } from '../context/ToastContext';

const CartDrawer = lazy(() => import('../components/CartDrawer').then(m => ({ default: m.CartDrawer })));

export const MainLayout: React.FC = () => {
  const [isCartOpen, setIsCartOpen] = useState(false);
  const cartIsOpen = useRef(false);
  const location = useLocation();
  const { showToast } = useToast();

  useEffect(() => {
    cartIsOpen.current = isCartOpen;
  }, [isCartOpen]);

  const openCart = useCallback(() => {
    if (cartIsOpen.current) return;
    window.history.pushState(
      { ...window.history.state, styledashCartDrawer: true },
      '',
      `${location.pathname}${location.search}${location.hash}`,
    );
    setIsCartOpen(true);
  }, [location.hash, location.pathname, location.search]);

  const closeCart = useCallback(() => {
    if (!cartIsOpen.current) return;
    setIsCartOpen(false);
    if (window.history.state?.styledashCartDrawer === true) {
      window.history.back();
    }
  }, []);

  useEffect(() => {
    const closeDrawerOnBack = () => {
      if (cartIsOpen.current && window.history.state?.styledashCartDrawer !== true) {
        setIsCartOpen(false);
      }
    };

    window.addEventListener('popstate', closeDrawerOnBack);
    return () => window.removeEventListener('popstate', closeDrawerOnBack);
  }, []);

  useEffect(() => {
    const historyState = window.history.state as { idx?: number; styledashExitGuard?: boolean } | null;
    const isInitialHomeEntry = location.pathname === '/' && !location.search && !location.hash && historyState?.idx === 0;
    if (!isInitialHomeEntry) return undefined;

    let exitArmed = false;
    let resetTimer = 0;
    const addExitGuard = () => {
      if (window.history.state?.styledashExitGuard === true) return;
      window.history.pushState(
        { ...window.history.state, styledashExitGuard: true },
        '',
        `${location.pathname}${location.search}${location.hash}`,
      );
    };
    const onPopState = () => {
      if (window.history.state?.styledashCartDrawer === true || window.history.state?.styledashExitGuard === true) return;

      if (exitArmed) {
        window.clearTimeout(resetTimer);
        window.history.back();
        return;
      }

      exitArmed = true;
      showToast('Press back again to exit', 'info');
      addExitGuard();
      resetTimer = window.setTimeout(() => { exitArmed = false; }, 2000);
    };

    addExitGuard();
    window.addEventListener('popstate', onPopState);
    return () => {
      window.clearTimeout(resetTimer);
      window.removeEventListener('popstate', onPopState);
    };
  }, [location.hash, location.pathname, location.search, showToast]);

  return (
    <div className="min-h-screen flex flex-col bg-neutral-50 dark:bg-neutral-950 text-neutral-900 dark:text-neutral-100 transition-colors">
      <NavigationScrollPolicy />
      <a href="#main-content" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[100] focus:rounded-lg focus:bg-white focus:px-4 focus:py-2 focus:font-bold focus:text-neutral-950 focus:shadow-xl">Skip to main content</a>
      <Header onOpenCart={openCart} />

      <main id="main-content" tabIndex={-1} className="flex-1">
        <Outlet />
      </main>

      <Footer />

      <Suspense fallback={null}>
        {isCartOpen && <CartDrawer isOpen onClose={closeCart} />}
      </Suspense>
    </div>
  );
};
