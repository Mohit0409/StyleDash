const LOCAL_PLACE_ALIASES = new Set(['neemuch', 'nmh']);
const LOCATION_CONNECTORS = new Set(['at', 'in', 'near']);

/**
 * Removes the local place name from catalogue queries so customers searching
 * for "nmh shoes" or "shoes in Neemuch" reach the same inventory. Neemuch
 * remains the canonical public place name; NMH is only a recognized alias.
 */
export const normalizeLocalShoppingQuery = (value: string): string => {
  const tokens = value
    .trim()
    .toLocaleLowerCase()
    .split(/[^\p{L}\p{N}]+/u)
    .filter(Boolean);
  const includesPlace = tokens.some(token => LOCAL_PLACE_ALIASES.has(token));
  if (!includesPlace) return tokens.join(' ');
  return tokens
    .filter(token => !LOCAL_PLACE_ALIASES.has(token) && !LOCATION_CONNECTORS.has(token))
    .join(' ');
};
