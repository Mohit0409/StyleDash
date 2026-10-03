import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { ShoppingBag, Heart, User, Search, Zap, Sun, Moon, Store, PlusCircle, LoaderCircle, Grid2X2, Mic, Menu, X } from 'lucide-react';
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
import categoryArtwork from '../assets/category-artwork.jpg';
import './Header.css';

const SEARCH_DEBOUNCE_MS = 220;
const MIN_SUGGESTION_QUERY = 2;

interface SpeechRecognitionResultLike { transcript: string; }
interface SpeechRecognitionEventLike { results: ArrayLike<ArrayLike<SpeechRecognitionResultLike>>; }
interface SpeechRecognitionLike {
  lang: string; continuous: boolean; interimResults: boolean;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: (() => void) | null; onend: (() => void) | null; start: () => void;
}
type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;
const getSpeechRecognitionConstructor = (): SpeechRecognitionConstructor | undefined => {
  const browserWindow = window as unknown as { SpeechRecognition?: SpeechRecognitionConstructor; webkitSpeechRecognition?: SpeechRecognitionConstructor };
  return browserWindow.SpeechRecognition || browserWindow.webkitSpeechRecognition;
};

export const Header: React.FC<{ onOpenCart: () => void }> = ({ onOpenCart }) => {
  const navigate = useNavigate();
  const { key: locationKey } = useLocation();
  const { totalItemsCount } = useCart();
  const { wishlistIds } = useWishlist();
  const { isDark, toggleTheme } = useTheme();
  const [searchQuery, setSearchQuery] = useState('');
  const [isMobileCollapsed, setIsMobileCollapsed] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [mobileSearchOpen, setMobileSearchOpen] = useState(false);
  const [speechSearchAvailable, setSpeechSearchAvailable] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [suggestionProducts, setSuggestionProducts] = useState<Product[]>([]);
  const [suggestionStores, setSuggestionStores] = useState<VendorStore[]>([]);
  const [suggestionsLoaded, setSuggestionsLoaded] = useState(false);
  const [suggestionsLoading, setSuggestionsLoading] = useState(false);
  const [suggestionsOpen, setSuggestionsOpen] = useState(false);
  const [activeSuggestionIndex, setActiveSuggestionIndex] = useState(-1);
  const suggestionLoadStarted = useRef(false);
  const { user } = useAuth();

  useEffect(() => { setSpeechSearchAvailable(Boolean(getSpeechRecognitionConstructor())); }, []);

  // Fixed panels must not cover the destination page after any navigation.
  useEffect(() => {
    setMobileSearchOpen(false);
    setMobileMenuOpen(false);
  }, [locationKey]);

  useEffect(() => {
    let frame = 0;
    const updateCollapsedState = () => {
      frame = 0;
      // Separate thresholds prevent flicker around the collapse boundary.
      // The mobile header's reserved space never changes with this state.
      setIsMobileCollapsed(collapsed => window.innerWidth < 768
        && window.scrollY > (collapsed ? 32 : 104));
    };
    const scheduleUpdate = () => {
      if (frame) return;
      frame = window.requestAnimationFrame(updateCollapsedState);
    };

    updateCollapsedState();
    window.addEventListener('scroll', scheduleUpdate, { passive: true });
    window.addEventListener('resize', scheduleUpdate);
    return () => {
      window.removeEventListener('scroll', scheduleUpdate);
      window.removeEventListener('resize', scheduleUpdate);
      if (frame) window.cancelAnimationFrame(frame);
    };
  }, []);

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

  const startSpeechSearch = () => {
    const SpeechRecognition = getSpeechRecognitionConstructor();
    if (!SpeechRecognition || isListening) return;
    const recognition = new SpeechRecognition();
    recognition.lang = 'en-IN'; recognition.continuous = false; recognition.interimResults = false;
    recognition.onresult = event => {
      const query = event.results[0]?.[0]?.transcript.trim();
      if (query) { setSearchQuery(query); setSuggestionsOpen(false); setActiveSuggestionIndex(-1); navigate(`/products?search=${encodeURIComponent(query)}`); }
    };
    recognition.onerror = () => setIsListening(false); recognition.onend = () => setIsListening(false);
    setIsListening(true); recognition.start();
  };

  const renderSearchForm = (mobile = false) => {
    const listboxId = `${mobile ? 'mobile' : 'desktop'}-search-suggestions`;
    return (
      <form
        onSubmit={handleSearchSubmit}
        className={`${mobile ? 'md:hidden pb-2' : 'hidden md:block flex-1 max-w-lg'} relative`}
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
          placeholder={mobile ? 'Search products or local stores' : 'Search products, brands, categories, or local Neemuch stores...'}
          className={mobile
            ? 'min-h-11 w-full rounded-xl border border-neutral-300 bg-neutral-50 py-2.5 pl-10 pr-11 text-sm text-neutral-900 placeholder-neutral-400 focus:outline-none focus:ring-2 focus:ring-lime-400 dark:border-neutral-700 dark:bg-neutral-800 dark:text-white'
            : 'w-full pl-10 pr-11 py-2 rounded-full border border-neutral-300 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-800 text-neutral-900 dark:text-white placeholder-neutral-400 focus:outline-none focus:ring-2 focus:ring-lime-400 text-sm transition-all'}
        />
        <Search className={`w-4 h-4 text-neutral-400 absolute left-3.5 ${mobile ? 'top-[0.7rem]' : 'top-1/2 -translate-y-1/2'}`} />
        {speechSearchAvailable && (
          <button type="button" onClick={startSpeechSearch} disabled={isListening}
            aria-label={isListening ? 'Listening for a search' : 'Speak to search'}
            title={isListening ? 'Listening…' : 'Speak to search'}
            className={`absolute right-0 flex min-h-11 min-w-11 items-center justify-center rounded-full text-neutral-500 transition-colors hover:bg-neutral-200 hover:text-lime-700 disabled:cursor-wait disabled:text-rose-500 dark:hover:bg-neutral-700 dark:hover:text-lime-400 ${mobile ? 'top-0' : 'top-1/2 -translate-y-1/2'}`}>
            <Mic className={`h-4 w-4 ${isListening ? 'animate-pulse text-rose-500' : ''}`} />
          </button>
        )}

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

  const mobileCategories = [
    { label: 'Women', href: '/products?dept=women', position: '0% 0%' },
    { label: 'Men', href: '/products?dept=men', position: '50% 0%' },
    { label: 'Kids', href: '/products?dept=kids', position: '100% 0%' },
    { label: 'Footwear', href: '/products?category=Footwear', position: '0% 100%' },
    { label: 'Beauty', href: '/products?category=Beauty%20%26%20Personal%20Care', position: '50% 100%' },
    { label: 'Jewellery', href: '/products?category=Accessories', position: '100% 100%' },
  ];

  return (
    <header data-mobile-header-collapsed={isMobileCollapsed ? 'true' : 'false'} className="site-header relative z-40 md:sticky md:top-0 md:border-b md:border-neutral-200 md:bg-white md:shadow-sm dark:md:border-neutral-800 dark:md:bg-neutral-900">
      <div className="hidden min-h-9 items-center justify-center gap-2 bg-neutral-950 px-4 py-2 text-center text-xs text-white md:flex">
        <Zap className="h-4 w-4 fill-lime-400 text-lime-400" />
        <span><strong>SAME-DAY DELIVERY</strong> in {CONFIG.SERVICE_CITY}</span>
      </div>

      <div className="mobile-header-shell fixed inset-x-0 top-0 border-b border-neutral-200 bg-white shadow-sm dark:border-neutral-800 dark:bg-neutral-900 md:hidden">
        <div className="mobile-header-chrome">
        <div className="mobile-header-delivery bg-neutral-950 text-white" aria-hidden={isMobileCollapsed}>
          <div className="flex h-[26px] items-center justify-center gap-1.5 text-[10px] tracking-wide"><Zap className="h-3 w-3 fill-lime-400 text-lime-400" /><span><strong>SAME-DAY DELIVERY</strong> in {CONFIG.SERVICE_CITY}</span></div>
        </div>
        <div className="flex h-[52px] items-center justify-between gap-2 px-3">
          <button type="button" onClick={() => navigate('/')} aria-label="vibe4you home" aria-hidden={isMobileCollapsed} tabIndex={isMobileCollapsed ? -1 : undefined} className="mobile-header-brand block min-h-11 w-[clamp(8rem,40vw,10rem)] shrink-0 text-left"><BrandWordmark className="w-full" /></button>
          <div className="mobile-header-actions ml-auto grid items-center">
            <button type="button" onClick={() => { setMobileSearchOpen(open => !open); setMobileMenuOpen(false); }} className="flex min-h-11 min-w-11 items-center justify-center rounded-full text-neutral-950 hover:bg-neutral-100 dark:text-white dark:hover:bg-neutral-800" aria-label={mobileSearchOpen ? 'Close search' : 'Search products'} aria-expanded={mobileSearchOpen} aria-controls="mobile-header-search"><Search className="h-6 w-6" strokeWidth={2} /></button>
            <button type="button" onClick={onOpenCart} aria-hidden={isMobileCollapsed} tabIndex={isMobileCollapsed ? -1 : undefined} className="mobile-header-bag relative flex h-11 w-11 items-center justify-center rounded-full text-neutral-950 hover:bg-neutral-100 dark:text-white dark:hover:bg-neutral-800" aria-label={`Header bag ${totalItemsCount}`}><ShoppingBag className="h-6 w-6" strokeWidth={2} />{totalItemsCount > 0 && <span className="absolute right-0 top-0 flex h-4 min-w-4 items-center justify-center rounded-full bg-lime-400 px-1 text-[10px] font-bold text-neutral-950">{totalItemsCount}</span>}</button>
            <button type="button" onClick={() => { setMobileMenuOpen(open => !open); setMobileSearchOpen(false); }} className="flex min-h-11 min-w-11 items-center justify-center rounded-full text-neutral-950 hover:bg-neutral-100 dark:text-white dark:hover:bg-neutral-800" aria-label={mobileMenuOpen ? 'Close menu' : 'Open menu'} aria-expanded={mobileMenuOpen} aria-controls="mobile-header-menu">{mobileMenuOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}</button>
          </div>
        </div>

        <nav aria-label="Shop by category" aria-hidden={isMobileCollapsed} className="mobile-header-categories">
          <div className="no-scrollbar flex h-[76px] gap-1 overflow-x-auto px-3 py-1.5">
            {mobileCategories.map(({ label, href, position }) => <Link key={label} to={href} tabIndex={isMobileCollapsed ? -1 : undefined} className="group flex min-w-[56px] flex-1 shrink-0 flex-col items-center gap-0.5 text-center"><span aria-hidden="true" className="h-12 w-12 shrink-0 rounded-full bg-white bg-[length:300%_200%] transition-transform group-active:scale-95 motion-reduce:transition-none" style={{ backgroundImage: `url(${categoryArtwork})`, backgroundPosition: position }} /><span className="text-[10px] font-semibold leading-[14px] text-neutral-800 dark:text-neutral-100">{label}</span></Link>)}
          </div>
        </nav>
        </div>

        {mobileSearchOpen && <div id="mobile-header-search" className="px-3 pb-2">{renderSearchForm(true)}</div>}

        {mobileMenuOpen && <nav id="mobile-header-menu" aria-label="Mobile menu" className="max-h-[60dvh] overflow-y-auto border-t border-neutral-200 bg-white px-4 py-3 shadow-lg dark:border-neutral-800 dark:bg-neutral-900"><div className="grid grid-cols-2 gap-2 text-sm font-bold">
          <Link onClick={() => setMobileMenuOpen(false)} to="/stores" className="rounded-xl px-3 py-3 hover:bg-neutral-100 dark:hover:bg-neutral-800">Local stores</Link><Link onClick={() => setMobileMenuOpen(false)} to="/categories" className="rounded-xl px-3 py-3 hover:bg-neutral-100 dark:hover:bg-neutral-800">All categories</Link><Link onClick={() => setMobileMenuOpen(false)} to="/wishlist" className="rounded-xl px-3 py-3 hover:bg-neutral-100 dark:hover:bg-neutral-800">Wishlist</Link><Link onClick={() => setMobileMenuOpen(false)} to="/profile" className="rounded-xl px-3 py-3 hover:bg-neutral-100 dark:hover:bg-neutral-800">Profile</Link><Link onClick={() => setMobileMenuOpen(false)} to="/partner" className="rounded-xl px-3 py-3 text-emerald-600 hover:bg-neutral-100 dark:text-emerald-400 dark:hover:bg-neutral-800">List your shop</Link><button type="button" onClick={toggleTheme} className="rounded-xl px-3 py-3 text-left hover:bg-neutral-100 dark:hover:bg-neutral-800">{isDark ? 'Light mode' : 'Dark mode'}</button>
        </div></nav>}
      </div>

      <div className="mx-auto hidden max-w-7xl px-4 sm:px-6 md:block lg:px-8">
        <div className="flex min-h-16 items-center justify-between gap-4 py-1.5 sm:h-16 sm:py-0">
          <div className="flex min-w-0 shrink items-center"><Link to="/" aria-label="vibe4you home" className="group block w-[205px] shrink-0"><BrandWordmark showTagline className="transition-transform duration-200 group-hover:scale-[1.015]" /></Link></div>
          {renderSearchForm(false)}
          <div className="flex shrink-0 items-center gap-3">
            <Link to="/stores" className="flex min-h-11 items-center gap-1.5 px-3 py-1.5 text-xs font-extrabold text-neutral-800 transition-colors hover:text-lime-600 dark:text-neutral-200" title="Browse Local Stores"><Store className="h-4 w-4 text-lime-600" /><span>Local Stores</span></Link>
            <button onClick={toggleTheme} className="flex min-h-11 min-w-11 items-center justify-center rounded-full p-2 text-neutral-700 transition-colors hover:bg-neutral-100 dark:text-neutral-300 dark:hover:bg-neutral-800" aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'} title="Toggle Dark Mode">{isDark ? <Sun className="h-5 w-5 text-amber-400" /> : <Moon className="h-5 w-5" />}</button>
            <Link to="/wishlist" className="relative flex min-h-11 min-w-11 items-center justify-center rounded-full p-2 text-neutral-700 transition-colors hover:bg-neutral-100 dark:text-neutral-300 dark:hover:bg-neutral-800" aria-label={`Wishlist${wishlistIds.length ? `, ${wishlistIds.length} saved` : ''}`} title="Wishlist"><Heart className="h-5 w-5" />{wishlistIds.length > 0 && <span className="absolute right-1 top-1 flex h-4 w-4 items-center justify-center rounded-full bg-rose-500 text-[10px] font-bold text-white">{wishlistIds.length}</span>}</Link>
            <Link to="/profile" className="flex min-h-11 min-w-11 items-center justify-center rounded-full p-2 text-neutral-700 transition-colors hover:bg-neutral-100 dark:text-neutral-300 dark:hover:bg-neutral-800" aria-label={user ? 'Profile and account' : 'Sign in or open account'} title="Profile / Account"><User className="h-5 w-5" /></Link>
            <button onClick={onOpenCart} aria-label={`Cart ${totalItemsCount}`} className="flex min-h-11 items-center gap-2 rounded-full bg-neutral-950 px-4 py-2 text-sm font-bold text-white shadow-md transition-all active:scale-95 hover:bg-neutral-800 dark:bg-lime-400 dark:text-neutral-950 dark:hover:bg-lime-300"><ShoppingBag className="h-4 w-4" /><span>Cart</span><span className="rounded-full bg-lime-400 px-2 py-0.5 text-xs font-black text-neutral-950 dark:bg-neutral-900 dark:text-lime-400">{totalItemsCount}</span></button>
          </div>
        </div>
        <nav aria-label="Shop navigation" className="flex items-center gap-4 overflow-x-auto border-t border-neutral-100 text-xs font-semibold text-neutral-700 no-scrollbar dark:border-neutral-800 dark:text-neutral-300">
          <Link to="/categories" className="inline-flex min-h-11 items-center gap-1 whitespace-nowrap transition-colors hover:text-lime-600"><Grid2X2 className="h-3.5 w-3.5" /> Categories</Link><span className="text-neutral-300 dark:text-neutral-700">|</span><Link to="/products?dept=men" className="inline-flex min-h-11 items-center whitespace-nowrap transition-colors hover:text-lime-600">Men</Link><Link to="/products?dept=women" className="inline-flex min-h-11 items-center whitespace-nowrap transition-colors hover:text-lime-600">Women</Link><Link to="/products?dept=kids" className="inline-flex min-h-11 items-center whitespace-nowrap transition-colors hover:text-lime-600">Kids</Link><Link to="/products?category=Footwear" className="inline-flex min-h-11 items-center whitespace-nowrap transition-colors hover:text-lime-600">Footwear</Link><Link to="/products?category=Accessories" className="inline-flex min-h-11 items-center whitespace-nowrap transition-colors hover:text-lime-600">Accessories</Link><Link to="/products?category=Beauty%20%26%20Personal%20Care" className="inline-flex min-h-11 items-center whitespace-nowrap transition-colors hover:text-lime-600">Beauty &amp; Care</Link><span className="text-neutral-300 dark:text-neutral-700">|</span><Link to="/partner" className="inline-flex min-h-11 items-center gap-1 whitespace-nowrap font-extrabold text-emerald-600 hover:underline dark:text-emerald-400"><PlusCircle className="h-3.5 w-3.5" /> List your shop</Link>
        </nav>
      </div>
    </header>
  );
};
