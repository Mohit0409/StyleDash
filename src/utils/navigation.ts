export const safeLocalReturnPath = (value: unknown, fallback = '/profile'): string =>
  typeof value === 'string' && value.startsWith('/') && !value.startsWith('//') ? value : fallback;
