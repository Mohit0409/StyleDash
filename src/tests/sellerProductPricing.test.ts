import { describe, expect, it } from 'vitest';
import { toPayload, type ProductFormState } from '../components/SellerProducts';

const form = (overrides: Partial<ProductFormState> = {}): ProductFormState => ({
  name: 'Local Kurta', description: 'A locally stocked cotton kurta for testing.', brand: 'Local Loom',
  department: 'women', category: 'Clothing & Fashion', subcategory: '', deliveryType: 'normal',
  price: '500.00', originalPrice: '540.00', variants: [{ size: 'M', inventory: '2' }],
  colourName: 'Blue', colourHex: '#0000FF', imageMode: 'links',
  imageUrls: 'https://images.example.test/kurta.jpg', uploadedImageUrls: [], material: '',
  tryAtHomeEnabled: false, exchangeAvailable: false, ...overrides,
});

describe('seller product MRP validation', () => {
  it('preserves the owner-provided MRP in the submission payload', () => {
    expect(toPayload(form()).originalPricePaise).toBe(54_000);
  });

  it('requires a numeric MRP at least as high as the owner selling price', () => {
    expect(() => toPayload(form({ originalPrice: '' }))).toThrow('original/MRP price');
    expect(() => toPayload(form({ originalPrice: '499.99' }))).toThrow('original/MRP price');
  });
});
