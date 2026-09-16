import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

const readText = (relativePath: string) => readFileSync(new URL(relativePath, import.meta.url), 'utf8');

describe('production ordering availability', () => {
  it('does not let a browser build flag disable an otherwise available checkout', () => {
    const config = readText('../config/index.ts');
    const checkout = readText('../pages/Checkout.tsx');

    expect(config).not.toContain('VITE_ORDERING_ENABLED');
    expect(checkout).not.toContain('CONFIG.ORDERING_ENABLED');
    expect(checkout).toContain('disabled={placing}');
    expect(checkout).toContain("'Place COD Order'");
  });

  it('does not retain obsolete launch or maintenance copy on customer checkout surfaces', () => {
    const obsoleteCopy = /Ordering and payments are temporarily unavailable|Ordering Opens at Launch|prepares for launch|Launching Soon/i;
    const customerSurfaces = [
      '../pages/Home.tsx',
      '../pages/ProductDetail.tsx',
      '../components/CartDrawer.tsx',
      '../pages/Checkout.tsx',
      '../pages/Orders.tsx',
    ];

    for (const surface of customerSurfaces) {
      expect(readText(surface)).not.toMatch(obsoleteCopy);
    }
  });
});
