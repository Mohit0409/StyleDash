import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, ShieldCheck } from 'lucide-react';
import { SEO } from '../components/SEO';
import { useCart } from '../context/CartContext';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import {
  createPaymentOrder,
  openRazorpayCheckout,
  PaymentApiError,
  placeCodOrder,
  ServerOrder,
  verifyPayment,
} from '../services/paymentApi';
import { CONFIG } from '../config';

const makeIdempotencyKey = () =>
  `checkout-${Date.now()}-${globalThis.crypto?.randomUUID?.() || Math.random().toString(36).slice(2)}`;

export const Checkout: React.FC = () => {
  const navigate = useNavigate();
  const {
    items,
    subtotal,
    deliveryFee,
    taxes,
    grandTotal,
    clearCart,
    deliveryMethod,
    appliedCoupon,
  } = useCart();
  const { user } = useAuth();
  const { showToast } = useToast();
  const savedAddress = user?.addresses?.find((address) => address.isDefault) || user?.addresses?.[0];

  const [name, setName] = useState(savedAddress?.name || user?.name || '');
  const [phone, setPhone] = useState(savedAddress?.phone || user?.phone || '');
  const [street, setStreet] = useState(savedAddress?.street || '');
  const [city] = useState(savedAddress?.city || CONFIG.SERVICE_CITY);
  const [pincode, setPincode] = useState(savedAddress?.pincode || CONFIG.DEFAULT_PINCODE);
  const [paymentMethod, setPaymentMethod] = useState<'cod' | 'upi' | 'card'>('cod');
  const [placing, setPlacing] = useState(false);
  const [checkoutError, setCheckoutError] = useState('');

  if (items.length === 0) {
    return (
      <div className="max-w-md mx-auto p-12 text-center space-y-4">
        <SEO title="Checkout - Vibe4You" noIndex />
        <h1 className="text-xl font-bold">Your cart is empty</h1>
        <button onClick={() => navigate('/products')} className="px-6 py-2.5 bg-neutral-950 text-white text-xs font-bold rounded-xl">
          Shop Fashion Catalogue
        </button>
      </div>
    );
  }

  const handlePlaceOrder = async (event: React.FormEvent) => {
    event.preventDefault();
    setPlacing(true);
    setCheckoutError('');

    const cartSnapshot = [...items];
    const intent = {
      items: cartSnapshot.map((item) => ({
        productId: item.productId,
        variantId: item.variantId,
        quantity: item.quantity,
      })),
      address: { name, phone, street, city, pincode },
      deliveryMethod,
      couponCode: appliedCoupon?.code || null,
      paymentMethod,
    };

    try {
      let confirmedOrder: ServerOrder;
      if (paymentMethod === 'cod') {
        const result = await placeCodOrder(intent, makeIdempotencyKey());
        confirmedOrder = result.order;
      } else {
        const createdOrder = await createPaymentOrder(intent, makeIdempotencyKey());
        const payment = await openRazorpayCheckout(
          createdOrder,
          { name, email: user?.email, phone },
          paymentMethod,
        );
        const result = await verifyPayment(payment, createdOrder.styleDashOrderId);
        if (result.pending) {
          clearCart();
          showToast('Payment authorized and awaiting capture. Track the pending order in your account.', 'info');
          navigate('/orders');
          return;
        }
        if (result.order.status === 'payment_review_required') {
          clearCart();
          showToast('Payment received. Stock confirmation is required. Do not pay again; check Your Orders.', 'info');
          navigate('/orders');
          return;
        }
        confirmedOrder = result.order;
      }

      clearCart();
      showToast(
        paymentMethod === 'cod' ? 'Cash on Delivery order placed!' : 'Payment verified and order placed!',
        'success',
      );
      navigate(`/order-success/${confirmedOrder.id}`);
    } catch (error) {
      const paymentError = error instanceof PaymentApiError
        ? error
        : new PaymentApiError('Checkout could not be completed. Please try again.');
      setCheckoutError(paymentError.message);
      showToast(paymentError.message, paymentError.code === 'payment_cancelled' ? 'info' : 'error');
    } finally {
      setPlacing(false);
    }
  };

  const paymentMethods: Array<{ id: 'cod' | 'upi' | 'card'; label: string; sub: string }> = [
    { id: 'cod', label: 'Cash / Pay on Delivery', sub: 'Pay with cash or UPI when your runner arrives' },
    { id: 'upi', label: 'UPI with Razorpay', sub: 'Use any supported UPI app in secure checkout' },
    { id: 'card', label: 'Credit / Debit Card with Razorpay', sub: 'Visa, Mastercard and RuPay cards' },
  ];

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      <SEO title="Checkout - Vibe4You" noIndex />
      <h1 className="text-2xl sm:text-3xl font-black text-neutral-900 dark:text-white">Secure Checkout</h1>

      <form onSubmit={handlePlaceOrder} className="grid md:grid-cols-3 gap-8">
        <div className="md:col-span-2 space-y-6">
          <div className="bg-white dark:bg-neutral-900 p-6 rounded-3xl border border-neutral-200 dark:border-neutral-800 space-y-4 shadow-sm">
            <h3 className="font-extrabold text-base text-neutral-900 dark:text-white">1. Delivery Address ({CONFIG.SERVICE_CITY})</h3>
            <div className="grid sm:grid-cols-2 gap-4 text-xs">
              <div>
                <label className="block font-bold text-neutral-600 dark:text-neutral-400 mb-1" htmlFor="checkout-name">Full Name</label>
                <input id="checkout-name" required autoComplete="name" type="text" value={name} onChange={(event) => setName(event.target.value)} className="w-full p-2.5 rounded-xl border border-neutral-300 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-800 font-bold" />
              </div>
              <div>
                <label className="block font-bold text-neutral-600 dark:text-neutral-400 mb-1" htmlFor="checkout-phone">Phone Number</label>
                <input id="checkout-phone" required autoComplete="tel" inputMode="tel" type="tel" value={phone} onChange={(event) => setPhone(event.target.value)} className="w-full p-2.5 rounded-xl border border-neutral-300 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-800 font-bold" />
              </div>
              <div className="sm:col-span-2">
                <label className="block font-bold text-neutral-600 dark:text-neutral-400 mb-1" htmlFor="checkout-street">Street Address &amp; Landmark</label>
                <input id="checkout-street" required autoComplete="street-address" type="text" value={street} onChange={(event) => setStreet(event.target.value)} className="w-full p-2.5 rounded-xl border border-neutral-300 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-800 font-bold" />
              </div>
              <div>
                <label className="block font-bold text-neutral-600 dark:text-neutral-400 mb-1" htmlFor="checkout-city">City</label>
                <input id="checkout-city" readOnly type="text" value={city} className="w-full p-2.5 rounded-xl border border-neutral-200 dark:border-neutral-800 bg-neutral-100 dark:bg-neutral-900 font-bold text-neutral-500" />
              </div>
              <div>
                <label className="block font-bold text-neutral-600 dark:text-neutral-400 mb-1" htmlFor="checkout-pincode">Pincode</label>
                <input id="checkout-pincode" required autoComplete="postal-code" inputMode="numeric" pattern="[0-9]{6}" maxLength={6} type="text" value={pincode} onChange={(event) => setPincode(event.target.value.replace(/\D/g, ''))} className="w-full p-2.5 rounded-xl border border-neutral-300 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-800 font-bold" />
              </div>
            </div>
          </div>

          <div className="bg-white dark:bg-neutral-900 p-6 rounded-3xl border border-neutral-200 dark:border-neutral-800 space-y-4 shadow-sm">
            <h3 className="font-extrabold text-base text-neutral-900 dark:text-white">2. Select Payment Method</h3>
            <div className="space-y-3">
              {paymentMethods.map((method) => (
                <label key={method.id} className={`flex items-start gap-3 p-4 rounded-2xl border cursor-pointer transition-all ${paymentMethod === method.id ? 'border-neutral-950 dark:border-lime-400 bg-neutral-50 dark:bg-neutral-800/80 shadow-md' : 'border-neutral-200 dark:border-neutral-800'}`}>
                  <input type="radio" name="payment" value={method.id} checked={paymentMethod === method.id} onChange={() => setPaymentMethod(method.id)} className="mt-1 accent-lime-500" />
                  <span>
                    <span className="font-bold text-xs text-neutral-900 dark:text-white block">{method.label}</span>
                    <span className="text-[11px] text-neutral-500">{method.sub}</span>
                  </span>
                </label>
              ))}
            </div>
            {paymentMethod !== 'cod' && (
              <p className="flex gap-2 text-[11px] text-neutral-500"><ShieldCheck className="w-4 h-4 shrink-0 text-lime-600" /> Your payment is completed in Razorpay Checkout. Vibe4You confirms fulfillment only after server-side signature and captured-payment verification.</p>
            )}
          </div>
        </div>

        <div className="bg-white dark:bg-neutral-900 p-6 rounded-3xl border border-neutral-200 dark:border-neutral-800 space-y-6 shadow-sm h-fit">
          <h3 className="font-black text-base text-neutral-900 dark:text-white">Order Summary</h3>
          <div className="space-y-3 max-h-48 overflow-y-auto no-scrollbar border-b border-neutral-100 dark:border-neutral-800 pb-4">
            {items.map((item) => (
              <div key={item.lineId} className="flex justify-between gap-3 text-xs">
                <div>
                  <p className="font-bold text-neutral-900 dark:text-white line-clamp-1">{item.product.name}</p>
                  <p className="text-[10px] text-neutral-500">{item.selectedSize} | {item.selectedColour} x {item.quantity}</p>
                </div>
                <span className="font-bold text-neutral-900 dark:text-white whitespace-nowrap">₹{item.unitPrice * item.quantity}</span>
              </div>
            ))}
          </div>
          <div className="space-y-2 text-xs text-neutral-600 dark:text-neutral-400">
            <div className="flex justify-between"><span>Subtotal</span><span>₹{subtotal}</span></div>
            <div className="flex justify-between"><span>Delivery</span><span>{deliveryFee === 0 ? 'FREE' : `₹${deliveryFee}`}</span></div>
            <div className="flex justify-between"><span>GST Taxes (5%)</span><span>₹{taxes}</span></div>
            <div className="flex justify-between pt-2 border-t border-neutral-200 dark:border-neutral-800 text-sm font-black text-neutral-900 dark:text-white">
              <span>Estimated Total</span><span className="text-lime-600 dark:text-lime-400">₹{grandTotal}</span>
            </div>
            <p className="text-[10px] leading-relaxed text-neutral-500">Inventory, coupon eligibility and the final payable amount are recalculated securely by the server.</p>
          </div>
          {checkoutError && <p role="alert" className="text-xs font-semibold text-red-600 dark:text-red-400">{checkoutError}</p>}
          <button type="submit" disabled={placing} className="w-full py-4 bg-neutral-950 dark:bg-lime-400 text-white dark:text-neutral-950 font-black text-sm rounded-xl shadow-xl hover:bg-neutral-800 dark:hover:bg-lime-300 transition-all flex items-center justify-center gap-2 disabled:cursor-not-allowed disabled:opacity-60">
            <span>{placing ? 'Processing securely...' : paymentMethod === 'cod' ? 'Place COD Order' : `Pay ₹${grandTotal}`}</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </form>
    </div>
  );
};
