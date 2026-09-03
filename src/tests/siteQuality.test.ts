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
    expect(deliveryAvailabilityMessage(saturday)).toContain('Express Local Delivery');
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
    expect(manifest.description).toContain('Express Local Delivery');
    expect(manifest.description).not.toMatch(/stores in minutes/i);
  });

  it('keeps exchange wording aligned with the charged-pickup policy', () => {
    const sizeGuide = readText('../components/SizeGuideModal.tsx');
    expect(sizeGuide).not.toContain('free of cost');
    expect(sizeGuide).toContain('pickup/exchange charges may apply');
  });
});
