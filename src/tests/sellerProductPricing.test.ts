import { describe, expect, it } from 'vitest';
import { toPayload, type ColourFormState, type ProductFormState } from '../components/SellerProducts';

const colour = (overrides: Partial<ColourFormState> = {}): ColourFormState => ({
  colourName: 'Blue', colourHex: '#0000FF', imageMode: 'links',
  imageUrls: 'https://images.example.test/kurta.jpg', uploadedImageUrls: [],
  variants: [{ size: 'M', inventory: '2' }], ...overrides,
});

const form = (overrides: Partial<ProductFormState> = {}): ProductFormState => ({
  name: 'Local Kurta', description: 'A locally stocked cotton kurta for testing.', brand: 'Local Loom',
  department: 'women', category: 'Clothing & Fashion', subcategory: '', deliveryType: 'normal',
  price: '500.00', originalPrice: '540.00', colours: [colour()], material: '',
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

describe('seller product single-colour payload compatibility', () => {
  it('keeps the legacy variants/colourName/imageUrls payload for one colour', () => {
    const payload = toPayload(form());
    expect(payload.colourVariants).toBeUndefined();
    expect(payload.variants).toEqual([{ size: 'M', inventory: 2 }]);
    expect(payload.colourName).toBe('Blue');
    expect(payload.colourHex).toBe('#0000FF');
    expect(payload.imageUrls).toEqual(['https://images.example.test/kurta.jpg']);
  });

  it('rejects duplicate sizes within a colour', () => {
    expect(() => toPayload(form({
      colours: [colour({ variants: [{ size: 'M', inventory: '2' }, { size: 'm', inventory: '1' }] })],
    }))).toThrow('Each size can appear only once');
  });
});

describe('seller multi-colour payload', () => {
  const multiColour = (overrides: Partial<ProductFormState> = {}): ProductFormState => form({
    colours: [
      colour({ imageUrls: 'https://images.example.test/kurta-blue.jpg' }),
      colour({
        colourName: 'Red', colourHex: '#FF0000',
        imageUrls: 'https://images.example.test/kurta-red.jpg\nhttps://images.example.test/kurta-red-back.jpg',
        variants: [{ size: 'M', inventory: '3' }, { size: 'L', inventory: '1' }],
      }),
    ],
    ...overrides,
  });

  it('creates a 2-colour product in one colourVariants payload', () => {
    const payload = toPayload(multiColour());
    expect(payload.variants).toBeUndefined();
    expect(payload.colourVariants).toEqual([
      {
        colourName: 'Blue', colourHex: '#0000FF',
        imageUrls: ['https://images.example.test/kurta-blue.jpg'],
        sizes: [{ size: 'M', inventory: 2 }],
      },
      {
        colourName: 'Red', colourHex: '#FF0000',
        imageUrls: ['https://images.example.test/kurta-red.jpg', 'https://images.example.test/kurta-red-back.jpg'],
        sizes: [{ size: 'M', inventory: 3 }, { size: 'L', inventory: 1 }],
      },
    ]);
    // Legacy top-level fields mirror the first colour for older consumers.
    expect(payload.colourName).toBe('Blue');
    expect(payload.imageUrls).toEqual(['https://images.example.test/kurta-blue.jpg']);
  });

  it('rejects duplicate colour names', () => {
    expect(() => toPayload(multiColour({
      colours: [colour(), colour({ imageUrls: 'https://images.example.test/other.jpg' })],
    }))).toThrow('Each colour can appear only once');
  });

  it('allows the same size in different colours but caps total combinations', () => {
    const manySizes = Array.from({ length: 21 }, (_, index) => ({ size: `S${index}`, inventory: '1' }));
    expect(() => toPayload(form({
      colours: [
        colour({ variants: manySizes.slice(0, 11) }),
        colour({ colourName: 'Red', imageUrls: 'https://images.example.test/red.jpg', variants: manySizes.slice(0, 10) }),
      ],
    }))).toThrow('A product can have at most 20 size and colour combinations.');
  });

  it('requires each colour to carry its own images', () => {
    expect(() => toPayload(multiColour({
      colours: [colour(), colour({ colourName: 'Red', imageUrls: '' })],
    }))).toThrow('Add 1-8 direct HTTPS image links for Red');
  });

  it('caps total stock across all colours at 100000', () => {
    expect(() => toPayload(form({
      colours: [
        colour({ variants: [{ size: 'M', inventory: '60000' }] }),
        colour({ colourName: 'Red', imageUrls: 'https://images.example.test/red.jpg', variants: [{ size: 'M', inventory: '40001' }] }),
      ],
    }))).toThrow('Total stock across all sizes cannot exceed 100000.');
  });
});
