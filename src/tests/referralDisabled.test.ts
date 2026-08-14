import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const source = (path: string) => readFileSync(resolve(path), 'utf8');

describe('disabled referral and wallet flows', () => {
  it('leaves the referral URL to the normal not-found route', () => {
    const app = source('src/App.tsx');

    expect(app).not.toMatch(/path=["']referrals["']/);
    expect(app).not.toContain('ReferralProvider');
    expect(app).toMatch(/<Route path=["']\*["'] element={<NotFound \/>} \/>/);
    expect(existsSync(resolve('src/pages/Referrals.tsx'))).toBe(false);
    expect(existsSync(resolve('src/context/ReferralContext.tsx'))).toBe(false);
  });

  it('contains no active referral or wallet marketing', () => {
    const customerSources = [
      'src/App.tsx',
      'src/pages/Home.tsx',
      'src/components/Footer.tsx',
      'src/context/CartContext.tsx',
      'src/pages/Checkout.tsx',
    ].map(source).join('\n');
    const staleClaims = [
      'Refer & Earn',
      'Give ₹100',
      'Get ₹100',
      'StyleWallet',
      'Auto-applies',
      'Referral Reward',
    ];

    for (const claim of staleClaims) expect(customerSources).not.toContain(claim);
  });

  it('keeps wallet credit out of the active checkout intent contract', () => {
    const paymentApi = source('src/services/paymentApi.ts');
    const checkoutIntent = paymentApi.match(/export interface CheckoutIntent \{[\s\S]*?\n\}/)?.[0];

    expect(checkoutIntent).toBeDefined();
    expect(checkoutIntent).not.toContain('walletAmount');
    expect(source('src/pages/Checkout.tsx')).not.toContain('walletAmount');
  });
});
