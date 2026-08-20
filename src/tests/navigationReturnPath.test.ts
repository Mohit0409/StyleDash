import { describe, expect, it } from 'vitest';
import { safeLocalReturnPath } from '../utils/navigation';

describe('authenticated return paths', () => {
  it('preserves local paths including query strings and fragments', () => {
    expect(safeLocalReturnPath('/partner?entry=header#application')).toBe('/partner?entry=header#application');
  });

  it.each([
    'https://attacker.example/path',
    '//attacker.example/path',
    'partner',
    null,
    undefined,
  ])('rejects a non-local return path (%s)', value => {
    expect(safeLocalReturnPath(value)).toBe('/profile');
  });
});
