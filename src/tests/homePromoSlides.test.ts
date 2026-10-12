import { describe, expect, it } from 'vitest';
import { HOME_PROMO_SLIDES } from '../data/homePromoSlides';

describe('Vibe4You homepage promotional cards', () => {
  it('has unique cards and valid category destinations', () => {
    expect(HOME_PROMO_SLIDES).toHaveLength(6);
    expect(new Set(HOME_PROMO_SLIDES.map(slide => slide.id)).size).toBe(HOME_PROMO_SLIDES.length);
    for (const slide of HOME_PROMO_SLIDES) {
      expect(slide.title.trim()).not.toBe('');
      expect(slide.eyebrow.trim()).not.toBe('');
      expect(slide.imageUrl).toMatch(/^https:\/\/images\.unsplash\.com\/photo-/);
      expect(slide.targetUrl).toMatch(/^\/(products|stores|categories|offers)(\?|$)/);
      expect(slide.targetUrl).not.toContain('//');
    }
  });

  it('only claims evergreen categories and existing budget filters', () => {
    const targets = HOME_PROMO_SLIDES.map(slide => slide.targetUrl);
    expect(targets).toContain('/categories');
    expect(targets).toContain('/offers');
    expect(targets).toContain('/stores?sort=newest');
    expect(targets).toContain('/products?maxPrice=499');
    expect(HOME_PROMO_SLIDES.map(slide => [slide.title, slide.subtitle].join(' ')).join(' ')).not.toMatch(/\d+% off|sale ends|free delivery/i);
  });
});
