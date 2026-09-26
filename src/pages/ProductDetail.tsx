import React, { useCallback, useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { Star, Zap, Heart, ShieldCheck, RefreshCw, ShoppingBag, CheckCircle, ArrowRight, Share2 } from 'lucide-react';
import { SEO } from '../components/SEO';
import { VariantSelector } from '../components/VariantSelector';
import { SizeGuideModal } from '../components/SizeGuideModal';
import { ProductCard } from '../components/ProductCard';
import { ProductImageLightbox } from '../components/ProductImageLightbox';
import { ProductReviews } from '../components/ProductReviews';
import { Product, ProductVariant } from '../types';
import { productRepository } from '../repositories/productRepository';
import { useCart } from '../context/CartContext';
import { useWishlist } from '../context/WishlistContext';
import { useToast } from '../context/ToastContext';
import { CONFIG } from '../config';
import { productGalleryImages } from '../utils/productGallery';

export const ProductDetail: React.FC = () => {
  const { slug } = useParams<{ slug: string }>();
  const navigate = useNavigate();
  const { addItem, addTryAtHomeItem } = useCart();
  const { isInWishlist, toggleWishlist, wishlistReady } = useWishlist();
  const { showToast } = useToast();

  const [product, setProduct] = useState<Product | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedImage, setSelectedImage] = useState<string>('');
  const [imageViewerOpen, setImageViewerOpen] = useState(false);
  const [selectedSize, setSelectedSize] = useState<string | null>(null);
  const [selectedColour, setSelectedColour] = useState<string | null>(null);
  const [quantity, setQuantity] = useState(1);
  const [sizeGuideOpen, setSizeGuideOpen] = useState(false);
  const [relatedProducts, setRelatedProducts] = useState<Product[]>([]);
  const [tryAtHomeSizeIds, setTryAtHomeSizeIds] = useState<string[]>([]);
  const [tryAtHomeTermsAccepted, setTryAtHomeTermsAccepted] = useState(false);

  const handleReviewSummaryChange = useCallback((rating: number, reviewCount: number) => {
    setProduct(current => current ? { ...current, rating, reviewCount } : current);
  }, []);

  useEffect(() => {
    if (!slug) return;
    let cancelled = false;
    setLoading(true);
    setRelatedProducts([]);
    (async () => {
      const p = await productRepository.getProductBySlug(slug);
      if (cancelled) return;
      if (p) {
        setProduct(p);
        setSelectedImage(p.images[0] || p.thumbnail);
        if (p.variants.length > 0) {
          const firstInStock = p.variants.find(v => v.available === true) || p.variants[0];
          setSelectedSize(firstInStock.size);
          setSelectedColour(firstInStock.colourName);
        }
      } else {
        setProduct(null);
      }
      setLoading(false);
      if (p) {
        const related = await productRepository.getSimilarProducts(p);
        if (!cancelled) setRelatedProducts(related.slice(0, 4));
      }
    })();
    return () => { cancelled = true; };
  }, [slug]);

  useEffect(() => {
    if (!product) return;
    const variantImages = product.variants.find(variant => variant.colourName === selectedColour)?.images || [];
    const colourImages = productGalleryImages(product.images, variantImages);
    setSelectedImage(colourImages[0] || product.thumbnail);
    setImageViewerOpen(false);
  }, [product, selectedColour]);

  if (loading) {
    return <div className="max-w-7xl mx-auto p-12 text-center text-neutral-500">Loading Vibe4You Product...</div>;
  }

  if (!product) {
    return (
      <div className="max-w-7xl mx-auto p-12 text-center space-y-4">
        <SEO title="Product not found - Vibe4You" description="The requested fashion item could not be found." noIndex />
        <h1 className="text-2xl font-black">Product Not Found</h1>
        <p className="text-xs text-neutral-500">The fashion item you are looking for is no longer available.</p>
        <Link to="/products" className="inline-block px-6 py-2.5 bg-neutral-950 text-white text-xs font-bold rounded-xl">
          Browse Fashion Catalogue
        </Link>
      </div>
    );
  }

  const selectedVariant = product.variants.find(
    v => v.size === selectedSize && v.colourName === selectedColour
  ) || null;
  const availabilityResolved = product.variants.length === 0
    || product.variants.every(variant => typeof variant.available === 'boolean');
  const variantImages = product.variants.find(v => v.colourName === selectedColour)?.images || [];
  const selectedColourImages = productGalleryImages(product.images, variantImages);
  const galleryImages = selectedColourImages.length > 0 ? selectedColourImages : [product.thumbnail];
  const tryAtHomeVariants = product.variants.filter(
    variant => variant.available === true && variant.colourName === selectedColour,
  );
  const tryAtHomeEligible = product.tryAtHomeAvailable === true
    && new Set(tryAtHomeVariants.map(variant => variant.size)).size >= 2;

  const isWishlisted = isInWishlist(product.id);

  const handleAddToCart = async () => {
    if (tryAtHomeSizeIds.length > 0) {
      if (tryAtHomeSizeIds.length !== 2 || !tryAtHomeTermsAccepted) {
        showToast('Select two sizes and accept the Try at Home terms.', 'error');
        return false;
      }
      const success = await addTryAtHomeItem(product, tryAtHomeSizeIds, tryAtHomeTermsAccepted);
      if (success) showToast(`Two sizes of ${product.name} are reserved for Try at Home.`, 'success');
      else showToast('One of the selected sizes is out of stock.', 'error');
      return success;
    }
    if (!selectedVariant) {
      showToast('Please select a valid size and colour', 'error');
      return false;
    }
    const success = await addItem(product, selectedVariant.id, quantity);
    if (success) {
      showToast(`Added ${product.name} (${selectedSize}, ${selectedColour}) to cart!`, 'success');
      return true;
    } else {
      showToast('Selected variant is out of stock', 'error');
      return false;
    }
  };

  const handleBuyNow = async () => {
    if (await handleAddToCart()) navigate('/checkout');
  };

  const handleShareProduct = async () => {
    const url = new URL(`/product/${product.slug}`, window.location.origin).href;
    const shareData = {
      title: `${product.name} | Vibe4You`,
      text: `Check out ${product.name} on Vibe4You`,
      url,
    };

    try {
      if (typeof navigator.share === 'function') {
        await navigator.share(shareData);
        return;
      }

      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(url);
      } else {
        const input = document.createElement('textarea');
        input.value = url;
        input.setAttribute('readonly', '');
        input.style.position = 'fixed';
        input.style.opacity = '0';
        document.body.appendChild(input);
        input.select();
        document.execCommand('copy');
        input.remove();
      }
      showToast('Product link copied. Share it anywhere!', 'success');
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') return;
      showToast('Could not share this product. Please try again.', 'error');
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-12">
      <SEO
        title={`${product.name}${product.brand ? ` - ${product.brand}` : ""} | Vibe4You`}
        description={product.shortDescription}
        image={product.images[0] || product.thumbnail}
        type="product"
        jsonLd={{
          '@context': 'https://schema.org',
          '@type': 'Product',
          name: product.name,
          description: product.shortDescription,
          image: product.images.map(image => new URL(image, 'https://vibe4you.in').href),
          sku: product.id,
          brand: product.brand ? { '@type': 'Brand', name: product.brand } : undefined,
          offers: {
            '@type': 'Offer',
            priceCurrency: 'INR',
            price: product.price,
            availability: availabilityResolved
              ? (product.variants.some(variant => variant.available === true)
                ? 'https://schema.org/InStock'
                : 'https://schema.org/OutOfStock')
              : undefined,
          },
          aggregateRating: product.reviewCount > 0 ? {
            '@type': 'AggregateRating',
            ratingValue: product.rating,
            reviewCount: product.reviewCount,
          } : undefined,
        }}
      />

      {/* Breadcrumbs */}
      <nav className="text-xs font-medium text-neutral-500 flex items-center gap-2">
        <Link to="/" className="hover:underline">Home</Link>
        <span>/</span>
        <Link to={`/products?dept=${product.department}`} className="hover:underline uppercase">{product.department}</Link>
        <span>/</span>
        <span className="text-neutral-900 dark:text-white font-bold">{product.name}</span>
      </nav>

      {/* Product Detail Grid */}
      <div className="grid lg:grid-cols-2 gap-12">
        
        {/* Product Gallery */}
        <div className="space-y-4">
          <button
            type="button"
            onClick={() => setImageViewerOpen(true)}
            aria-label={`Open full screen image of ${product.name}`}
            className="relative block aspect-[3/4] w-full overflow-hidden rounded-3xl border border-neutral-200 bg-neutral-100 text-left focus:outline-none focus:ring-2 focus:ring-lime-500 focus:ring-offset-2 dark:border-neutral-800 dark:bg-neutral-800 dark:focus:ring-offset-neutral-950"
          >
            <img
              src={selectedImage}
              alt={product.name}
              className="h-full w-full object-contain object-center p-3"
            />
            {product.badge && (
              <span className="absolute top-4 left-4 bg-neutral-950 text-white dark:bg-lime-400 dark:text-neutral-950 text-xs font-black px-3 py-1 rounded-full shadow">
                {product.badge}
              </span>
            )}
          </button>

          <div className="flex gap-3 overflow-x-auto no-scrollbar">
            {galleryImages.map((img, idx) => (
              <button
                key={idx}
                onClick={() => setSelectedImage(img)}
                className={`w-20 aspect-[3/4] rounded-xl overflow-hidden border-2 transition-all ${
                  selectedImage === img ? 'border-lime-500 scale-105 shadow-md' : 'border-transparent opacity-70'
                }`}
              >
                <img src={img} alt={`${product.name} ${idx + 1}`} loading="lazy" decoding="async" className="h-full w-full object-contain object-center p-1" />
              </button>
            ))}
          </div>
        </div>

        {/* Product Details & Actions */}
        <div className="space-y-6">
          <div>
            {product.brand && (
              <span className="text-xs font-black uppercase tracking-widest text-lime-600 dark:text-lime-400">{product.brand}</span>
            )}
            <h1 className="text-2xl sm:text-3xl font-black text-neutral-900 dark:text-white mt-1">{product.name}</h1>
            <p className="text-xs text-neutral-500 mt-2">{product.shortDescription}</p>

            {/* Rating */}
            {product.reviewCount > 0 && (
              <div className="flex items-center gap-2 mt-3 text-xs font-bold text-amber-500">
                <div className="flex items-center gap-1 bg-amber-50 dark:bg-amber-950/40 px-2.5 py-1 rounded-full border border-amber-200 dark:border-amber-800">
                  <Star className="w-3.5 h-3.5 fill-amber-400" />
                  <span>{product.rating}</span>
                </div>
                <span className="text-neutral-400">({product.reviewCount} customer reviews)</span>
              </div>
            )}
          </div>

          {/* Pricing */}
          <div className="p-4 bg-neutral-50 dark:bg-neutral-800/50 rounded-2xl border border-neutral-200 dark:border-neutral-800 flex items-baseline gap-3">
            <span className="text-3xl font-black text-neutral-900 dark:text-white">₹{selectedVariant?.price ?? product.price}</span>
            {product.originalPrice > product.price && (
              <>
                <span className="text-sm text-neutral-400 line-through">₹{product.originalPrice}</span>
                <span className="text-xs font-black text-rose-500 bg-rose-50 dark:bg-rose-950/40 px-2 py-0.5 rounded-full">
                  {product.discount}% OFF
                </span>
              </>
            )}
            <span className="text-[10px] text-neutral-400 ml-auto">Price includes GST</span>
          </div>

          {/* Variant Selector */}
          <VariantSelector
            product={product}
            selectedVariantId={selectedVariant?.id || null}
            onSelectVariant={() => {}}
            selectedSize={selectedSize}
            onSelectSize={(s) => setSelectedSize(s)}
            selectedColour={selectedColour}
            onSelectColour={(c) => {
              setSelectedColour(c);
              setTryAtHomeSizeIds([]);
              setTryAtHomeTermsAccepted(false);
              const firstSize = product.variants.find(variant => variant.colourName === c && variant.available === true)
                || product.variants.find(variant => variant.colourName === c);
              setSelectedSize(firstSize?.size || null);
            }}
            onOpenSizeGuide={() => setSizeGuideOpen(true)}
          />

          {tryAtHomeEligible && (
            <section className="rounded-2xl border border-lime-300 bg-lime-50 p-4 text-xs text-neutral-700 dark:border-lime-800 dark:bg-lime-950/30 dark:text-neutral-200" aria-labelledby="try-at-home-heading">
              <h2 id="try-at-home-heading" className="font-black text-sm">Try two sizes at home</h2>
              <p className="mt-1">Choose exactly two sizes of the selected colour. A ₹50 Try at Home fee is added securely at checkout. You have 15 minutes to decide; extra time costs ₹50.</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {tryAtHomeVariants.map(variant => {
                  const selected = tryAtHomeSizeIds.includes(variant.id);
                  return <button key={variant.id} type="button" onClick={() => setTryAtHomeSizeIds(current => selected ? current.filter(id => id !== variant.id) : current.length < 2 ? [...current, variant.id] : current)} className={`rounded-lg border px-3 py-2 font-bold ${selected ? 'border-lime-600 bg-lime-400 text-neutral-950' : 'border-neutral-300 bg-white dark:border-neutral-700 dark:bg-neutral-900'}`}>{variant.size}</button>;
                })}
              </div>
              <label className="mt-3 flex gap-2 leading-relaxed"><input type="checkbox" checked={tryAtHomeTermsAccepted} onChange={event => setTryAtHomeTermsAccepted(event.target.checked)} className="mt-0.5 accent-lime-600" /> I agree to return the unselected size to the delivery partner within 15 minutes and understand the ₹50 late-selection charge.</label>
            </section>
          )}

          {/* Stock Status Badge */}
          {selectedVariant && (
            <div className="text-xs font-bold">
              {selectedVariant.available === true ? (
                <span className="text-emerald-600 dark:text-emerald-400 flex items-center gap-1">
                  <CheckCircle className="w-4 h-4" /> In stock in Neemuch
                </span>
              ) : selectedVariant.available === false ? (
                <span className="text-rose-600 dark:text-rose-400">Out of Stock for this variant</span>
              ) : (
                <span className="text-neutral-500">Checking live availability…</span>
              )}
            </div>
          )}

          {/* CTA Action Buttons */}
          <div className="flex gap-4 pt-4">
            <button
              onClick={handleAddToCart}
              disabled={!selectedVariant || selectedVariant.available !== true}
              className="flex-1 py-4 bg-neutral-950 dark:bg-lime-400 text-white dark:text-neutral-950 font-black text-sm rounded-2xl shadow-xl hover:bg-neutral-800 dark:hover:bg-lime-300 transition-all flex items-center justify-center gap-2 disabled:opacity-50"
            >
              <ShoppingBag className="w-4 h-4" /> Add to Cart
            </button>

            <button
              onClick={handleBuyNow}
              disabled={!selectedVariant || selectedVariant.available !== true}
              className="px-8 py-4 bg-lime-400 text-neutral-950 font-black text-sm rounded-2xl shadow-xl hover:bg-lime-300 transition-all disabled:opacity-50"
            >
              Buy Now
            </button>

            <button
              type="button"
              onClick={handleShareProduct}
              aria-label={`Share ${product.name}`}
              title="Share product"
              className="p-4 rounded-2xl border border-neutral-300 dark:border-neutral-700 hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors"
            >
              <Share2 className="w-5 h-5" />
            </button>

            <button
              onClick={() => toggleWishlist(product.id)}
              aria-label={isWishlisted ? `Remove ${product.name} from wishlist` : `Add ${product.name} to wishlist`}
              aria-pressed={isWishlisted}
              disabled={!wishlistReady}
              className="p-4 rounded-2xl border border-neutral-300 dark:border-neutral-700 hover:bg-neutral-100 disabled:cursor-wait disabled:opacity-60 dark:hover:bg-neutral-800"
            >
              <Heart className={`w-5 h-5 ${isWishlisted ? 'fill-rose-500 text-rose-500' : ''}`} />
            </button>
          </div>

          {/* Hyperlocal Delivery Trust Box */}
          <div className="p-4 bg-lime-50 dark:bg-lime-950/20 rounded-2xl border border-lime-200 dark:border-lime-900 space-y-2 text-xs text-neutral-700 dark:text-neutral-300">
            <div className="flex items-center gap-2 font-black text-lime-800 dark:text-lime-300">
              <Zap className="w-4 h-4 fill-lime-500" />
              <span>Dispatched from Neemuch Partner Boutique</span>
            </div>
            <p>Same Day Delivery is available to pincode 458441. Weekend Express is available at checkout on Saturday and Sunday.</p>
          </div>

          {/* Specifications */}
          <div className="pt-6 border-t border-neutral-200 dark:border-neutral-800 space-y-2 text-xs text-neutral-600 dark:text-neutral-400">
            <p><strong>Material:</strong> {product.material}</p>
            {product.fit && <p><strong>Fit:</strong> {product.fit}</p>}
            <p><strong>Care Instructions:</strong> {product.careInstructions.join(', ')}</p>
            <p><strong>Exchange:</strong> {product.exchangeAvailable ? `Eligible for size exchange within ${product.returnWindowDays} days for ₹50; replacement stock and conditions apply.` : 'Not available for this product.'}</p>
          </div>
        </div>
      </div>

      {/* Size Guide Modal */}
      <SizeGuideModal
        isOpen={sizeGuideOpen}
        onClose={() => setSizeGuideOpen(false)}
        department={product.department}
      />

      <ProductImageLightbox
        imageUrls={galleryImages}
        selectedImage={selectedImage}
        productName={product.name}
        isOpen={imageViewerOpen}
        onSelectImage={setSelectedImage}
        onClose={() => setImageViewerOpen(false)}
      />

      <ProductReviews productId={product.id} onSummaryChange={handleReviewSummaryChange} />

      {/* Similar Products */}
      <section className="pt-12 border-t border-neutral-200 dark:border-neutral-800 space-y-6">
        <h3 className="text-xl font-black text-neutral-900 dark:text-white">You May Also Like</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 sm:gap-6">
          {relatedProducts.map(p => (
            <ProductCard key={p.id} product={p} />
          ))}
        </div>
      </section>
    </div>
  );
};
