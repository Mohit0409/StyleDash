import { describe, expect, it } from 'vitest';
import { deliveryRequestHref, parseDeliveryRequestSelection } from '../utils/deliveryRequestNavigation';

describe('outside-Neemuch delivery request page navigation', () => {
  it('preserves the exact product, variant and quantity across login and refresh', () => {
    const href = deliveryRequestHref('casio-f-91w-blue', 'v-silver/blue', 2);
    expect(href.startsWith('/delivery-requests?')).toBe(true);
    const selection = parseDeliveryRequestSelection(href.slice(href.indexOf('?')));
    expect(selection).toEqual({ product: 'casio-f-91w-blue', variant: 'v-silver/blue', quantity: 2 });
  });

  it('does not include customer contact or delivery address in the URL', () => {
    const href = deliveryRequestHref('product-1', 'variant-2', 1);
    expect(href).not.toMatch(/phone|address|street|pincode|name=/i);
  });

  it('fails closed for missing, forged or oversized selections', () => {
    expect(parseDeliveryRequestSelection('')).toBeNull();
    expect(parseDeliveryRequestSelection('?product=x&variant=y')).toBeNull();
    expect(parseDeliveryRequestSelection('?product=x&variant=y&qty=0')).toBeNull();
    expect(parseDeliveryRequestSelection('?product=x&variant=y&qty=-1')).toBeNull();
    expect(parseDeliveryRequestSelection('?product=x&variant=y&qty=1.5')).toBeNull();
    expect(parseDeliveryRequestSelection('?product=x&variant=y&qty=100')).toBeNull();
    expect(parseDeliveryRequestSelection('?product=' + 'x'.repeat(201) + '&variant=y&qty=1')).toBeNull();
  });
});
