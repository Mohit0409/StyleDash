import React from 'react';
import { Product, ProductVariant } from '../types';

interface VariantSelectorProps {
  product: Product;
  selectedVariantId: string | null;
  onSelectVariant: (variantId: string) => void;
  selectedSize: string | null;
  onSelectSize: (size: string) => void;
  selectedColour: string | null;
  onSelectColour: (colour: string) => void;
  onOpenSizeGuide?: () => void;
}

export const VariantSelector: React.FC<VariantSelectorProps> = ({
  product,
  selectedSize,
  onSelectSize,
  selectedColour,
  onSelectColour,
  onOpenSizeGuide
}) => {
  const colours = Array.from(new Set(product.variants.map(v => v.colourName)));
  const sizes = Array.from(new Set(product.variants.map(v => v.size)));

  return (
    <div className="space-y-5">
      {/* Colour Selection */}
      <div>
        <label className="block text-xs font-bold text-neutral-700 dark:text-neutral-300 uppercase tracking-wider mb-2">
          Select Colour: <span className="text-lime-600 dark:text-lime-400 font-black">{selectedColour || 'Choose one'}</span>
        </label>
        <div className="flex flex-wrap gap-2.5">
          {colours.map(cName => {
            const variantForColour = product.variants.find(v => v.colourName === cName);
            const isSelected = selectedColour === cName;

            return (
              <button
                key={cName}
                onClick={() => onSelectColour(cName)}
                className={`px-3 py-2 rounded-xl text-xs font-bold border transition-all flex items-center gap-2 ${
                  isSelected
                    ? 'border-neutral-950 dark:border-lime-400 bg-neutral-950 dark:bg-lime-400 text-white dark:text-neutral-950 shadow-md scale-105'
                    : 'border-neutral-300 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-800 text-neutral-800 dark:text-neutral-200 hover:border-neutral-400'
                }`}
              >
                {variantForColour?.colourHex && (
                  <span
                    className="w-3.5 h-3.5 rounded-full border border-black/20"
                    style={{ backgroundColor: variantForColour.colourHex }}
                  />
                )}
                <span>{cName}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Size Selection */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <label className="text-xs font-bold text-neutral-700 dark:text-neutral-300 uppercase tracking-wider">
            Select Size: <span className="text-lime-600 dark:text-lime-400 font-black">{selectedSize || 'Choose one'}</span>
          </label>
          {onOpenSizeGuide && (
            <button
              onClick={onOpenSizeGuide}
              className="text-xs text-lime-600 dark:text-lime-400 font-bold hover:underline"
            >
              Size Guide & Measurements
            </button>
          )}
        </div>

        <div className="flex flex-wrap gap-2.5">
          {sizes.map(sz => {
            // Check stock for size given selected colour
            const variantForSize = product.variants.find(
              v => v.size === sz && (!selectedColour || v.colourName === selectedColour)
            );
            const isOutOfStock = !variantForSize || variantForSize.stock <= 0;
            const isSelected = selectedSize === sz;

            return (
              <button
                key={sz}
                disabled={isOutOfStock}
                onClick={() => onSelectSize(sz)}
                className={`min-w-[48px] h-11 px-3 rounded-xl text-xs font-extrabold border transition-all relative ${
                  isOutOfStock
                    ? 'opacity-40 border-neutral-200 dark:border-neutral-800 bg-neutral-100 dark:bg-neutral-900 text-neutral-400 cursor-not-allowed line-through'
                    : isSelected
                    ? 'border-neutral-950 dark:border-lime-400 bg-neutral-950 dark:bg-lime-400 text-white dark:text-neutral-950 shadow-md scale-105'
                    : 'border-neutral-300 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-800 text-neutral-800 dark:text-neutral-200 hover:border-neutral-400'
                }`}
              >
                {sz}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
};
