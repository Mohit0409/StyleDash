import React, { useEffect, useMemo, useState } from 'react';
import { Link, Navigate, useParams } from 'react-router-dom';
import { ArrowRight, MapPin, ShoppingBag, Store, Zap } from 'lucide-react';
import { SEO } from '../components/SEO';
import { ProductCard } from '../components/ProductCard';
import { NEEMUCH_SHOPPING_PAGES, neemuchShoppingPageBySlug } from '../data/neemuchShopping';
import { productRepository } from '../repositories/productRepository';
import { vendorRepository } from '../repositories/vendorRepository';
import { Product, VendorStore } from '../types';

const PRODUCTION_ORIGIN = 'https://vibe4you.in';
const MAX_PRODUCTS = 40;

const normalize = (value?: string): string => (value || '').trim().toLowerCase();

export const matchesPage = (product: Product, slug: string): boolean => {
  const page = neemuchShoppingPageBySlug(slug);
  if (!page) return false;
  if (page.directory === 'stores') return false;
  if (page.allProducts) return true;
  if (page.category && normalize(product.category) !== normalize(page.category)) return false;
  if (page.department && normalize(product.department) !== normalize(page.department)) return false;

  const hasSpecificTerms = Boolean(page.subcategories?.length || page.nameTerms?.length);
  if (!hasSpecificTerms) return true;

  const subcategory = normalize(product.subcategory);
  const name = normalize(product.name);
  const brand = normalize(product.brand);
  const subcategoryMatch = page.subcategories?.some(value => normalize(value) === subcategory) ?? false;
  const nameMatch = page.nameTerms?.some(term => name.includes(normalize(term)) || brand.includes(normalize(term))) ?? false;
  return subcategoryMatch || nameMatch;
};

export const catalogueUrl = (slug: string): string => {
  const page = neemuchShoppingPageBySlug(slug);
  if (page?.catalogueUrl) return page.catalogueUrl;
  if (!page || page.allProducts) return '/products';
  const params = new URLSearchParams();
  if (page.department) params.set('dept', page.department);
  if (page.category) params.set('category', page.category);
  if (page.subcategories?.length === 1) params.set('subcategory', page.subcategories[0]);
  return `/products?${params.toString()}`;
};

/** Client-side fallback for local development. Production performs a 308
 * redirect before serving the SPA so search engines see only the canonical
 * /neemuch/ URL. */
export const NmhShoppingRedirect: React.FC = () => {
  const { topic } = useParams<{ topic: string }>();
  return <Navigate to={`/neemuch/${topic || 'same-day-delivery'}`} replace />;
};

export const NeemuchShopping: React.FC = () => {
  const { topic } = useParams<{ topic: string }>();
  const page = neemuchShoppingPageBySlug(topic);
  const [products, setProducts] = useState<Product[]>([]);
  const [stores, setStores] = useState<VendorStore[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    if (page?.directory === 'stores') {
      vendorRepository.getAllStores().then(items => {
        if (cancelled) return;
        setStores(items.filter(shop => shop.active && shop.approved && (shop.productCount || 0) > 0)
          .sort((a, b) => a.storeName.localeCompare(b.storeName)));
        setLoading(false);
      });
    } else {
      productRepository.getAllProducts().then(items => {
        if (cancelled) return;
        setProducts(items);
        setLoading(false);
      });
    }
    return () => {
      cancelled = true;
    };
  }, [topic, page?.directory]);

  const matchingProducts = useMemo(() => {
    if (!page) return [];
    return products
      .filter(product => matchesPage(product, page.slug))
      .sort((a, b) =>
        Number(b.featured) - Number(a.featured)
        || Number(b.trending) - Number(a.trending)
        || b.rating - a.rating
        || b.reviewCount - a.reviewCount
        || String(b.updatedAt || '').localeCompare(String(a.updatedAt || ''))
      );
  }, [page, products]);

  if (!page) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-16 text-center">
        <SEO title="Neemuch shopping page not found - Vibe4You" description="The requested Neemuch shopping page could not be found." noIndex />
        <h1 className="text-2xl font-black">Shopping page not found</h1>
        <Link to="/products" className="mt-5 inline-flex rounded-xl bg-neutral-950 px-5 py-3 text-sm font-bold text-white">
          Browse all products
        </Link>
      </div>
    );
  }

  const visibleProducts = matchingProducts.slice(0, MAX_PRODUCTS);
  const visibleStores = stores.slice(0, MAX_PRODUCTS);
  const canonicalUrl = `${PRODUCTION_ORIGIN}/neemuch/${page.slug}`;
  const seoDescription = `${page.description} Neemuch is also commonly searched as NMH.`;
  const jsonLd = {
    '@context': 'https://schema.org',
    '@graph': [
      {
        '@type': 'CollectionPage',
        '@id': `${canonicalUrl}#page`,
        url: canonicalUrl,
        name: page.heading,
        description: seoDescription,
        about: {
          '@type': 'City',
          name: 'Neemuch',
          alternateName: 'NMH',
          address: {
            '@type': 'PostalAddress',
            addressLocality: 'Neemuch',
            addressRegion: 'Madhya Pradesh',
            addressCountry: 'IN',
          },
        },
        isPartOf: {
          '@type': 'WebSite',
          '@id': `${PRODUCTION_ORIGIN}/#website`,
          name: 'Vibe4You',
          url: PRODUCTION_ORIGIN,
        },
      },
      {
        '@type': 'BreadcrumbList',
        itemListElement: [
          {
            '@type': 'ListItem',
            position: 1,
            name: 'Vibe4You',
            item: `${PRODUCTION_ORIGIN}/`,
          },
          {
            '@type': 'ListItem',
            position: 2,
            name: page.heading,
            item: canonicalUrl,
          },
        ],
      },
      {
        '@type': 'ItemList',
        name: page.heading,
        numberOfItems: page.directory === 'stores' ? stores.length : matchingProducts.length,
        itemListElement: page.directory === 'stores'
          ? visibleStores.slice(0, 24).map((shop, index) => ({
            '@type': 'ListItem',
            position: index + 1,
            url: PRODUCTION_ORIGIN + '/store/' + shop.slug,
            name: shop.storeName,
          }))
          : visibleProducts.slice(0, 24).map((product, index) => ({
            '@type': 'ListItem',
            position: index + 1,
            url: PRODUCTION_ORIGIN + '/product/' + product.slug,
            name: product.name,
          })),
      },
    ],
  };

  return (
    <div className="space-y-10 pb-16">
      <SEO title={page.title} description={seoDescription} jsonLd={jsonLd} />

      <section className="border-b border-neutral-200 bg-neutral-950 px-4 py-12 text-white dark:border-neutral-800 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-7xl space-y-5">
          <nav className="flex flex-wrap items-center gap-2 text-xs font-medium text-neutral-400" aria-label="Breadcrumb">
            <Link to="/" className="hover:text-white hover:underline">Home</Link>
            <span>/</span>
            <span className="text-neutral-200">{page.heading}</span>
          </nav>
          <div className="max-w-3xl space-y-4">
            <div className="inline-flex items-center gap-2 rounded-full bg-lime-400 px-3 py-1.5 text-xs font-black uppercase tracking-wide text-neutral-950">
              <MapPin className="h-3.5 w-3.5" /> Shop Local in Neemuch (NMH)
            </div>
            <h1 className="text-3xl font-black tracking-tight sm:text-5xl">{page.heading}</h1>
            <p className="max-w-2xl text-sm leading-6 text-neutral-300 sm:text-base">{page.intro}</p>
            <p className="max-w-2xl text-xs leading-5 text-neutral-400">Searching for the same products in NMH? NMH is a commonly used short name for Neemuch, and these listings cover the same local service area.</p>
            <div className="flex flex-wrap gap-3 pt-1 text-xs font-bold">
              <span className="inline-flex items-center gap-1.5 rounded-xl border border-white/15 bg-white/5 px-3 py-2">
                <Store className="h-4 w-4 text-lime-400" /> Local Neemuch stores
              </span>
              <span className="inline-flex items-center gap-1.5 rounded-xl border border-white/15 bg-white/5 px-3 py-2">
                <Zap className="h-4 w-4 text-lime-400" /> Same Day Delivery in supported areas
              </span>
              <span className="inline-flex items-center gap-1.5 rounded-xl border border-white/15 bg-white/5 px-3 py-2">
                <ShoppingBag className="h-4 w-4 text-lime-400" /> {loading ? 'Loading listings...' : (page.directory === 'stores' ? stores.length + ' stores found' : matchingProducts.length + ' products found')}
              </span>
            </div>
          </div>
        </div>
      </section>

      <div className="mx-auto max-w-7xl space-y-10 px-4 sm:px-6 lg:px-8">
        <section className="space-y-5" aria-labelledby="local-products-heading">
          <div className="flex flex-col gap-2 border-b border-neutral-200 pb-5 dark:border-neutral-800 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-xs font-black uppercase tracking-wider text-lime-700 dark:text-lime-400">Available from local sellers</p>
              <h2 id="local-products-heading" className="mt-1 text-2xl font-black text-neutral-900 dark:text-white">
                  {page.directory === 'stores' ? 'Local shops available now' : page.heading + ' — Products Available Now'}
              </h2>
              <p className="mt-1 text-xs text-neutral-500">
                Browse current Vibe4You listings from participating stores serving Neemuch.
              </p>
            </div>
            <Link to={catalogueUrl(page.slug)} className="inline-flex min-h-11 items-center gap-1 text-sm font-bold text-lime-700 hover:underline dark:text-lime-400">
              Open full catalogue <ArrowRight className="h-4 w-4" />
            </Link>
          </div>

          {loading ? (
            <div className="rounded-3xl border border-neutral-200 bg-white p-10 text-center text-sm text-neutral-500 dark:border-neutral-800 dark:bg-neutral-900">
                {page.directory === 'stores' ? 'Loading local stores...' : 'Loading live local products...'}
            </div>
          ) : page.directory === 'stores' ? (
            visibleStores.length > 0 ? (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {visibleStores.map(shop => (
                  <Link key={shop.id} to={'/store/' + shop.slug}
                    className="rounded-2xl border border-neutral-200 bg-white p-5 transition hover:border-lime-400 hover:shadow-sm dark:border-neutral-700 dark:bg-neutral-900">
                    <div className="flex items-start gap-3">
                      <Store className="mt-1 h-6 w-6 shrink-0 text-lime-700 dark:text-lime-400" />
                      <div>
                        <h3 className="text-base font-bold text-neutral-900 dark:text-white">{shop.storeName}</h3>
                        <p className="mt-1 text-xs text-neutral-500">{shop.category} · {shop.city || 'Neemuch'}</p>
                        <p className="mt-2 text-xs text-neutral-600 dark:text-neutral-300">{shop.productCount} listed products</p>
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            ) : (
              <div className="rounded-3xl border border-neutral-200 bg-white p-10 text-center text-sm text-neutral-500 dark:border-neutral-800 dark:bg-neutral-900">
                No participating stores with published products are currently available.
              </div>
            )
          ) : visibleProducts.length > 0 ? (
            <div className="grid grid-cols-2 gap-4 sm:gap-6 md:grid-cols-3 lg:grid-cols-4">
              {visibleProducts.map(product => <ProductCard key={product.id} product={product} />)}
            </div>
          ) : (
            <div className="rounded-3xl border border-neutral-200 bg-white p-10 text-center text-sm text-neutral-500 dark:border-neutral-800 dark:bg-neutral-900">
              No matching products are currently published. Check the full catalogue for other local options.
            </div>
          )}
        </section>

        <section className="grid gap-4 rounded-3xl border border-neutral-200 bg-white p-6 dark:border-neutral-800 dark:bg-neutral-900 md:grid-cols-3">
          <div>
            <h2 className="font-black text-neutral-900 dark:text-white">Why shop local on Vibe4You?</h2>
            <p className="mt-2 text-sm leading-6 text-neutral-600 dark:text-neutral-300">
              Vibe4You brings products from participating Neemuch stores into one catalogue so you can compare local options before ordering.
            </p>
          </div>
          <div>
            <h3 className="font-black text-neutral-900 dark:text-white">Local availability</h3>
            <p className="mt-2 text-sm leading-6 text-neutral-600 dark:text-neutral-300">
              Product listings come from local shop inventory, helping you discover what nearby sellers currently offer.
            </p>
          </div>
          <div>
            <h3 className="font-black text-neutral-900 dark:text-white">Fast local delivery</h3>
            <p className="mt-2 text-sm leading-6 text-neutral-600 dark:text-neutral-300">
              Same Day Delivery is available within the supported Neemuch service area, subject to product and delivery availability.
            </p>
          </div>
        </section>

        <section className="space-y-4" aria-labelledby="more-neemuch-shopping">
          <h2 id="more-neemuch-shopping" className="text-xl font-black text-neutral-900 dark:text-white">More Shopping in Neemuch</h2>
          <div className="flex flex-wrap gap-2">
            {NEEMUCH_SHOPPING_PAGES.filter(item => item.slug !== page.slug).map(item => (
              <Link
                key={item.slug}
                to={`/neemuch/${item.slug}`}
                className="rounded-full border border-neutral-200 bg-white px-4 py-2 text-xs font-bold text-neutral-700 transition hover:border-lime-400 hover:bg-lime-50 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-200 dark:hover:bg-lime-950/20"
              >
                {item.label}
              </Link>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
};
