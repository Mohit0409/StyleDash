import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Heart, Star, Zap, Eye } from 'lucide-react';
import { Product } from '../types';
import { useWishlist } from '../context/WishlistContext';

const PRODUCT_IMAGE_FALLBACK = '/product-placeholder.svg';

export const ProductCard: React.FC<{ product: Product; onQuickView?: (p: Product) => void; priority?: boolean }> = ({
  product,
  onQuickView,
  priority = false,
}) => {
  const { isInWishlist, toggleWishlist } = useWishlist();
  const [hoveredImage, setHoveredImage] = useState(false);
  const [failedProductId, setFailedProductId] = useState<string | null>(null);
  const isWishlisted = isInWishlist(product.id);
  const imageFailed = failedProductId === product.id;

  const primaryImage = product.images[0] || product.thumbnail;
  const secondaryImage = product.images[1] || primaryImage;

  const availableSizes = Array.from(new Set(product.variants.filter(v => v.available === true).map(v => v.size)));
  const isAvailable = product.variants.some(v => v.available === true);
  const availabilityResolved = product.variants.length === 0
    || product.variants.every(v => typeof v.available === 'boolean');
  const availableColours = Array.from(new Set(product.variants.map(v => ({ name: v.colourName, hex: v.colourHex }))));

  return (
    <div className="group bg-white dark:bg-neutral-900 rounded-2xl border border-neutral-200 dark:border-neutral-800 overflow-hidden shadow-sm hover:shadow-xl transition-all duration-300 flex flex-col relative">

      {/* Badges */}
      <div className="absolute top-3 left-3 z-10 flex flex-col gap-1 pointer-events-none">
        {product.badge && (
          <span className="bg-neutral-950 text-white dark:bg-lime-400 dark:text-neutral-950 text-[10px] font-black px-2.5 py-1 rounded-full shadow">
            {product.badge}
          </span>
        )}
        {product.discount > 0 && (
          <span className="bg-rose-500 text-white text-[10px] font-bold px-2 py-0.5 rounded-full">
            {product.discount}% OFF
          </span>
        )}
        {product.sponsored && (
          <span className="bg-amber-500 text-white text-[9px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider">
            Sponsored
          </span>
        )}
      </div>

      {/* Wishlist Button */}
      <button
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          toggleWishlist(product.id);
        }}
        aria-label={isWishlisted ? `Remove ${product.name} from wishlist` : `Add ${product.name} to wishlist`}
        aria-pressed={isWishlisted}
        className="absolute top-3 right-3 z-10 flex min-h-11 min-w-11 items-center justify-center rounded-full bg-white/80 p-2 text-neutral-700 shadow-md backdrop-blur-md transition-transform hover:scale-110 dark:bg-neutral-800/80 dark:text-neutral-200"
      >
        <Heart className={`w-4 h-4 ${isWishlisted ? 'fill-rose-500 text-rose-500' : ''}`} />
      </button>

      {/* Image & Hover Action */}
      <Link
        to={`/product/${product.slug}`}
        data-product-card-image
        className="block relative aspect-[4/5] bg-neutral-100 dark:bg-neutral-800 overflow-hidden"
        onMouseEnter={() => setHoveredImage(true)}
        onMouseLeave={() => setHoveredImage(false)}
      >
        <img
          src={imageFailed ? PRODUCT_IMAGE_FALLBACK : (hoveredImage ? secondaryImage : primaryImage)}
          alt={product.name}
          className={`h-full w-full object-center transition-opacity duration-300 ${imageFailed ? 'object-contain p-8' : 'object-cover'}`}
          loading={priority ? 'eager' : 'lazy'}
          fetchPriority={priority ? 'high' : 'auto'}
          decoding="async"
          onError={() => {
            if (!imageFailed) setFailedProductId(product.id);
          }}
        />

        {/* Quick View Button on Hover */}
        {onQuickView && (
          <button
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              onQuickView(product);
            }}
            className="absolute bottom-3 left-3 right-3 py-2 bg-white/90 dark:bg-neutral-900/90 text-neutral-900 dark:text-white text-xs font-bold rounded-xl shadow-lg backdrop-blur-sm opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-1.5"
          >
            <Eye className="w-3.5 h-3.5" /> Quick View
          </button>
        )}
      </Link>

      {/* Product Information */}
      <div className="p-4 flex-1 flex flex-col justify-between">
        <div>
          <div className="flex items-center justify-between text-xs text-neutral-500 mb-1">
            {product.brand && (
              <span className="font-bold text-neutral-800 dark:text-neutral-200 uppercase tracking-wider">{product.brand}</span>
            )}
            {product.reviewCount > 0 && (
              <span className="flex items-center gap-1 text-amber-500 font-semibold">
                <Star className="w-3 h-3 fill-amber-400" /> {product.rating} ({product.reviewCount})
              </span>
            )}
          </div>

          <Link to={`/product/${product.slug}`} className="block">
            <h3 className="font-semibold text-sm text-neutral-900 dark:text-white line-clamp-1 hover:text-lime-600 transition-colors mb-2">
              {product.name}
            </h3>
          </Link>

          {/* Size Pills Preview */}
          <div className="flex items-center gap-1 mb-3 flex-wrap">
            <span className="text-[10px] text-neutral-400 font-medium">Sizes:</span>
            {availableSizes.slice(0, 4).map(sz => (
              <span key={sz} className="text-[10px] px-1.5 py-0.5 rounded bg-neutral-100 dark:bg-neutral-800 text-neutral-700 dark:text-neutral-300 font-medium border border-neutral-200 dark:border-neutral-700">
                {sz}
              </span>
            ))}
            {availableSizes.length > 4 && (
              <span className="text-[10px] text-neutral-400">+{availableSizes.length - 4}</span>
            )}
            {availabilityResolved && !isAvailable && <span className="text-[10px] font-bold text-rose-600">Currently unavailable</span>}
            {!availabilityResolved && <span className="text-[10px] font-semibold text-neutral-500">Select options</span>}
          </div>
        </div>

        {/* Pricing & CTA */}
        <div className="pt-2 border-t border-neutral-100 dark:border-neutral-800 flex items-center justify-between">
          <div>
            <div className="flex items-baseline gap-1.5">
              <span className="text-base font-extrabold text-neutral-900 dark:text-white">₹{product.price}</span>
              {product.originalPrice > product.price && (
                <span className="text-xs text-neutral-400 line-through">₹{product.originalPrice}</span>
              )}
            </div>
            <div className="flex items-center gap-1 text-[10px] font-bold text-emerald-600 dark:text-emerald-400">
              <Zap className="w-3 h-3 fill-emerald-400" /> Same Day Delivery
            </div>
          </div>

          <Link
            to={`/product/${product.slug}`}
            className="inline-flex min-h-11 items-center rounded-lg bg-neutral-950 px-3 py-1.5 text-xs font-bold text-white transition-colors hover:bg-neutral-800 dark:bg-lime-400 dark:text-neutral-950 dark:hover:bg-lime-300"
          >
            Select Option
          </Link>
        </div>
      </div>
    </div>
  );
};
