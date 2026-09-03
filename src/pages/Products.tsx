import React, { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { MapPin, SlidersHorizontal, Store, Zap } from 'lucide-react';
import { SEO } from '../components/SEO';
import { ProductCard } from '../components/ProductCard';
import { StoreImage } from '../components/StoreImage';
import { FilterSidebar } from '../components/FilterSidebar';
import { Product, VendorStore } from '../types';
import { productRepository } from '../repositories/productRepository';
import { vendorRepository } from '../repositories/vendorRepository';
import { expressCatalogueState } from '../utils/delivery';
import { availableBrandOptions, availableCategoryOptions, availableSizeOptions, matchesCatalogueProduct } from '../utils/catalogFilters';

export const Products: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [products, setProducts] = useState<Product[]>([]);
  const [stores, setStores] = useState<VendorStore[]>([]);
  const [storesLoading, setStoresLoading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [mobileFilterOpen, setMobileFilterOpen] = useState(false);

  // Search parameters state
  const department = searchParams.get('dept') || 'all';
  const category = searchParams.get('category') || 'all';
  const subcategory = searchParams.get('subcategory') || 'all';
  const brand = searchParams.get('brand') || 'all';
  const size = searchParams.get('size') || 'all';
  const maxPrice = Number(searchParams.get('maxPrice')) || 4999;
  const sortBy = searchParams.get('sort') || 'recommended';
  const searchQuery = searchParams.get('search') || '';
  const filterBadge = searchParams.get('filter') || '';
  const { requested: expressRequested, available: expressAvailable, active: expressFilterActive } = expressCatalogueState(filterBadge);

  // Backward compatibility for older links that treated merchandise classes
  // as departments. Canonical seller data now keeps audience (men/women/kids/
  // unisex) separate from category (for example Footwear or Accessories).
  useEffect(() => {
    if (department !== 'footwear' && department !== 'accessories') return;
    const nextParams = new URLSearchParams(searchParams);
    if (!nextParams.has('category')) {
      nextParams.set('category', department === 'footwear' ? 'Footwear' : 'Accessories');
    }
    nextParams.delete('dept');
    setSearchParams(nextParams, { replace: true });
  }, [department, searchParams, setSearchParams]);

  useEffect(() => {
    productRepository.getAllProducts().then(data => {
      setProducts(data);
      setLoading(false);
    });
  }, []);

  useEffect(() => {
    let cancelled = false;

    if (!searchQuery.trim()) {
      setStores([]);
      setStoresLoading(false);
      return () => {
        cancelled = true;
      };
    }

    setStores([]);
    setStoresLoading(true);
    vendorRepository.getAllStores()
      .then(data => {
        if (!cancelled) {
          setStores(data.filter(store => store.approved && store.active));
        }
      })
      .catch(() => {
        if (!cancelled) {
          setStores([]);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setStoresLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [searchQuery]);

  const updateParam = (key: string, value: string) => {
    const newParams = new URLSearchParams(searchParams);
    if (value && value !== 'all') {
      newParams.set(key, value);
    } else {
      newParams.delete(key);
    }
    setSearchParams(newParams);
  };

  const handleClearAll = () => {
    setSearchParams(new URLSearchParams());
  };

  const updateCategory = (value: string) => {
    const nextParams = new URLSearchParams(searchParams);
    if (value && value !== 'all') nextParams.set('category', value);
    else nextParams.delete('category');
    nextParams.delete('subcategory');
    setSearchParams(nextParams);
  };

  const catalogueFilters = useMemo(() => ({
    department,
    category,
    subcategory,
    brand,
    size,
    maxPrice,
    searchQuery,
    filterBadge,
    expressFilterActive,
  }), [department, category, subcategory, brand, size, maxPrice, searchQuery, filterBadge, expressFilterActive]);

  // Facets are derived from the same published catalogue being displayed. Each
  // facet ignores only itself so changing department/category/brand/size never
  // offers an option that is guaranteed to return zero products.
  const categoryOptions = useMemo(
    () => availableCategoryOptions(products, catalogueFilters),
    [products, catalogueFilters],
  );
  const brandOptions = useMemo(
    () => availableBrandOptions(products, catalogueFilters),
    [products, catalogueFilters],
  );
  const sizeOptions = useMemo(
    () => availableSizeOptions(products, catalogueFilters),
    [products, catalogueFilters],
  );

  // Drop stale facet query values when another filter changes the available
  // inventory scope. This prevents an invisible old brand/size from trapping
  // customers on a zero-result page.
  useEffect(() => {
    if (loading) return;
    const nextParams = new URLSearchParams(searchParams);
    let changed = false;
    if (category !== 'all' && !categoryOptions.includes(category)) {
      nextParams.delete('category');
      nextParams.delete('subcategory');
      changed = true;
    }
    if (brand !== 'all' && !brandOptions.includes(brand)) {
      nextParams.delete('brand');
      changed = true;
    }
    if (size !== 'all' && !sizeOptions.includes(size)) {
      nextParams.delete('size');
      changed = true;
    }
    if (changed) setSearchParams(nextParams, { replace: true });
  }, [brand, brandOptions, category, categoryOptions, loading, searchParams, setSearchParams, size, sizeOptions]);

  const filteredProducts = products.filter(product => matchesCatalogueProduct(product, catalogueFilters));

  const matchingStores = searchQuery
    ? stores.filter(store => {
        const q = searchQuery.toLowerCase();
        return [store.storeName, store.category, store.description, store.address, store.city]
          .some(value => value?.toLowerCase().includes(q));
      })
    : [];

  // Sorting logic
  const sortedProducts = [...filteredProducts].sort((a, b) => {
    if (sortBy === 'price-asc') return a.price - b.price;
    if (sortBy === 'price-desc') return b.price - a.price;
    if (sortBy === 'rating') return b.rating - a.rating;
    if (sortBy === 'newest') return (b.newArrival ? 1 : 0) - (a.newArrival ? 1 : 0);
    if (sortBy === 'discount') return b.discount - a.discount;
    return 0; // recommended
  });

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      <SEO title="Browse Fashion Catalogue - Vibe4You" />

      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-neutral-200 dark:border-neutral-800">
        <div>
          <h1 className="text-2xl sm:text-3xl font-black text-neutral-900 dark:text-white capitalize">
            {searchQuery ? `Search results for "${searchQuery}"` : category !== 'all' ? `${category} Catalogue` : `${department} Fashion Catalogue`}
          </h1>
          <p className="text-xs text-neutral-500 mt-1">
            {searchQuery ? (
              <>Found <strong>{matchingStores.length}</strong> local store{matchingStores.length === 1 ? '' : 's'} and <strong>{sortedProducts.length}</strong> available product{sortedProducts.length === 1 ? '' : 's'} in Neemuch</>
            ) : (
              <>Showing <strong>{sortedProducts.length}</strong> available items from local Neemuch stores. Express Local Delivery appears where eligible.</>
            )}
          </p>
        </div>

        {/* Mobile Filter Trigger Button */}
        <button
          onClick={() => setMobileFilterOpen(true)}
          className="lg:hidden flex items-center justify-center gap-2 px-4 py-2.5 bg-neutral-950 dark:bg-lime-400 text-white dark:text-neutral-950 font-bold text-xs rounded-xl"
        >
          <SlidersHorizontal className="w-4 h-4" /> Filter & Sort
        </button>
      </div>

      {searchQuery && matchingStores.length > 0 && (
        <section aria-labelledby="matching-local-stores" className="space-y-3">
          <div className="flex items-center gap-2">
            <Store className="w-5 h-5 text-lime-600" />
            <h2 id="matching-local-stores" className="text-lg font-black text-neutral-900 dark:text-white">Matching Local Stores</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {matchingStores.map(store => (
              <Link key={store.id} to={`/store/${store.slug}`} aria-label={`Visit ${store.storeName} storefront`} className="group flex items-center gap-4 rounded-2xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 p-4 hover:border-lime-400 hover:shadow-md transition-all">
                <StoreImage
                  src={store.logoImage}
                  alt=""
                  storeName={store.storeName}
                  kind="logo"
                  loading="lazy"
                  decoding="async"
                  className="h-14 w-14 shrink-0 rounded-xl object-cover"
                />
                <div className="min-w-0">
                  <h3 className="font-extrabold text-neutral-900 dark:text-white truncate group-hover:text-lime-600">{store.storeName}</h3>
                  <p className="text-xs text-neutral-500 truncate">{store.category}</p>
                  <p className="mt-1 flex items-center gap-1 text-xs text-neutral-500 truncate"><MapPin className="w-3 h-3 shrink-0" /> {store.address}</p>
                  <p className="mt-1 flex items-center gap-1 text-[11px] font-bold text-emerald-600 dark:text-emerald-400"><Zap className="w-3 h-3" /> Express Local Delivery</p>
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}

      {expressRequested && !expressAvailable && (
        <div role="status" className="rounded-2xl border border-amber-200 bg-amber-50 px-5 py-4 text-sm text-amber-950 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-100">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="font-black">Weekend Express is available Saturday and Sunday.</p>
              <p className="mt-1 text-xs opacity-80">Today we are showing the regular local catalogue instead, so you can keep shopping.</p>
            </div>
            <button
              type="button"
              onClick={() => updateParam('filter', 'all')}
              className="shrink-0 rounded-xl bg-neutral-950 px-4 py-2 text-xs font-bold text-white dark:bg-lime-400 dark:text-neutral-950"
            >
              Browse Normal Delivery
            </button>
          </div>
        </div>
      )}

      <div className="flex gap-8 items-start">
        {/* Filter Sidebar */}
        <FilterSidebar
          department={department}
          setDepartment={(d) => updateParam('dept', d)}
          category={category}
          setCategory={updateCategory}
          categories={categoryOptions}
          brand={brand}
          setBrand={(b) => updateParam('brand', b)}
          brands={brandOptions}
          size={size}
          setSize={(s) => updateParam('size', s)}
          sizes={sizeOptions}
          maxPrice={maxPrice}
          setMaxPrice={(p) => updateParam('maxPrice', p.toString())}
          sortBy={sortBy}
          setSortBy={(s) => updateParam('sort', s)}
          onClearAll={handleClearAll}
          isOpenMobile={mobileFilterOpen}
          onCloseMobile={() => setMobileFilterOpen(false)}
        />

        {/* Catalogue Product Grid */}
        <div className="flex-1 min-w-0">
          {loading ? (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-6">
              {[1, 2, 3, 4, 6].map(i => (
                <div key={i} className="aspect-[3/4] bg-neutral-200 dark:bg-neutral-800 rounded-2xl animate-pulse" />
              ))}
            </div>
          ) : sortedProducts.length === 0 && matchingStores.length === 0 && !storesLoading ? (
            <div className="text-center py-20 bg-white dark:bg-neutral-900 rounded-3xl border border-neutral-200 dark:border-neutral-800 p-8">
              <h3 className="font-extrabold text-lg text-neutral-900 dark:text-white mb-2">
                {expressFilterActive ? 'No Weekend Express products are available right now' : 'No matching products found'}
              </h3>
              <p className="text-xs text-neutral-500 mb-6">
                {expressFilterActive ? 'Regular local delivery is still available from local Neemuch stores.' : 'Try relaxing your search terms or clearing filters to view more items.'}
              </p>
              <button
                onClick={expressFilterActive ? () => updateParam('filter', 'all') : handleClearAll}
                className="px-6 py-2.5 bg-neutral-950 dark:bg-lime-400 text-white dark:text-neutral-950 font-bold text-xs rounded-xl"
              >
                {expressFilterActive ? 'Browse Normal Delivery' : 'Clear All Filters'}
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4 sm:gap-6">
              {sortedProducts.map((p, index) => (
                <ProductCard key={p.id} product={p} priority={index === 0} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
