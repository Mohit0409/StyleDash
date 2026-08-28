import React, { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { Star, Zap, Heart, ShieldCheck, RefreshCw, ShoppingBag, CheckCircle, ArrowRight } from 'lucide-react';
import { SEO } from '../components/SEO';
import { VariantSelector } from '../components/VariantSelector';
import { SizeGuideModal } from '../components/SizeGuideModal';
import { ProductCard } from '../components/ProductCard';
import { Product, ProductVariant } from '../types';
import { productRepository } from '../repositories/productRepository';
import { useCart } from '../context/CartContext';
import { useWishlist } from '../context/WishlistContext';
import { useToast } from '../context/ToastContext';
import { CONFIG } from '../config';

export const ProductDetail: React.FC = () => {
  const { slug } = useParams<{ slug: string }>();
  const navigate = useNavigate();
  const { addItem } = useCart();
  const { isInWishlist, toggleWishlist } = useWishlist();
  const { showToast } = useToast();

  const [product, setProduct] = useState<Product | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedImage, setSelectedImage] = useState<string>('');
  const [selectedSize, setSelectedSize] = useState<string | null>(null);
  const [selectedColour, setSelectedColour] = useState<string | null>(null);
  const [quantity, setQuantity] = useState(1);
  const [sizeGuideOpen, setSizeGuideOpen] = useState(false);
  const [relatedProducts, setRelatedProducts] = useState<Product[]>([]);

  useEffect(() => {
    if (!slug) return;
    setLoading(true);
    productRepository.getAllProducts().then(all => {
      const p = all.find(item => item.slug === slug || item.id === slug) || null;
      if (p) {
        setProduct(p);
        setSelectedImage(p.images[0] || p.thumbnail);
        if (p.variants.length > 0) {
          const firstInStock = p.variants.find(v => v.available === true) || p.variants[0];
          setSelectedSize(firstInStock.size);
          setSelectedColour(firstInStock.colourName);
        }
      }
      setRelatedProducts(all.filter(item => item.id !== p?.id).slice(0, 4));
      setLoading(false);
    });
  }, [slug]);

  if (loading) {
    return <div className="max-w-7xl mx-auto p-12 text-center text-neutral-500">Loading Vibe4You Product...</div>;
  }

  if (!product) {
    return (
      <div className="max-w-7xl mx-auto p-12 text-center space-y-4">
        <h2 className="text-2xl font-black">Product Not Found</h2>
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

  const isWishlisted = isInWishlist(product.id);

  const handleAddToCart = async () => {
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
          image: product.images,
          sku: product.id,
          brand: product.brand ? { '@type': 'Brand', name: product.brand } : undefined,
          offers: {
            '@type': 'Offer',
            priceCurrency: 'INR',
            price: product.price,
            availability: product.variants.some(variant => variant.available === true)
              ? 'https://schema.org/InStock'
              : 'https://schema.org/OutOfStock',
          },
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
          <div className="aspect-[3/4] bg-neutral-100 dark:bg-neutral-800 rounded-3xl overflow-hidden border border-neutral-200 dark:border-neutral-800 relative">
            <img
              src={selectedImage}
              alt={product.name}
              className="w-full h-full object-cover object-center"
            />
            {product.badge && (
              <span className="absolute top-4 left-4 bg-neutral-950 text-white dark:bg-lime-400 dark:text-neutral-950 text-xs font-black px-3 py-1 rounded-full shadow">
                {product.badge}
              </span>
            )}
          </div>

          <div className="flex gap-3 overflow-x-auto no-scrollbar">
            {product.images.map((img, idx) => (
              <button
                key={idx}
                onClick={() => setSelectedImage(img)}
                className={`w-20 aspect-[3/4] rounded-xl overflow-hidden border-2 transition-all ${
                  selectedImage === img ? 'border-lime-500 scale-105 shadow-md' : 'border-transparent opacity-70'
                }`}
              >
                <img src={img} alt={`${product.name} ${idx}`} className="w-full h-full object-cover" />
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
            <span className="text-3xl font-black text-neutral-900 dark:text-white">â‚¹{selectedVariant?.price ?? product.price}</span>
            {product.originalPrice > product.price && (
              <>
                <span className="text-sm text-neutral-400 line-through">â‚¹{product.originalPrice}</span>
                <span className="text-xs font-black text-rose-500 bg-rose-50 dark:bg-rose-950/40 px-2 py-0.5 rounded-full">
                  {product.discount}% OFF
                </span>
              </>
            )}
            <span className="text-[10px] text-neutral-400 ml-auto">GST calculated at checkout</span>
          </div>

          {/* Variant Selector */}
          <VariantSelector
            product={product}
            selectedVariantId={selectedVariant?.id || null}
            onSelectVariant={() => {}}
            selectedSize={selectedSize}
            onSelectSize={(s) => setSelectedSize(s)}
            selectedColour={selectedColour}
            onSelectColour={(c) => setSelectedColour(c)}
            onOpenSizeGuide={() => setSizeGuideOpen(true)}
          />

          {/* Stock Status Badge */}
          {selectedVariant && (
            <div className="text-xs font-bold">
              {selectedVariant.available === true ? (
                <span className="text-emerald-600 dark:text-emerald-400 flex items-center gap-1">
                  <CheckCircle className="w-4 h-4" /> In stock in Neemuch
                </span>
              ) : (
                <span className="text-rose-600 dark:text-rose-400">Out of Stock for this variant</span>
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
              <ShoppingBag className="w-4 h-4" /> Add to StyleCart
            </button>

            <button
              onClick={handleBuyNow}
              disabled={!selectedVariant || selectedVariant.available !== true}
              className="px-8 py-4 bg-lime-400 text-neutral-950 font-black text-sm rounded-2xl shadow-xl hover:bg-lime-300 transition-all disabled:opacity-50"
            >
              Buy Now
            </button>

            <button
              onClick={() => toggleWishlist(product.id)}
              aria-label={isWishlisted ? `Remove ${product.name} from wishlist` : `Add ${product.name} to wishlist`}
              aria-pressed={isWishlisted}
              className="p-4 rounded-2xl border border-neutral-300 dark:border-neutral-700 hover:bg-neutral-100 dark:hover:bg-neutral-800"
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
            <p>Estimated delivery within <strong>60 minutes</strong> to pincode 458441.</p>
          </div>

          {/* Specifications */}
          <div className="pt-6 border-t border-neutral-200 dark:border-neutral-800 space-y-2 text-xs text-neutral-600 dark:text-neutral-400">
            <p><strong>Material:</strong> {product.material}</p>
            {product.fit && <p><strong>Fit:</strong> {product.fit}</p>}
            <p><strong>Care Instructions:</strong> {product.careInstructions.join(', ')}</p>
            <p><strong>Exchange:</strong> {product.returnWindowDays}-Day Size Exchange on eligible items; conditions and pickup charges may apply.</p>
          </div>
        </div>
      </div>

      {/* Size Guide Modal */}
      <SizeGuideModal
        isOpen={sizeGuideOpen}
        onClose={() => setSizeGuideOpen(false)}
        department={product.department}
      />

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
