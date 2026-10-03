import React from 'react';
import { Heart, Home, ShoppingBag, User } from 'lucide-react';
import { NavLink } from 'react-router-dom';
import { useCart } from '../context/CartContext';
import { useWishlist } from '../context/WishlistContext';

export const MobileBottomNav: React.FC<{ onOpenCart: () => void }> = ({ onOpenCart }) => {
  const { totalItemsCount } = useCart();
  const { wishlistIds } = useWishlist();

  const navLinkClass = ({ isActive }: { isActive: boolean }) =>
    `relative flex min-h-14 flex-col items-center justify-center gap-0.5 rounded-2xl px-2 text-[11px] font-bold transition-colors ${isActive
      ? 'bg-lime-100 text-neutral-950 dark:bg-lime-400 dark:text-neutral-950'
      : 'text-neutral-600 hover:bg-neutral-100 dark:text-neutral-300 dark:hover:bg-neutral-800'}`;

  return (
    <nav
      aria-label="Mobile primary navigation"
      data-mobile-bottom-nav
      className="fixed inset-x-0 bottom-0 z-50 border-t border-neutral-200 bg-white/95 px-3 pt-2 shadow-[0_-8px_24px_rgba(0,0,0,0.08)] backdrop-blur-xl dark:border-neutral-800 dark:bg-neutral-950/95 md:hidden"
      style={{ paddingBottom: 'max(0.5rem, env(safe-area-inset-bottom))' }}
    >
      <div className="mx-auto grid max-w-md grid-cols-4 gap-1">
        <NavLink to="/" end className={navLinkClass} aria-label="Home">
          <Home className="h-5 w-5" />
          <span>Home</span>
        </NavLink>

        <NavLink to="/profile" className={navLinkClass} aria-label="Profile">
          <User className="h-5 w-5" />
          <span>Profile</span>
        </NavLink>

        <button
          type="button"
          onClick={onOpenCart}
          aria-label={`Cart ${totalItemsCount}`}
          className="relative flex min-h-14 flex-col items-center justify-center gap-0.5 rounded-2xl px-2 text-[11px] font-bold text-neutral-600 transition-colors hover:bg-neutral-100 active:scale-[0.98] dark:text-neutral-300 dark:hover:bg-neutral-800"
        >
          <span className="relative">
            <ShoppingBag className="h-5 w-5" />
            {totalItemsCount > 0 && (
              <span className="absolute -right-2.5 -top-2 flex min-h-4 min-w-4 items-center justify-center rounded-full bg-lime-400 px-1 text-[9px] font-black leading-none text-neutral-950">
                {totalItemsCount}
              </span>
            )}
          </span>
          <span>Cart</span>
        </button>

        <NavLink
          to="/wishlist"
          className={navLinkClass}
          aria-label={`Wishlist${wishlistIds.length ? `, ${wishlistIds.length} saved` : ''}`}
        >
          <span className="relative">
            <Heart className="h-5 w-5" />
            {wishlistIds.length > 0 && (
              <span className="absolute -right-2.5 -top-2 flex min-h-4 min-w-4 items-center justify-center rounded-full bg-rose-500 px-1 text-[9px] font-black leading-none text-white">
                {wishlistIds.length}
              </span>
            )}
          </span>
          <span>Wishlist</span>
        </NavLink>
      </div>
    </nav>
  );
};
