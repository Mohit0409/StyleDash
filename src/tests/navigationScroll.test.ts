import { describe, expect, it } from 'vitest';
import { decodeNavigationFragment } from '../components/NavigationScrollPolicy';

describe('navigation fragment decoding', () => {
  it('decodes valid fragments used by same-page anchors', () => {
    expect(decodeNavigationFragment('#returns%20policy')).toBe('returns policy');
  });

  it('fails safely for malformed URI fragments', () => {
    expect(decodeNavigationFragment('#%E0%A4%A')).toBe('');
  });
});
