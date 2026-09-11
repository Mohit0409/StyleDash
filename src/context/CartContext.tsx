import React, { createContext, useContext, useEffect, useRef, useState } from 'react';
import { Product, CartItem, Coupon } from '../types';
import { trackEvent } from '../services/analytics';
import { calculateCartTotals } from './cartTotals';
import { canAddVariantToCart, canIncreaseCartQuantity } from '../repositories/inventoryRepository';
import { cartExpressEligibility, isExpressDeliveryAvailable } from '../utils/delivery';
import { accountCartRepository, LOCAL_CART_KEY } from '../repositories/accountCartRepository';
import { useAuth } from './AuthContext';

interface CartContextType {
  items: CartItem[];
  addItem: (product: Product, variantId: string, quantity?: number) => Promise<boolean>;
  removeItem: (lineId: string) => void;
  updateQuantity: (lineId: string, quantity: number) => Promise<void>;
  clearCart: () => void;
  appliedCoupon: Coupon | null;
  applyCoupon: (coupon: Coupon) => void;
  removeCoupon: () => void;
  subtotal: number;
  discountTotal: number;
  couponDiscount: number;
  deliveryFee: number;
  taxes: number;
  grandTotal: number;
  totalItemsCount: number;
  deliveryMethod: 'express' | 'standard';
  setDeliveryMethod: (method: 'express' | 'standard') => void;
}

const CartContext = createContext<CartContextType | undefined>(undefined);

const cartSignature = (cartItems: CartItem[]): string => JSON.stringify(
  cartItems.map(item => ({ productId: item.productId, variantId: item.variantId, quantity: item.quantity })),
);

const readGuestCart = (): CartItem[] => {
  const saved = localStorage.getItem(LOCAL_CART_KEY);
  if (!saved) return [];
  try {
    const parsed = JSON.parse(saved);
    return Array.isArray(parsed)
      ? parsed.filter(item => item && typeof item === 'object' && typeof item.productId === 'string' && typeof item.variantId === 'string')
      : [];
  } catch {
    return [];
  }
};

export const CartProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user, loading: authLoading } = useAuth();
  const userId = user?.uid ?? 'guest';
  const [items, setItems] = useState<CartItem[]>(readGuestCart);
  const [appliedCoupon, setAppliedCoupon] = useState<Coupon | null>(null);
  const [deliveryMethod, setDeliveryMethodState] = useState<'express' | 'standard'>('standard');
  const ownerRef = useRef('guest');
  const hydratedRef = useRef(false);
  const hydrationPromiseRef = useRef<Promise<void>>(Promise.resolve());
  const saveQueueRef = useRef<Promise<void>>(Promise.resolve());
  const serverCartSignatureRef = useRef('');
  const expressCart = cartExpressEligibility(items.map(item => item.product));

  const setDeliveryMethod = (method: 'express' | 'standard') => {
    const expressAllowed = isExpressDeliveryAvailable() && expressCart.eligible;
    setDeliveryMethodState(method === 'express' && !expressAllowed ? 'standard' : method);
  };

  useEffect(() => {
    if (deliveryMethod === 'express' && (!isExpressDeliveryAvailable() || !expressCart.eligible)) {
      setDeliveryMethodState('standard');
    }
  }, [deliveryMethod, expressCart.eligible]);

  useEffect(() => {
    if (authLoading) return;
    let cancelled = false;
    hydratedRef.current = false;
    ownerRef.current = `loading:${userId}`;
    serverCartSignatureRef.current = '';

    if (userId === 'guest') {
      setItems(readGuestCart());
      ownerRef.current = 'guest';
      hydratedRef.current = true;
      hydrationPromiseRef.current = Promise.resolve();
      return;
    }

    setItems([]);
    const hydrate = accountCartRepository.loadAndMigrate()
      .then(nextItems => {
        if (cancelled) return;
        ownerRef.current = userId;
        hydratedRef.current = true;
        serverCartSignatureRef.current = cartSignature(nextItems);
        setItems(nextItems);
      })
      .catch(() => {
        if (cancelled) return;
        ownerRef.current = `unavailable:${userId}`;
        hydratedRef.current = false;
        setItems([]);
      });
    hydrationPromiseRef.current = hydrate.then(() => undefined);

    return () => { cancelled = true; };
  }, [authLoading, userId]);

  useEffect(() => {
    if (authLoading || !hydratedRef.current || ownerRef.current !== userId) return;
    if (userId === 'guest') {
      localStorage.setItem(LOCAL_CART_KEY, JSON.stringify(items));
      return;
    }
    const owner = userId;
    const snapshot = [...items];
    const signature = cartSignature(snapshot);
    if (signature === serverCartSignatureRef.current) return;
    saveQueueRef.current = saveQueueRef.current.catch(() => undefined).then(async () => {
      if (!hydratedRef.current || ownerRef.current !== owner) return;
      if (signature === serverCartSignatureRef.current) return;
      await accountCartRepository.save(snapshot);
      if (ownerRef.current === owner) serverCartSignatureRef.current = signature;
    });
  }, [authLoading, items, userId]);

  useEffect(() => {
    if (authLoading || userId === 'guest') return;
    const refresh = () => {
      const owner = userId;
      saveQueueRef.current = saveQueueRef.current.catch(() => undefined).then(async () => {
        if (!hydratedRef.current || ownerRef.current !== owner) return;
        try {
          const nextItems = await accountCartRepository.loadAndMigrate();
          if (ownerRef.current === owner) {
            serverCartSignatureRef.current = cartSignature(nextItems);
            setItems(nextItems);
          }
        } catch { /* Keep the last known account cart if refresh fails. */ }
      });
    };
    const onVisibility = () => { if (document.visibilityState === 'visible') refresh(); };
    window.addEventListener('focus', refresh);
    document.addEventListener('visibilitychange', onVisibility);
    return () => {
      window.removeEventListener('focus', refresh);
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, [authLoading, userId]);

  const addItem = async (product: Product, variantId: string, quantity = 1): Promise<boolean> => {
    await hydrationPromiseRef.current;
    if (userId !== 'guest' && (!hydratedRef.current || ownerRef.current !== userId)) return false;
    const variant = product.variants.find(v => v.id === variantId);
    if (!variant) return false;
    if (!await canAddVariantToCart(variantId)) return false;

    const lineId = `${product.id}:${variantId}`;
    setItems(prev => {
      const existingIdx = prev.findIndex(item => item.lineId === lineId);
      if (existingIdx >= 0) {
        const existing = prev[existingIdx];
        const updated = [...prev];
        updated[existingIdx] = { ...existing, quantity: existing.quantity + quantity };
        return updated;
      }
      return [...prev, {
        lineId, productId: product.id, product, variantId: variant.id,
        selectedSize: variant.size, selectedColour: variant.colourName,
        sku: variant.sku, quantity, unitPrice: variant.price ?? product.price,
      }];
    });

    trackEvent('add_to_cart', {
      item_id: product.id,
      item_name: product.name,
      item_category: product.category,
      variant_id: variantId,
      size: variant.size,
      colour: variant.colourName,
      price: variant.price ?? product.price,
      quantity,
    });
    return true;
  };

  const removeItem = (lineId: string) => {
    setItems(prev => {
      const item = prev.find(candidate => candidate.lineId === lineId);
      if (item) {
        trackEvent('remove_from_cart', {
          item_id: item.productId,
          line_id: lineId,
          quantity: item.quantity,
        });
      }
      return prev.filter(candidate => candidate.lineId !== lineId);
    });
  };

  const updateQuantity = async (lineId: string, quantity: number): Promise<void> => {
    await hydrationPromiseRef.current;
    if (userId !== 'guest' && (!hydratedRef.current || ownerRef.current !== userId)) return;
    if (quantity <= 0) {
      removeItem(lineId);
      return;
    }
    const currentItem = items.find(item => item.lineId === lineId);
    if (!currentItem) return;
    if (quantity > currentItem.quantity && !await canIncreaseCartQuantity(currentItem.variantId)) return;
    setItems(prev => prev.map(item =>
      item.lineId === lineId ? { ...item, quantity } : item,
    ));
  };

  const clearCart = () => {
    setItems([]);
    setAppliedCoupon(null);
    setDeliveryMethodState('standard');
    if (userId === 'guest') localStorage.removeItem(LOCAL_CART_KEY);
  };

  const applyCoupon = (coupon: Coupon) => {
    setAppliedCoupon(coupon);
    trackEvent('select_promotion', { promotion_id: coupon.code });
  };
  const removeCoupon = () => setAppliedCoupon(null);

  const subtotal = items.reduce((acc, item) => acc + item.unitPrice * item.quantity, 0);
  const totalItemsCount = items.reduce((acc, item) => acc + item.quantity, 0);
  const { couponDiscount, discountTotal, deliveryFee, taxes, grandTotal } = calculateCartTotals({
    subtotal,
    appliedCoupon,
    deliveryMethod,
  });

  return (
    <CartContext.Provider value={{
      items,
      addItem,
      removeItem,
      updateQuantity,
      clearCart,
      appliedCoupon,
      applyCoupon,
      removeCoupon,
      subtotal,
      discountTotal,
      couponDiscount,
      deliveryFee,
      taxes,
      grandTotal,
      totalItemsCount,
      deliveryMethod,
      setDeliveryMethod,
    }}>
      {children}
    </CartContext.Provider>
  );
};

export const useCart = () => {
  const context = useContext(CartContext);
  if (!context) throw new Error('useCart must be used within CartProvider');
  return context;
};
