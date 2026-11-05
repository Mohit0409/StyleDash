/**
 * Keep only public catalogue identifiers in the URL; this survives refresh
 * and sign-in redirects without exposing any customer address information.
 */
export interface DeliveryRequestSelection {
  product: string;
  variant: string;
  quantity: number;
}

export const deliveryRequestHref = (product: string, variant: string, quantity: number): string => {
  const params = new URLSearchParams({ product, variant, qty: String(quantity) });
  return '/delivery-requests?' + params.toString();
};

export const parseDeliveryRequestSelection = (search: string): DeliveryRequestSelection | null => {
  const params = new URLSearchParams(search);
  const product = params.get('product')?.trim() ?? '';
  const variant = params.get('variant')?.trim() ?? '';
  const rawQuantity = params.get('qty') ?? '';
  const quantity = Number(rawQuantity);
  if (!product || !variant || product.length > 200 || variant.length > 200) return null;
  if (!/^[1-9][0-9]*$/.test(rawQuantity)) return null;
  if (!Number.isSafeInteger(quantity) || quantity > 99) return null;
  return { product, variant, quantity };
};
