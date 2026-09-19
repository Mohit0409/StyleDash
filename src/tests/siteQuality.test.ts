import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { BANNERS } from '../data/banners';
import { deliveryAvailabilityMessage, expressCatalogueState, isExpressDeliveryAvailable } from '../utils/delivery';

const readText = (relativePath: string) => readFileSync(new URL(relativePath, import.meta.url), 'utf8');

describe('site quality guardrails', () => {
  it('keeps express delivery weekend-only in India time', () => {
    const saturday = new Date('2026-08-29T06:00:00Z');
    const monday = new Date('2026-08-31T06:00:00Z');
    expect(isExpressDeliveryAvailable(saturday)).toBe(true);
    expect(isExpressDeliveryAvailable(monday)).toBe(false);
    expect(deliveryAvailabilityMessage(saturday)).toContain('Express Delivery');
    expect(deliveryAvailabilityMessage(monday)).toContain('unavailable Monday');
  });


  it('keeps catalogue brand and size facets data-driven', () => {
    const sidebar = readText('../components/FilterSidebar.tsx');
    expect(sidebar).toContain("['all', ...brands]");
    expect(sidebar).toContain("['all', ...sizes]");
    expect(sidebar).not.toContain("'Roadster', 'HRX'");
    expect(sidebar).not.toContain("'UK 6', 'UK 7', 'UK 8', 'UK 9'");
  });

  it('does not advertise a nonexistent express route or generic minute delivery in install metadata', () => {
    expect(BANNERS.some(banner => banner.targetUrl === '/express')).toBe(false);
    expect(BANNERS[0].title).not.toContain(' ? ');
    const manifest = JSON.parse(readText('../../public/manifest.json')) as { description: string };
    expect(manifest.description).toContain('Express Delivery');
    expect(manifest.description).not.toMatch(/stores in minutes/i);
  });

  it('keeps exchange wording aligned with the charged-pickup policy', () => {
    const sizeGuide = readText('../components/SizeGuideModal.tsx');
    expect(sizeGuide).not.toContain('free of cost');
    expect(sizeGuide).toContain('pickup/exchange charges may apply');
  });

  it('keeps separate women and men/unisex footwear guidance visible', () => {
    const sizeGuide = readText('../components/SizeGuideModal.tsx');
    expect(sizeGuide).toContain('Men / Unisex');
    expect(sizeGuide).toContain('>Women</button>');
    expect(sizeGuide).toContain("footwearAudience === 'women'");
    expect(sizeGuide).toContain('Brand and seller-specific sizing can vary');
  });

  it('does not make an unsupported size-exchange promise in the homepage trust strip', () => {
    const home = readText('../pages/Home.tsx');
    expect(home).not.toContain('Easy Size Exchange');
    expect(home).toContain('Shop by Budget');
    expect(home).toContain('/products?maxPrice=499');
  });

  it('keeps one department grid and separates Top Picks from lower curated rows', () => {
    const home = readText('../pages/Home.tsx');
    expect((home.match(/<h2[^>]*>Shop by Department<\/h2>/g) || [])).toHaveLength(1);
    expect(home).toContain('merchandisingProducts');
    expect(home).toContain('products.filter(product => !topPickIds.has(product.id))');
  });

  it('keeps customer product imagery uncropped across shopping and order surfaces', () => {
    const productCard = readText('../components/ProductCard.tsx');
    const productDetail = readText('../pages/ProductDetail.tsx');
    const cartDrawer = readText('../components/CartDrawer.tsx');
    const orders = readText('../pages/Orders.tsx');
    const orderTracking = readText('../pages/OrderTracking.tsx');

    for (const source of [productCard, productDetail, cartDrawer, orders, orderTracking]) {
      expect(source).toContain('object-contain');
    }
    expect(cartDrawer).not.toContain('object-cover');
    expect(orders).not.toContain('object-cover');
    expect(orderTracking).not.toContain('object-cover');
  });

  it('keeps delivery fee amounts at checkout instead of marketing surfaces', () => {
    const checkout = readText('../pages/Checkout.tsx');
    const marketingSources = [
      readText('../components/SEO.tsx'),
      readText('../pages/ProductDetail.tsx'),
      readText('../pages/Products.tsx'),
      readText('../pages/Stores.tsx'),
      readText('../utils/delivery.ts'),
      readText('../utils/homeMerchandising.ts'),
    ];

    expect(checkout).toContain('₹50 for orders below ₹300');
    expect(checkout).toContain('FREE on orders of ₹300+');
    for (const source of marketingSources) {
      expect(source).not.toMatch(/Same Day Delivery[^'\n<]*₹/i);
      expect(source).not.toMatch(/Express Delivery[^'\n<]*₹/i);
      expect(source).not.toContain('below ₹300');
      expect(source).not.toContain('free from ₹300');
    }
  });
});
