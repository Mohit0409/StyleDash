import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ShoppingBag, Heart, User, Search, MapPin, Zap, Sun, Moon, Store, PlusCircle } from 'lucide-react';
import { useCart } from '../context/CartContext';
import { useWishlist } from '../context/WishlistContext';
import { useTheme } from '../context/ThemeContext';
import { CONFIG } from '../config';
import { useAuth } from '../context/AuthContext';

export const Header: React.FC<{ onOpenCart: () => void; onOpenLocation: () => void }> = ({
  onOpenCart,
  onOpenLocation
}) => {
  const navigate = useNavigate();
  const { totalItemsCount } = useCart();
  const { wishlistIds } = useWishlist();
  const { isDark, toggleTheme } = useTheme();
  const [searchQuery, setSearchQuery] = useState('');
  const { user } = useAuth();

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      navigate(`/products?search=${encodeURIComponent(searchQuery.trim())}`);
    }
  };

  return (
    <header className="sticky top-0 z-40 bg-white dark:bg-neutral-900 border-b border-neutral-200 dark:border-neutral-800 shadow-sm transition-colors">
      {/* Top Banner */}
      <div className="bg-neutral-950 text-white text-xs py-1.5 px-4 text-center flex items-center justify-center gap-2">
        <Zap className="w-3.5 h-3.5 text-lime-400 fill-lime-400" />
        <span><strong>60-MIN EXPRESS DELIVERY</strong> in {CONFIG.SERVICE_CITY} — Multi-Store Local Marketplace!</span>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16 gap-2 sm:gap-4">
          
          {/* Brand Logo & Tagline */}
          <div className="flex min-w-0 items-center gap-2 sm:gap-6">
            <Link to="/" className="flex items-center gap-2 group">
              <div className="w-9 h-9 bg-neutral-950 dark:bg-lime-400 rounded-xl flex items-center justify-center font-black text-xl text-lime-400 dark:text-neutral-950 shadow-md group-hover:scale-105 transition-transform">
                SD
              </div>
              <div className="flex flex-col">
                <span className="font-extrabold text-xl tracking-tight text-neutral-900 dark:text-white leading-none">
                  Style<span className="text-lime-500">Dash</span>
                </span>
                <span className="hidden sm:block text-[10px] text-neutral-500 font-medium tracking-wide">
                  {CONFIG.TAGLINE}
                </span>
              </div>
            </Link>

            {/* Location Selector */}
            <button
              onClick={onOpenLocation}
              className="hidden lg:flex items-center gap-2 text-xs font-semibold px-3 py-1.5 rounded-full bg-neutral-100 dark:bg-neutral-800 hover:bg-neutral-200 dark:hover:bg-neutral-700 text-neutral-800 dark:text-neutral-200 transition-colors"
            >
              <MapPin className="w-3.5 h-3.5 text-lime-600" />
              <span>Deliver to: <strong>{CONFIG.SERVICE_CITY} ({CONFIG.DEFAULT_PINCODE})</strong></span>
            </button>
          </div>

          {/* Search Bar */}
          <form onSubmit={handleSearchSubmit} className="flex-1 max-w-lg relative hidden md:block">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search products, brands, or local Neemuch stores..."
              className="w-full pl-10 pr-4 py-2 rounded-full border border-neutral-300 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-800 text-neutral-900 dark:text-white placeholder-neutral-400 focus:outline-none focus:ring-2 focus:ring-lime-400 text-sm transition-all"
            />
            <Search className="w-4 h-4 text-neutral-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
          </form>

          {/* Header Action Controls */}
          <div className="flex shrink-0 items-center gap-1 sm:gap-3">
            <Link
              to="/stores"
              className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 text-xs font-extrabold text-neutral-800 dark:text-neutral-200 hover:text-lime-600 transition-colors"
              title="Browse Local Stores"
            >
              <Store className="w-4 h-4 text-lime-600" />
              <span>Local Stores</span>
            </Link>

            <button
              onClick={toggleTheme}
              className="p-2 rounded-full hover:bg-neutral-100 dark:hover:bg-neutral-800 text-neutral-700 dark:text-neutral-300 transition-colors"
              title="Toggle Dark Mode"
            >
              {isDark ? <Sun className="w-5 h-5 text-amber-400" /> : <Moon className="w-5 h-5" />}
            </button>

            <Link
              to="/wishlist"
              className="p-2 rounded-full hover:bg-neutral-100 dark:hover:bg-neutral-800 text-neutral-700 dark:text-neutral-300 relative transition-colors"
              title="Wishlist"
            >
              <Heart className="w-5 h-5" />
              {wishlistIds.length > 0 && (
                <span className="absolute top-1 right-1 bg-rose-500 text-white text-[10px] font-bold w-4 h-4 rounded-full flex items-center justify-center">
                  {wishlistIds.length}
                </span>
              )}
            </Link>

            <Link
              to="/profile"
              className="p-2 rounded-full hover:bg-neutral-100 dark:hover:bg-neutral-800 text-neutral-700 dark:text-neutral-300 transition-colors"
              title="Profile / Account"
            >
              <User className="w-5 h-5" />
            </Link>

            <button
              onClick={onOpenCart}
              className="flex items-center gap-2 bg-neutral-950 dark:bg-lime-400 text-white dark:text-neutral-950 px-4 py-2 rounded-full font-bold text-sm shadow-md hover:bg-neutral-800 dark:hover:bg-lime-300 transition-all transform active:scale-95"
            >
              <ShoppingBag className="w-4 h-4" />
              <span className="hidden sm:inline">Cart</span>
              <span className="bg-lime-400 dark:bg-neutral-900 text-neutral-950 dark:text-lime-400 px-2 py-0.5 rounded-full text-xs font-black">
                {totalItemsCount}
              </span>
            </button>
          </div>
        </div>

        <form onSubmit={handleSearchSubmit} className="md:hidden relative pb-3">
          <input
            type="search"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search products and brands"
            className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-neutral-300 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-800 text-neutral-900 dark:text-white placeholder-neutral-400 focus:outline-none focus:ring-2 focus:ring-lime-400 text-sm"
          />
          <Search className="w-4 h-4 text-neutral-400 absolute left-3.5 top-[0.7rem]" />
        </form>

        {/* Category Navigation Bar */}
        <nav className="flex items-center gap-6 py-2.5 overflow-x-auto no-scrollbar border-t border-neutral-100 dark:border-neutral-800 text-xs font-bold text-neutral-700 dark:text-neutral-300">
          <Link to="/stores" className="text-lime-600 dark:text-lime-400 font-black hover:underline whitespace-nowrap flex items-center gap-1">
            <Store className="w-3.5 h-3.5" /> LOCAL STORES
          </Link>
          <span className="text-neutral-300 dark:text-neutral-700">|</span>
          <Link to="/products?dept=men" className="hover:text-lime-600 transition-colors whitespace-nowrap">MEN</Link>
          <Link to="/products?dept=women" className="hover:text-lime-600 transition-colors whitespace-nowrap">WOMEN</Link>
          <Link to="/products?dept=kids" className="hover:text-lime-600 transition-colors whitespace-nowrap">KIDS</Link>
          <Link to="/products?dept=footwear" className="hover:text-lime-600 transition-colors whitespace-nowrap">FOOTWEAR</Link>
          <Link to="/products?dept=accessories" className="hover:text-lime-600 transition-colors whitespace-nowrap">ACCESSORIES</Link>
          <span className="text-neutral-300 dark:text-neutral-700">|</span>
          <Link to="/partner" className="text-emerald-600 dark:text-emerald-400 font-extrabold hover:underline whitespace-nowrap flex items-center gap-1">
            <PlusCircle className="w-3.5 h-3.5" /> LIST YOUR SHOP
          </Link>
        </nav>
      </div>
    </header>
  );
};
