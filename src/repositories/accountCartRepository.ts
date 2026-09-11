import { CartItem, Product } from '../types';
import { accountStateApi, SavedCartLine } from '../services/accountStateApi';
import { productRepository } from './productRepository';

export const LOCAL_CART_KEY = 'sd_cart_v2';

const validQuantity = (value: unknown): number | null =>
  Number.isInteger(value) && Number(value) >= 1 && Number(value) <= 50
    ? Number(value)
    : null;

export const compactCart = (items: CartItem[]): SavedCartLine[] =>
  items.map(item => ({
    productId: item.productId,
    variantId: item.variantId,
    quantity: item.quantity,
  }));

export const readLegacyLocalCart = (): SavedCartLine[] => {
  const saved = localStorage.getItem(LOCAL_CART_KEY);
  if (!saved) return [];
  try {
    const parsed = JSON.parse(saved);
    if (!Array.isArray(parsed)) return [];
    return parsed.flatMap(item => {
      if (!item || typeof item !== 'object') return [];
      const productId = typeof item.productId === 'string' ? item.productId : '';
      const variantId = typeof item.variantId === 'string' ? item.variantId : '';
      const quantity = validQuantity(item.quantity);
      return productId && variantId && quantity
        ? [{ productId, variantId, quantity }]
        : [];
    });
  } catch {
    return [];
  }
};

export const mergeSavedCart = (
  serverItems: SavedCartLine[],
  localItems: SavedCartLine[],
): SavedCartLine[] => {
  const merged = new Map<string, SavedCartLine>();
  for (const source of [...serverItems, ...localItems]) {
    const quantity = validQuantity(source.quantity);
    if (!source.productId || !source.variantId || !quantity) continue;
    const existing = merged.get(source.variantId);
    merged.set(source.variantId, {
      productId: source.productId,
      variantId: source.variantId,
      quantity: Math.max(existing?.quantity ?? 0, quantity),
    });
  }
  return [...merged.values()].slice(0, 50);
};

const hydrateLine = (line: SavedCartLine, products: Map<string, Product>): CartItem | null => {
  const product = products.get(line.productId);
  if (!product || product.active === false) return null;
  const variant = product.variants.find(candidate => candidate.id === line.variantId);
  const quantity = validQuantity(line.quantity);
  if (!variant || !quantity) return null;
  return {
    lineId: `${product.id}:${variant.id}`,
    productId: product.id,
    product,
    variantId: variant.id,
    selectedSize: variant.size,
    selectedColour: variant.colourName,
    sku: variant.sku,
    quantity,
    unitPrice: variant.price ?? product.price,
  };
};

export const hydrateSavedCart = async (lines: SavedCartLine[]): Promise<CartItem[]> => {
  const products = await productRepository.getAllProducts();
  const byId = new Map(products.map(product => [product.id, product]));
  return lines.flatMap(line => {
    const item = hydrateLine(line, byId);
    return item ? [item] : [];
  });
};

export const accountCartRepository = {
  async loadAndMigrate(): Promise<CartItem[]> {
    const state = await accountStateApi.get();
    const legacy = readLegacyLocalCart();
    const merged = mergeSavedCart(state.cart, legacy);
    if (legacy.length > 0) {
      await accountStateApi.saveCart(merged);
      localStorage.removeItem(LOCAL_CART_KEY);
    }
    return hydrateSavedCart(merged);
  },
  async save(items: CartItem[]): Promise<void> {
    await accountStateApi.saveCart(compactCart(items));
  },
};
