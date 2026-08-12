import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ShieldCheck, Zap, CheckCircle2, ArrowRight } from 'lucide-react';
import { SEO } from '../components/SEO';
import { useCart } from '../context/CartContext';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { orderRepository } from '../repositories/orderRepository';
import { Order, CartItem } from '../types';
import { CONFIG } from '../config';

export const Checkout: React.FC = () => {
  const navigate = useNavigate();
  const { items, subtotal, deliveryFee, taxes, grandTotal, clearCart, deliveryMethod } = useCart();
  const { user } = useAuth();
  const { showToast } = useToast();

  const [name, setName] = useState(user?.name || 'Mohit Jangde');
  const [phone, setPhone] = useState(user?.phone || '+919876543210');
  const [street, setStreet] = useState(user?.addresses[0]?.street || '12 Station Road, Main Market');
  const [city, setCity] = useState(CONFIG.SERVICE_CITY);
  const [pincode, setPincode] = useState(CONFIG.DEFAULT_PINCODE);
  const [paymentMethod, setPaymentMethod] = useState<'cod' | 'upi' | 'card'>('cod');
  const [placing, setPlacing] = useState(false);

  if (items.length === 0) {
    return (
      <div className="max-w-md mx-auto p-12 text-center space-y-4">
        <h2 className="text-xl font-bold">Your cart is empty</h2>
        <button onClick={() => navigate('/products')} className="px-6 py-2.5 bg-neutral-950 text-white text-xs font-bold rounded-xl">
          Shop Fashion Catalogue
        </button>
      </div>
    );
  }

  const handlePlaceOrder = async (e: React.FormEvent) => {
    e.preventDefault();
    setPlacing(true);

    const orderId = `SD-${new Date().toISOString().slice(0,10).replace(/-/g,'')}-${Math.floor(1000 + Math.random() * 9000)}`;

    const newOrder: Order = {
      id: orderId,
      userId: user ? user.uid : 'guest-user-id',
      items: [...items],
      address: {
        id: 'addr-checkout',
        name,
        phone,
        street,
        city,
        state: 'Madhya Pradesh',
        pincode
      },
      paymentMethod,
      paymentStatus: paymentMethod === 'cod' ? 'pending' : 'paid',
      subtotal,
      discount: 0,
      walletAmount: 0,
      deliveryFee,
      taxes,
      grandTotal,
      deliveryMethod,
      estimatedDelivery: '60 minutes',
      status: 'placed',
      statusHistory: [
        {
          status: 'placed',
          timestamp: new Date().toISOString(),
          note: 'Order placed successfully'
        }
      ],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString()
    };

    await orderRepository.saveOrder(newOrder);
    clearCart();
    showToast('Order placed successfully!', 'success');
    navigate(`/order-success/${orderId}`);
  };

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      <SEO title="Checkout - StyleDash" />

      <h1 className="text-2xl sm:text-3xl font-black text-neutral-900 dark:text-white">Secure Checkout</h1>

      <form onSubmit={handlePlaceOrder} className="grid md:grid-cols-3 gap-8">

        {/* Form Inputs */}
        <div className="md:col-span-2 space-y-6">

          {/* Shipping Address */}
          <div className="bg-white dark:bg-neutral-900 p-6 rounded-3xl border border-neutral-200 dark:border-neutral-800 space-y-4 shadow-sm">
            <h3 className="font-extrabold text-base text-neutral-900 dark:text-white">1. Delivery Address ({CONFIG.SERVICE_CITY})</h3>
            <div className="grid sm:grid-cols-2 gap-4 text-xs">
              <div>
                <label className="block font-bold text-neutral-600 dark:text-neutral-400 mb-1">Full Name</label>
                <input
                  required
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full p-2.5 rounded-xl border border-neutral-300 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-800 font-bold"
                />
              </div>
              <div>
                <label className="block font-bold text-neutral-600 dark:text-neutral-400 mb-1">Phone Number</label>
                <input
                  required
                  type="text"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  className="w-full p-2.5 rounded-xl border border-neutral-300 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-800 font-bold"
                />
              </div>
              <div className="sm:col-span-2">
                <label className="block font-bold text-neutral-600 dark:text-neutral-400 mb-1">Street Address & Landmark</label>
                <input
                  required
                  type="text"
                  value={street}
                  onChange={(e) => setStreet(e.target.value)}
                  className="w-full p-2.5 rounded-xl border border-neutral-300 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-800 font-bold"
                />
              </div>
              <div>
                <label className="block font-bold text-neutral-600 dark:text-neutral-400 mb-1">City</label>
                <input
                  disabled
                  type="text"
                  value={city}
                  className="w-full p-2.5 rounded-xl border border-neutral-200 dark:border-neutral-800 bg-neutral-100 dark:bg-neutral-900 font-bold text-neutral-500"
                />
              </div>
              <div>
                <label className="block font-bold text-neutral-600 dark:text-neutral-400 mb-1">Pincode</label>
                <input
                  required
                  type="text"
                  value={pincode}
                  onChange={(e) => setPincode(e.target.value)}
                  className="w-full p-2.5 rounded-xl border border-neutral-300 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-800 font-bold"
                />
              </div>
            </div>
          </div>

          {/* Payment Method */}
          <div className="bg-white dark:bg-neutral-900 p-6 rounded-3xl border border-neutral-200 dark:border-neutral-800 space-y-4 shadow-sm">
            <h3 className="font-extrabold text-base text-neutral-900 dark:text-white">2. Select Payment Method</h3>
            <div className="space-y-3">
              {[
                { id: 'cod', label: 'Cash / Pay on Delivery', sub: 'Pay via Cash or UPI when runner arrives at doorstep' },
                { id: 'upi', label: 'Instant UPI (Simulated Demo)', sub: 'GPay, PhonePe, Paytm or BHIM' },
                { id: 'card', label: 'Credit / Debit Card (Simulated Demo)', sub: 'Visa, Mastercard, RuPay' }
              ].map(pm => (
                <label
                  key={pm.id}
                  onClick={() => setPaymentMethod(pm.id as any)}
                  className={`flex items-start gap-3 p-4 rounded-2xl border cursor-pointer transition-all ${
                    paymentMethod === pm.id
                      ? 'border-neutral-950 dark:border-lime-400 bg-neutral-50 dark:bg-neutral-800/80 shadow-md'
                      : 'border-neutral-200 dark:border-neutral-800'
                  }`}
                >
                  <input
                    type="radio"
                    name="payment"
                    checked={paymentMethod === pm.id}
                    onChange={() => {}}
                    className="mt-1 accent-lime-500"
                  />
                  <div>
                    <span className="font-bold text-xs text-neutral-900 dark:text-white block">{pm.label}</span>
                    <span className="text-[11px] text-neutral-500">{pm.sub}</span>
                  </div>
                </label>
              ))}
            </div>
          </div>
        </div>

        {/* Summary Card */}
        <div className="bg-white dark:bg-neutral-900 p-6 rounded-3xl border border-neutral-200 dark:border-neutral-800 space-y-6 shadow-sm h-fit">
          <h3 className="font-black text-base text-neutral-900 dark:text-white">Order Summary</h3>

          <div className="space-y-3 max-h-48 overflow-y-auto no-scrollbar border-b border-neutral-100 dark:border-neutral-800 pb-4">
            {items.map(item => (
              <div key={item.lineId} className="flex justify-between text-xs">
                <div>
                  <p className="font-bold text-neutral-900 dark:text-white line-clamp-1">{item.product.name}</p>
                  <p className="text-[10px] text-neutral-500">{item.selectedSize} | {item.selectedColour} x {item.quantity}</p>
                </div>
                <span className="font-bold text-neutral-900 dark:text-white">₹{item.unitPrice * item.quantity}</span>
              </div>
            ))}
          </div>

          <div className="space-y-2 text-xs text-neutral-600 dark:text-neutral-400">
            <div className="flex justify-between"><span>Subtotal</span><span>₹{subtotal}</span></div>
            <div className="flex justify-between"><span>Delivery</span><span>{deliveryFee === 0 ? 'FREE' : `₹${deliveryFee}`}</span></div>
            <div className="flex justify-between"><span>GST Taxes (5%)</span><span>₹{taxes}</span></div>
            <div className="flex justify-between pt-2 border-t border-neutral-200 dark:border-neutral-800 text-sm font-black text-neutral-900 dark:text-white">
              <span>Grand Total</span><span className="text-lime-600 dark:text-lime-400">₹{grandTotal}</span>
            </div>
          </div>

          <button
            type="submit"
            disabled={placing}
            className="w-full py-4 bg-neutral-950 dark:bg-lime-400 text-white dark:text-neutral-950 font-black text-sm rounded-xl shadow-xl hover:bg-neutral-800 dark:hover:bg-lime-300 transition-all flex items-center justify-center gap-2"
          >
            <span>{placing ? 'Placing Order...' : 'Confirm & Place Order'}</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </form>
    </div>
  );
};
