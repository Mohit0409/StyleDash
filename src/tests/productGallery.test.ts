import { describe, expect, it } from 'vitest';
import { productGalleryImages } from '../utils/productGallery';

describe('productGalleryImages', () => {
  it('uses product images when a variant has no image gallery', () => {
    expect(productGalleryImages(['/primary.webp', '/secondary.jpg'], [])).toEqual([
      '/primary.webp',
      '/secondary.jpg',
    ]);
  });

  it('exposes product secondary images when the variant only inherited the primary', () => {
    expect(productGalleryImages(
      ['/primary.webp', '/secondary.jpg'],
      ['/primary.webp'],
    )).toEqual(['/primary.webp', '/secondary.jpg']);
  });

  it('keeps a genuinely colour-specific variant image isolated', () => {
    expect(productGalleryImages(
      ['/default.webp', '/default-secondary.jpg'],
      ['/blue.webp'],
    )).toEqual(['/blue.webp']);
  });

  it('keeps a variant-owned multi-image gallery isolated', () => {
    expect(productGalleryImages(
      ['/default.webp', '/default-secondary.jpg'],
      ['/blue-front.webp', '/blue-side.webp'],
    )).toEqual(['/blue-front.webp', '/blue-side.webp']);
  });
});
