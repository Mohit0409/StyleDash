import { describe, expect, it } from 'vitest';
import { HOME_PROMO_SLIDES } from '../data/homePromoSlides';

describe('Vibe4You homepage promotional cards', () => {
  it('has unique cards and valid category destinations', () => {
    expect(HOME_PROMO_SLIDES.length).toBeGreaterThanOrEqual(4);
    expect(new Set(HOME_PROMO_SLIDES.map(slide => slide.id)).size).toBe(HOME_PROMO_SLIDES.length);
    for (const slide of HOME_PROMO_SLIDES) {
      expect(slide.title.trim()).not.toBe('');
      expect(slide.eyebrow.trim()).not.toBe('');
      expect(slide.imageUrl).toMatch(/^https:\/\/images\.unsplash\.com\/photo-/);
      expect(slide.targetUrl).toMatch(/^\/(products|stores)(\?|$)/);
      expect(slide.targetUrl).not.toContain('//');
    }
  });

  it('only claims evergreen categories and existing budget filters', () => {
    const targets = HOME_PROMO_SLIDES.map(slide => slide.targetUrl);
    expect(targets).toContain('/products?dept=men');
    expect(targets).toContain('/products?dept=women');
    expect(targets).toContain('/products?category=Footwear');
    expect(targets).toContain('/products?maxPrice=499');
    expect(HOME_PROMO_SLIDES.map(slide => [slide.title, slide.subtitle].join(' ')).join(' ')).not.toMatch(/\d+% off|sale ends|free delivery/i);
  });
});
