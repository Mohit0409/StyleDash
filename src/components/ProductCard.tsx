import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Heart, Star, Zap, Eye } from 'lucide-react';
import { Product } from '../types';
import { useWishlist } from '../context/WishlistContext';

export const ProductCard: React.FC<{ product: Product; onQuickView?: (p: Product) => void }> = ({
  product,
  onQuickView
}) => {
  const { isInWishlist, toggleWishlist } = useWishlist();
  const [hoveredImage, setHoveredImage] = useState(false);
  const isWishlisted = isInWishlist(product.id);

  const primaryImage = product.images[0] || product.thumbnail;
  const secondaryImage = product.images[1] || primaryImage;

  const availableSizes = Array.from(new Set(product.variants.filter(v => v.stock > 0).map(v => v.size)));
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
        className="absolute top-3 right-3 z-10 p-2 bg-white/80 dark:bg-neutral-800/80 backdrop-blur-md rounded-full shadow-md text-neutral-700 dark:text-neutral-200 hover:scale-110 transition-transform"
      >
        <Heart className={`w-4 h-4 ${isWishlisted ? 'fill-rose-500 text-rose-500' : ''}`} />
      </button>

      {/* Image & Hover Action */}
      <Link
        to={`/product/${product.slug}`}
        className="block relative aspect-[3/4] bg-neutral-100 dark:bg-neutral-800 overflow-hidden"
        onMouseEnter={() => setHoveredImage(true)}
        onMouseLeave={() => setHoveredImage(false)}
      >
        <img
          src={hoveredImage ? secondaryImage : primaryImage}
          alt={product.name}
          className="w-full h-full object-cover object-center group-hover:scale-105 transition-transform duration-500"
          loading="lazy"
          onError={(e) => {
            (e.target as HTMLImageElement).src = 'https://images.unsplash.com/photo-1521572267360-ee0c2909d518?auto=format&fit=crop&w=800&q=80';
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
            <span className="font-bold text-neutral-800 dark:text-neutral-200 uppercase tracking-wider">{product.brand}</span>
            <span className="flex items-center gap-1 text-amber-500 font-semibold">
              <Star className="w-3 h-3 fill-amber-400" /> {product.rating} ({product.reviewCount})
            </span>
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
              <Zap className="w-3 h-3 fill-emerald-400" /> 60-min delivery
            </div>
          </div>

          <Link
            to={`/product/${product.slug}`}
            className="px-3 py-1.5 bg-neutral-950 dark:bg-lime-400 text-white dark:text-neutral-950 text-xs font-bold rounded-lg hover:bg-neutral-800 dark:hover:bg-lime-300 transition-colors"
          >
            Select Option
          </Link>
        </div>
      </div>
    </div>
  );
};
