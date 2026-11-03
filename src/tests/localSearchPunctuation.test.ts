import { describe, expect, it } from 'vitest';
import { normalizeLocalShoppingQuery } from '../utils/localSearch';

describe('local catalogue search and model punctuation', () => {
  it('preserves exact product-model punctuation', () => {
    expect(normalizeLocalShoppingQuery('Casio F-91W')).toBe('casio f-91w');
    expect(normalizeLocalShoppingQuery('facet-scope')).toBe('facet-scope');
    expect(normalizeLocalShoppingQuery('F-91WF-1A')).toBe('f-91wf-1a');
  });

  it('removes only explicit Neemuch/NMH place tokens and preceding connectors', () => {
    expect(normalizeLocalShoppingQuery('Casio F-91W in Neemuch')).toBe('casio f-91w');
    expect(normalizeLocalShoppingQuery('nmh shoes')).toBe('shoes');
    expect(normalizeLocalShoppingQuery('Lavie bags near Neemuch')).toBe('lavie bags');
  });

  it('keeps unknown place names and does not strip locality inside a brand', () => {
    expect(normalizeLocalShoppingQuery('Munger shoes')).toBe('munger shoes');
    expect(normalizeLocalShoppingQuery('MyNeemuchBrand')).toBe('myneemuchbrand');
  });
});
