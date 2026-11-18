import { describe, expect, it } from 'vitest';
import { Product } from '../types';
import {
  hasMeaningfulProductText,
  meaningfulCareInstructions,
  shouldShowSizeGuide,
  shouldShowVariantChoice,
  variantAttributeLabel,
} from '../utils/productPresentation';

const product = (overrides: Partial<Product> = {}): Product => ({
  id: 'p1', slug: 'product', name: 'Product', brand: 'Brand', department: 'unisex',
  category: 'Accessories', shortDescription: 'Short', description: 'Description',
  material: 'Not specified', careInstructions: [], price: 100, originalPrice: 100,
  discount: 0, images: ['/p.jpg'], thumbnail: '/p.jpg', rating: 0, reviewCount: 0,
  variants: [{ id: 'v1', sku: 'sku', size: 'Default', colourName: 'Default', stock: 1, available: true }],
  tags: [], returnWindowDays: 0, exchangeAvailable: false, vendorId: 'vendor', active: true,
  ...overrides,
});

describe('product presentation', () => {
  it('hides generic single variants and size guides for watches', () => {
    const watch = product();
    expect(shouldShowVariantChoice(watch)).toBe(false);
    expect(shouldShowSizeGuide(watch)).toBe(false);
    expect(variantAttributeLabel(watch)).toBe('Option');
  });

  it('uses pack/volume language for beauty products', () => {
    const shampoo = product({
      category: 'Beauty & Personal Care',
      variants: [{ id: 'v1', sku: 'sku', size: '200 ml', colourName: 'Default', stock: 1, available: true }],
    });
    expect(shouldShowVariantChoice(shampoo)).toBe(true);
    expect(shouldShowSizeGuide(shampoo)).toBe(false);
    expect(variantAttributeLabel(shampoo)).toBe('Pack / Volume');
  });

  it('keeps sizing and the size guide for footwear', () => {
    const shoe = product({
      category: 'Footwear',
      variants: [
        { id: 'v1', sku: 'sku-7', size: 'UK 7', colourName: 'Black', stock: 1, available: true },
        { id: 'v2', sku: 'sku-8', size: 'UK 8', colourName: 'Black', stock: 1, available: true },
      ],
    });
    expect(variantAttributeLabel(shoe)).toBe('Size');
    expect(shouldShowSizeGuide(shoe)).toBe(true);
  });

  it('filters blank and unknown specification values', () => {
    const item = product({ careInstructions: ['', 'N/A', 'Keep dry'] });
    expect(hasMeaningfulProductText(item.material)).toBe(false);
    expect(meaningfulCareInstructions(item)).toEqual(['Keep dry']);
  });
});
