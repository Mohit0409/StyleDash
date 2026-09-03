import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ShoppingBag, Heart, User, Search, Zap, Sun, Moon, Store, PlusCircle, LoaderCircle } from 'lucide-react';
import { useCart } from '../context/CartContext';
import { useWishlist } from '../context/WishlistContext';
import { useTheme } from '../context/ThemeContext';
import { CONFIG } from '../config';
import { useAuth } from '../context/AuthContext';
import { BrandWordmark } from './BrandWordmark';
import { productRepository } from '../repositories/productRepository';
import { vendorRepository } from '../repositories/vendorRepository';
import type { Product, VendorStore } from '../types';
import { buildSearchSuggestions, highlightSearchMatch, type SearchSuggestion } from '../utils/searchSuggestions';

const SEARCH_DEBOUNCE_MS = 220;
const MIN_SUGGESTION_QUERY = 2;

export const Header: React.FC<{ onOpenCart: () => void }> = ({ onOpenCart }) => {
  const navigate = useNavigate();
  const { totalItemsCount } = useCart();
  const { wishlistIds } = useWishlist();
  const { isDark, toggleTheme } = useTheme();
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [suggestionProducts, setSuggestionProducts] = useState<Product[]>([]);
  const [suggestionStores, setSuggestionStores] = useState<VendorStore[]>([]);
  const [suggestionsLoaded, setSuggestionsLoaded] = useState(false);
  const [suggestionsLoading, setSuggestionsLoading] = useState(false);
  const [suggestionsOpen, setSuggestionsOpen] = useState(false);
  const [activeSuggestionIndex, setActiveSuggestionIndex] = useState(-1);
  const suggestionLoadStarted = useRef(false);
  const { user } = useAuth();

  useEffect(() => {
    const trimmed = searchQuery.trim();
    if (trimmed.length < MIN_SUGGESTION_QUERY) {
      setDebouncedSearch('');
      setActiveSuggestionIndex(-1);
      return;
    }
    const timer = window.setTimeout(() => {
      setDebouncedSearch(trimmed);
      setActiveSuggestionIndex(-1);
    }, SEARCH_DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [searchQuery]);

  useEffect(() => {
    if (debouncedSearch.length < MIN_SUGGESTION_QUERY || suggestionsLoaded || suggestionLoadStarted.current) return;
    suggestionLoadStarted.current = true;
    setSuggestionsLoading(true);
    Promise.all([
      productRepository.getAllProducts(),
      vendorRepository.getAllStores(),
    ])
      .then(([products, stores]) => {
        setSuggestionProducts(products);
        setSuggestionStores(stores);
      })
      .catch(() => {
        setSuggestionProducts([]);
        setSuggestionStores([]);
      })
      .finally(() => {
        setSuggestionsLoaded(true);
        setSuggestionsLoading(false);
      });
  }, [debouncedSearch, suggestionsLoaded]);

  const suggestions = useMemo(
    () => suggestionsLoaded
      ? buildSearchSuggestions(debouncedSearch, suggestionProducts, suggestionStores)
      : [],
    [debouncedSearch, suggestionProducts, suggestionStores, suggestionsLoaded],
  );

  const isDebouncing = searchQuery.trim().length >= MIN_SUGGESTION_QUERY
    && searchQuery.trim() !== debouncedSearch;
  const showSuggestionPanel = suggestionsOpen && searchQuery.trim().length >= MIN_SUGGESTION_QUERY;
  const showSuggestionLoading = isDebouncing || suggestionsLoading || (!suggestionsLoaded && debouncedSearch.length >= MIN_SUGGESTION_QUERY);

  const selectSuggestion = (suggestion: SearchSuggestion) => {
    setSuggestionsOpen(false);
    setActiveSuggestionIndex(-1);
    navigate(suggestion.href);
  };

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!showSuggestionLoading && activeSuggestionIndex >= 0 && suggestions[activeSuggestionIndex]) {
      selectSuggestion(suggestions[activeSuggestionIndex]);
      return;
    }
    const trimmed = searchQuery.trim();
    if (trimmed) {
      setSuggestionsOpen(false);
      setActiveSuggestionIndex(-1);
      navigate(`/products?search=${encodeURIComponent(trimmed)}`);
    }
  };

  const handleSearchKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Escape') {
      setSuggestionsOpen(false);
      setActiveSuggestionIndex(-1);
      return;
    }
    if (showSuggestionLoading || suggestions.length === 0) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSuggestionsOpen(true);
      setActiveSuggestionIndex(current => (current + 1) % suggestions.length);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSuggestionsOpen(true);
      setActiveSuggestionIndex(current => (current <= 0 ? suggestions.length - 1 : current - 1));
    } else if (e.key === 'Enter' && activeSuggestionIndex >= 0) {
      e.preventDefault();
      selectSuggestion(suggestions[activeSuggestionIndex]);
    }
  };

  const highlightedLabel = (label: string) => highlightSearchMatch(label, searchQuery).map((part, index) => (
    part.match
      ? <mark key={`${part.text}-${index}`} className="rounded bg-lime-200 px-0.5 text-neutral-950 dark:bg-lime-400">{part.text}</mark>
      : <React.Fragment key={`${part.text}-${index}`}>{part.text}</React.Fragment>
  ));

  const renderSearchForm = (mobile = false) => {
    const listboxId = `${mobile ? 'mobile' : 'desktop'}-search-suggestions`;
    return (
      <form
        onSubmit={handleSearchSubmit}
        className={`${mobile ? 'md:hidden pb-3' : 'hidden md:block flex-1 max-w-lg'} relative`}
        role="search"
      >
        <input
          type="search"
          value={searchQuery}
          onChange={(e) => {
            setSearchQuery(e.target.value);
            setSuggestionsOpen(true);
          }}
          onFocus={() => setSuggestionsOpen(true)}
          onBlur={() => window.setTimeout(() => setSuggestionsOpen(false), 120)}
          onKeyDown={handleSearchKeyDown}
          aria-label="Search products, brands, or local Neemuch stores"
          aria-autocomplete="list"
          aria-controls={listboxId}
          aria-expanded={showSuggestionPanel}
          aria-activedescendant={activeSuggestionIndex >= 0 ? `${listboxId}-${activeSuggestionIndex}` : undefined}
          role="combobox"
          placeholder={mobile ? 'Search products, brands, categories, or stores' : 'Search products, brands, categories, or local Neemuch stores...'}
          className={mobile
            ? 'w-full pl-10 pr-4 py-2.5 rounded-xl border border-neutral-300 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-800 text-neutral-900 dark:text-white placeholder-neutral-400 focus:outline-none focus:ring-2 focus:ring-lime-400 text-sm'
            : 'w-full pl-10 pr-4 py-2 rounded-full border border-neutral-300 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-800 text-neutral-900 dark:text-white placeholder-neutral-400 focus:outline-none focus:ring-2 focus:ring-lime-400 text-sm transition-all'}
        />
        <Search className={`w-4 h-4 text-neutral-400 absolute left-3.5 ${mobile ? 'top-[0.7rem]' : 'top-1/2 -translate-y-1/2'}`} />

        {showSuggestionPanel && (
          <div
            id={listboxId}
            role="listbox"
            aria-label="Search suggestions"
            className={`absolute left-0 right-0 z-50 overflow-hidden rounded-2xl border border-neutral-200 bg-white shadow-2xl dark:border-neutral-700 dark:bg-neutral-900 ${mobile ? 'top-[3rem]' : 'top-[2.8rem]'}`}
          >
            {showSuggestionLoading ? (
              <div className="flex min-h-20 items-center justify-center gap-2 px-4 py-5 text-sm font-semibold text-neutral-500">
                <LoaderCircle className="h-4 w-4 animate-spin" /> Searching local catalogue…
              </div>
            ) : suggestions.length > 0 ? (
              <div className="max-h-[min(26rem,60vh)] overflow-y-auto py-1">
                {suggestions.map((suggestion, index) => (
                  <button
                    key={suggestion.id}
                    id={`${listboxId}-${index}`}
                    type="button"
                    role="option"
                    aria-selected={activeSuggestionIndex === index}
                    onMouseDown={(e) => e.preventDefault()}
                    onMouseEnter={() => setActiveSuggestionIndex(index)}
                    onClick={() => selectSuggestion(suggestion)}
                    className={`flex w-full items-center gap-3 px-4 py-3 text-left transition-colors ${activeSuggestionIndex === index ? 'bg-lime-50 dark:bg-lime-400/10' : 'hover:bg-neutral-50 dark:hover:bg-neutral-800'}`}
                  >
                    <span className="w-16 shrink-0 rounded-full bg-neutral-100 px-2 py-1 text-center text-[10px] font-black uppercase tracking-wide text-neutral-500 dark:bg-neutral-800 dark:text-neutral-300">
                      {suggestion.type}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-extrabold text-neutral-900 dark:text-white">{highlightedLabel(suggestion.label)}</span>
                      <span className="mt-0.5 block truncate text-[11px] text-neutral-500">{suggestion.secondary}</span>
                    </span>
                  </button>
                ))}
                <div className="border-t border-neutral-100 px-4 py-2 text-[11px] text-neutral-500 dark:border-neutral-800">
                  Use ↑/↓ and Enter, or press Enter without selecting to search all results.
                </div>
              </div>
            ) : (
              <div className="px-4 py-5 text-center">
                <p className="text-sm font-extrabold text-neutral-800 dark:text-neutral-100">No suggestions found</p>
                <p className="mt-1 text-xs text-neutral-500">Press Enter to search the full catalogue for “{searchQuery.trim()}”.</p>
              </div>
            )}
          </div>
        )}
      </form>
    );
  };

  return (
    <header className="sticky top-0 z-40 bg-white dark:bg-neutral-900 border-b border-neutral-200 dark:border-neutral-800 shadow-sm transition-colors">
      {/* Top Banner */}
      <div className="bg-neutral-950 text-white text-xs py-1.5 px-4 text-center flex items-center justify-center gap-2">
        <Zap className="w-3.5 h-3.5 text-lime-400 fill-lime-400" />
        <span><strong>EXPRESS LOCAL DELIVERY</strong> in {CONFIG.SERVICE_CITY} — Weekend Express options appear when eligible.</span>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16 gap-2 sm:gap-4">
          <div className="flex min-w-0 items-center gap-2 sm:gap-6">
            <Link to="/" aria-label="vibe4you home" className="group block w-[168px] sm:w-[205px]">
              <BrandWordmark showTagline className="transition-transform duration-200 group-hover:scale-[1.015]" />
            </Link>
          </div>

          {renderSearchForm(false)}

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
              aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
              title="Toggle Dark Mode"
            >
              {isDark ? <Sun className="w-5 h-5 text-amber-400" /> : <Moon className="w-5 h-5" />}
            </button>

            <Link
              to="/wishlist"
              className="p-2 rounded-full hover:bg-neutral-100 dark:hover:bg-neutral-800 text-neutral-700 dark:text-neutral-300 relative transition-colors"
              aria-label={`Wishlist${wishlistIds.length ? `, ${wishlistIds.length} saved` : ''}`}
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
              aria-label={user ? 'Profile and account' : 'Sign in or open account'}
              title="Profile / Account"
            >
              <User className="w-5 h-5" />
            </Link>

            <button
              onClick={onOpenCart}
              aria-label={`Cart ${totalItemsCount}`}
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

        {renderSearchForm(true)}

        <nav className="flex items-center gap-6 py-2.5 overflow-x-auto no-scrollbar border-t border-neutral-100 dark:border-neutral-800 text-xs font-bold text-neutral-700 dark:text-neutral-300">
          <Link to="/stores" className="text-lime-600 dark:text-lime-400 font-black hover:underline whitespace-nowrap flex items-center gap-1">
            <Store className="w-3.5 h-3.5" /> LOCAL STORES
          </Link>
          <span className="text-neutral-300 dark:text-neutral-700">|</span>
          <Link to="/products?dept=men" className="hover:text-lime-600 transition-colors whitespace-nowrap">MEN</Link>
          <Link to="/products?dept=women" className="hover:text-lime-600 transition-colors whitespace-nowrap">WOMEN</Link>
          <Link to="/products?dept=kids" className="hover:text-lime-600 transition-colors whitespace-nowrap">KIDS</Link>
          <Link to="/products?category=Footwear" className="hover:text-lime-600 transition-colors whitespace-nowrap">FOOTWEAR</Link>
          <Link to="/products?category=Accessories" className="hover:text-lime-600 transition-colors whitespace-nowrap">ACCESSORIES</Link>
          <Link to="/products?category=Beauty%20%26%20Personal%20Care" className="hover:text-lime-600 transition-colors whitespace-nowrap">BEAUTY &amp; CARE</Link>
          <span className="text-neutral-300 dark:text-neutral-700">|</span>
          <Link to="/partner" className="text-emerald-600 dark:text-emerald-400 font-extrabold hover:underline whitespace-nowrap flex items-center gap-1">
            <PlusCircle className="w-3.5 h-3.5" /> LIST YOUR SHOP
          </Link>
        </nav>
      </div>
    </header>
  );
};
