import React, { createContext, useContext, useState, useEffect } from 'react';
import { Product, CartItem, Coupon } from '../types';
import { trackEvent } from '../services/analytics';
import { CONFIG } from '../config';

interface CartContextType {
  items: CartItem[];
  addItem: (product: Product, variantId: string, quantity?: number) => boolean;
  removeItem: (lineId: string) => void;
  updateQuantity: (lineId: string, quantity: number) => void;
  clearCart: () => void;
  appliedCoupon: Coupon | null;
  applyCoupon: (coupon: Coupon) => void;
  removeCoupon: () => void;
  walletDiscount: number;
  applyWalletCredit: (amount: number) => void;
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
  const [walletDiscount, setWalletDiscount] = useState<number>(0);
  const [deliveryMethod, setDeliveryMethod] = useState<'express' | 'standard'>('express');

  useEffect(() => {
    localStorage.setItem(LOCAL_CART_KEY, JSON.stringify(items));
  }, [items]);

  const addItem = (product: Product, variantId: string, quantity = 1): boolean => {
    const variant = product.variants.find(v => v.id === variantId);
    if (!variant) return false;

    if (variant.stock <= 0) {
      return false;
    }

    const lineId = `${product.id}:${variantId}`;

    setItems(prev => {
      const existingIdx = prev.findIndex(item => item.lineId === lineId);
      if (existingIdx >= 0) {
        const existing = prev[existingIdx];
        const newQty = Math.min(existing.quantity + quantity, variant.stock);
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
          quantity: Math.min(quantity, variant.stock),
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

  const updateQuantity = (lineId: string, quantity: number) => {
    if (quantity <= 0) {
      removeItem(lineId);
      return;
    }
    setItems(prev => {
      return prev.map(item => {
        if (item.lineId === lineId) {
          const variant = item.product.variants.find(v => v.id === item.variantId);
          const maxStock = variant ? variant.stock : item.quantity;
          return { ...item, quantity: Math.min(quantity, maxStock) };
        }
        return item;
      });
    });
  };

  const clearCart = () => {
    setItems([]);
    setAppliedCoupon(null);
    setWalletDiscount(0);
    localStorage.removeItem(LOCAL_CART_KEY);
  };

  const applyCoupon = (coupon: Coupon) => {
    setAppliedCoupon(coupon);
    trackEvent('select_promotion', { promotion_id: coupon.code });
  };

  const removeCoupon = () => {
    setAppliedCoupon(null);
  };

  const applyWalletCredit = (amount: number) => {
    setWalletDiscount(amount);
  };

  const subtotal = items.reduce((acc, item) => acc + item.unitPrice * item.quantity, 0);
  const totalItemsCount = items.reduce((acc, item) => acc + item.quantity, 0);

  let couponDiscount = 0;
  if (appliedCoupon && subtotal >= appliedCoupon.minOrderValue) {
    if (appliedCoupon.discountType === 'fixed') {
      couponDiscount = appliedCoupon.value;
    } else {
      couponDiscount = (subtotal * appliedCoupon.value) / 100;
      if (appliedCoupon.maxDiscount) {
        couponDiscount = Math.min(couponDiscount, appliedCoupon.maxDiscount);
      }
    }
  }

  const isFreeDelivery = subtotal >= CONFIG.FREE_DELIVERY_THRESHOLD;
  const baseDeliveryFee = deliveryMethod === 'express' ? CONFIG.EXPRESS_DELIVERY_FEE : CONFIG.STANDARD_DELIVERY_FEE;
  const deliveryFee = isFreeDelivery ? 0 : baseDeliveryFee;

  const taxes = Math.round((subtotal - couponDiscount) * CONFIG.TAX_RATE);
  const discountTotal = couponDiscount + walletDiscount;
  const grandTotal = Math.max(0, subtotal - discountTotal + deliveryFee + taxes);

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
      walletDiscount,
      applyWalletCredit,
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
