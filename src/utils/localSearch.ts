/**
 * Remove an explicit Neemuch/NMH location suffix or prefix without changing
 * product model punctuation (Casio F-91W), hyphenated brands or SKU tokens.
 * Punctuation is preserved when there is no location to strip.
 */
export const normalizeLocalShoppingQuery = (value: string): string => {
  const query = value.trim().toLocaleLowerCase();
  if (!query) return '';

  // Strip the locality only as a complete word, never from model identifiers.
  if (!/(?:^|[^\p{L}\p{N}])(?:neemuch|nmh)(?=$|[^\p{L}\p{N}])/u.test(query)) {
    return query;
  }

  return query
    .replace(/\b(?:in|at|near)\s+(?=(?:neemuch|nmh)\b)/gu, ' ')
    .replace(/\b(?:neemuch|nmh)\b/gu, ' ')
    .replace(/[\s,;:]+/g, ' ')
    .replace(/^[\s,;:.-]+|[\s,;:.-]+$/g, '')
    .trim();
};
