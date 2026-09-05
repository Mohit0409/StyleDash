import React, { createContext, useContext, useState, useEffect } from 'react';
import { Product, CartItem, Coupon } from '../types';
import { trackEvent } from '../services/analytics';
import { calculateCartTotals } from './cartTotals';
import { canAddVariantToCart, canIncreaseCartQuantity } from '../repositories/inventoryRepository';
import { cartExpressEligibility, isExpressDeliveryAvailable } from '../utils/delivery';

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

const LOCAL_CART_KEY = 'sd_cart_v2';

export const CartProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [items, setItems] = useState<CartItem[]>(() => {
    const saved = localStorage.getItem(LOCAL_CART_KEY);
    if (saved) {
      try { return JSON.parse(saved); } catch { /* Ignore malformed local cart data. */ }
    }
    return [];
  });

  const [appliedCoupon, setAppliedCoupon] = useState<Coupon | null>(null);
  const [deliveryMethod, setDeliveryMethodState] = useState<'express' | 'standard'>('standard');
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
    localStorage.setItem(LOCAL_CART_KEY, JSON.stringify(items));
  }, [items]);

  const addItem = async (product: Product, variantId: string, quantity = 1): Promise<boolean> => {
    const variant = product.variants.find(v => v.id === variantId);
    if (!variant) return false;

    if (!await canAddVariantToCart(variantId)) return false;

    const lineId = `${product.id}:${variantId}`;

    setItems(prev => {
      const existingIdx = prev.findIndex(item => item.lineId === lineId);
      if (existingIdx >= 0) {
        const existing = prev[existingIdx];
        const newQty = existing.quantity + quantity;
        const updated = [...prev];
        updated[existingIdx] = { ...existing, quantity: newQty };
        return updated;
      } else {
        const unitPrice = variant.price ?? product.price;
        const newItem: CartItem = {
          lineId,
          productId: product.id,
          product,
          variantId: variant.id,
          selectedSize: variant.size,
          selectedColour: variant.colourName,
          sku: variant.sku,
          quantity,
          unitPrice
        };
        return [...prev, newItem];
      }
    });

    trackEvent('add_to_cart', {
      item_id: product.id,
      item_name: product.name,
      item_category: product.category,
      variant_id: variantId,
      size: variant.size,
      colour: variant.colourName,
      price: variant.price ?? product.price,
      quantity
    });

    return true;
  };

  const removeItem = (lineId: string) => {
    setItems(prev => {
      const item = prev.find(i => i.lineId === lineId);
      if (item) {
        trackEvent('remove_from_cart', {
          item_id: item.productId,
          line_id: lineId,
          quantity: item.quantity
        });
      }
      return prev.filter(i => i.lineId !== lineId);
    });
  };

  const updateQuantity = async (lineId: string, quantity: number): Promise<void> => {
    if (quantity <= 0) {
      removeItem(lineId);
      return;
    }
    const currentItem = items.find(item => item.lineId === lineId);
    if (!currentItem) return;
    if (quantity > currentItem.quantity && !await canIncreaseCartQuantity(currentItem.variantId)) return;

    setItems(prev => {
      return prev.map(item => {
        if (item.lineId === lineId) {
          return { ...item, quantity };
        }
        return item;
      });
    });
  };

  const clearCart = () => {
    setItems([]);
    setAppliedCoupon(null);
    setDeliveryMethodState('standard');
    localStorage.removeItem(LOCAL_CART_KEY);
  };

  const applyCoupon = (coupon: Coupon) => {
    setAppliedCoupon(coupon);
    trackEvent('select_promotion', { promotion_id: coupon.code });
  };

  const removeCoupon = () => {
    setAppliedCoupon(null);
  };

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
      setDeliveryMethod
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
