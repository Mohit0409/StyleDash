import React, { useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { X, Trash2, Plus, Minus, Zap, ArrowRight, Tag, ShieldCheck } from 'lucide-react';
import { useCart } from '../context/CartContext';
import { CONFIG } from '../config';
import { deliveryAvailabilityMessage, isExpressDeliveryAvailable } from '../utils/delivery';

export const CartDrawer: React.FC<{ isOpen: boolean; onClose: () => void }> = ({ isOpen, onClose }) => {
  const navigate = useNavigate();
  const {
    items,
    removeItem,
    updateQuantity,
    subtotal,
    deliveryFee,
    taxes,
    grandTotal,
    totalItemsCount,
    deliveryMethod,
    setDeliveryMethod
  } = useCart();
  const expressAvailable = isExpressDeliveryAvailable();

  useEffect(() => {
    if (!isOpen) return undefined;
    const onKeyDown = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-sm animate-fade-in">
      <div role="dialog" aria-modal="true" aria-labelledby="cart-drawer-title" className="w-full max-w-md bg-white dark:bg-neutral-900 h-full flex flex-col shadow-2xl border-l border-neutral-200 dark:border-neutral-800">

        {/* Header */}
        <div className="p-4 sm:p-6 border-b border-neutral-200 dark:border-neutral-800 flex items-center justify-between bg-neutral-50 dark:bg-neutral-950">
          <div className="flex items-center gap-2">
            <span id="cart-drawer-title" className="font-black text-lg text-neutral-900 dark:text-white">Your Cart</span>
            <span className="bg-lime-400 text-neutral-950 font-extrabold text-xs px-2.5 py-0.5 rounded-full">
              {totalItemsCount} items
            </span>
          </div>
          <button aria-label="Close cart" onClick={onClose} className="p-2 rounded-full hover:bg-neutral-200 dark:hover:bg-neutral-800 text-neutral-500">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Free Delivery Bar */}
        <div className="bg-lime-100 dark:bg-lime-950/40 p-3 text-xs text-center font-bold text-lime-800 dark:text-lime-300 border-b border-lime-200 dark:border-lime-900 flex items-center justify-center gap-1.5">
          <Zap className="w-4 h-4 fill-lime-500 text-lime-600" />
          {subtotal >= CONFIG.FREE_DELIVERY_THRESHOLD ? (
            <span>You've unlocked <strong>FREE NORMAL DELIVERY</strong>!</span>
          ) : (
            <span>Add ₹{CONFIG.FREE_DELIVERY_THRESHOLD - subtotal} more for <strong>FREE NORMAL DELIVERY</strong></span>
          )}
        </div>

        {/* Cart Item List */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4">
          {items.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center p-8">
              <div className="w-20 h-20 bg-neutral-100 dark:bg-neutral-800 rounded-full flex items-center justify-center text-neutral-400 mb-4">
                <Tag className="w-10 h-10" />
              </div>
              <h4 className="font-bold text-lg text-neutral-900 dark:text-white mb-1">Your cart is empty</h4>
              <p className="text-xs text-neutral-500 mb-6">Local delivery is available in {CONFIG.SERVICE_CITY} ({CONFIG.DEFAULT_PINCODE}). Express Local Delivery is shown when an item is eligible.</p>
              <button
                onClick={() => { onClose(); navigate('/products'); }}
                className="px-6 py-2.5 bg-neutral-950 dark:bg-lime-400 text-white dark:text-neutral-950 font-bold text-xs rounded-xl"
              >
                Start Shopping
              </button>
            </div>
          ) : (
            items.map(item => (
              <div
                key={item.lineId}
                className="flex gap-4 p-3 bg-neutral-50 dark:bg-neutral-800/50 rounded-2xl border border-neutral-200 dark:border-neutral-800"
              >
                <img
                  src={item.product.thumbnail}
                  alt={item.product.name}
                  className="w-20 h-24 object-cover rounded-xl bg-neutral-200"
                />
                <div className="flex-1 flex flex-col justify-between">
                  <div>
                    <div className="flex justify-between items-start">
                      <div>
                        {item.product.brand && (
                          <span className="text-[10px] font-bold uppercase text-neutral-400">{item.product.brand}</span>
                        )}
                        <h5 className="font-semibold text-xs text-neutral-900 dark:text-white line-clamp-1">{item.product.name}</h5>
                      </div>
                      <button
                        aria-label={`Remove ${item.product.name} from cart`}
                        onClick={() => removeItem(item.lineId)}
                        className="text-neutral-400 hover:text-rose-500 p-1"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>

                    <div className="flex items-center gap-2 mt-1.5">
                      <span className="text-[10px] font-bold px-2 py-0.5 bg-white dark:bg-neutral-700 text-neutral-800 dark:text-neutral-200 rounded border border-neutral-200 dark:border-neutral-600">
                        Size: {item.selectedSize}
                      </span>
                      <span className="text-[10px] font-bold px-2 py-0.5 bg-white dark:bg-neutral-700 text-neutral-800 dark:text-neutral-200 rounded border border-neutral-200 dark:border-neutral-600">
                        {item.selectedColour}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center justify-between mt-2">
                    <span className="font-extrabold text-sm text-neutral-900 dark:text-white">
                      ₹{item.unitPrice * item.quantity}
                    </span>

                    {/* Quantity Controls */}
                    <div className="flex items-center gap-2 bg-white dark:bg-neutral-700 border border-neutral-300 dark:border-neutral-600 rounded-lg px-2 py-1">
                      <button aria-label={`Decrease ${item.product.name} quantity`} onClick={() => updateQuantity(item.lineId, item.quantity - 1)} className="p-0.5 text-neutral-600 dark:text-neutral-200">
                        <Minus className="w-3 h-3" />
                      </button>
                      <span className="text-xs font-bold text-neutral-900 dark:text-white w-4 text-center">{item.quantity}</span>
                      <button aria-label={`Increase ${item.product.name} quantity`} onClick={() => updateQuantity(item.lineId, item.quantity + 1)} className="p-0.5 text-neutral-600 dark:text-neutral-200">
                        <Plus className="w-3 h-3" />
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Footer & Checkout CTA */}
        {items.length > 0 && (
          <div className="p-4 sm:p-6 border-t border-neutral-200 dark:border-neutral-800 bg-neutral-50 dark:bg-neutral-950 space-y-3">

            {/* Delivery Option Toggle */}
            <div className="flex items-center justify-between p-2.5 bg-white dark:bg-neutral-800 rounded-xl border border-neutral-200 dark:border-neutral-700 text-xs font-bold">
              <span className="text-neutral-600 dark:text-neutral-400">Speed:</span>
              <div className="flex gap-1">
                <button
                  disabled={!expressAvailable}
                  onClick={() => setDeliveryMethod('express')}
                  className={`px-3 py-1 rounded-lg transition-all disabled:cursor-not-allowed disabled:opacity-40 ${
                    deliveryMethod === 'express'
                      ? 'bg-lime-400 text-neutral-950 shadow-sm'
                      : 'text-neutral-500'
                  }`}
                >
                  ⚡ Express (60m)
                </button>
                <button
                  onClick={() => setDeliveryMethod('standard')}
                  className={`px-3 py-1 rounded-lg transition-all ${
                    deliveryMethod === 'standard'
                      ? 'bg-neutral-900 text-white dark:bg-neutral-700 shadow-sm'
                      : 'text-neutral-500'
                  }`}
                >
                  Normal Delivery
                </button>
              </div>
            </div>
            <p className="text-[11px] text-neutral-500">{deliveryAvailabilityMessage()} Delivery is available in {CONFIG.SERVICE_CITY} ({CONFIG.DEFAULT_PINCODE}).</p>

            {/* Price Breakdown */}
            <div className="space-y-1.5 text-xs text-neutral-600 dark:text-neutral-400">
              <div className="flex justify-between">
                <span>Subtotal</span>
                <span className="font-semibold text-neutral-900 dark:text-white">₹{subtotal}</span>
              </div>
              <div className="flex justify-between">
                <span>Delivery Charge</span>
                <span className="font-semibold text-neutral-900 dark:text-white">
                  {deliveryFee === 0 ? <strong className="text-emerald-600">FREE</strong> : `₹${deliveryFee}`}
                </span>
              </div>
              <div className="flex justify-between">
                <span>GST & Taxes (5%)</span>
                <span className="font-semibold text-neutral-900 dark:text-white">₹{taxes}</span>
              </div>
              <div className="flex justify-between pt-2 border-t border-neutral-200 dark:border-neutral-800 text-sm font-black text-neutral-900 dark:text-white">
                <span>Grand Total</span>
                <span className="text-lime-600 dark:text-lime-400">₹{grandTotal}</span>
              </div>
            </div>

            <button
              onClick={() => { onClose(); navigate('/checkout'); }}
              className="w-full py-3.5 bg-neutral-950 dark:bg-lime-400 text-white dark:text-neutral-950 font-black text-sm rounded-xl shadow-lg hover:bg-neutral-800 dark:hover:bg-lime-300 transition-all flex items-center justify-center gap-2"
            >
              <span>Proceed to Checkout</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
