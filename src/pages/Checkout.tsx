import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, Globe2, ShieldCheck, Truck, Zap } from 'lucide-react';
import { DeliveryLocationCheck } from '../components/DeliveryLocationCheck';
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
import { ApiError } from '../services/apiClient';
import { mediatorOrderApi } from '../services/businessApi';
import { CONFIG } from '../config';
import { serviceAreaRepository } from '../repositories/serviceAreaRepository';
import type { DeliveryCoordinates, ServiceArea } from '../types';
import { cartExpressEligibility, isExpressDeliveryAvailable } from '../utils/delivery';
import { allIndiaCartEligibility } from '../utils/allIndiaDelivery';

const makeIdempotencyKey = () =>
  `checkout-${Date.now()}-${globalThis.crypto?.randomUUID?.() || Math.random().toString(36).slice(2)}`;

export const Checkout: React.FC = () => {
  const navigate = useNavigate();
  const {
    items,
    subtotal,
    deliveryFee,
    grandTotal,
    tryAtHomeFee,
    clearCart,
    deliveryMethod,
    setDeliveryMethod,
    appliedCoupon,
  } = useCart();
  const { user } = useAuth();
  const { showToast } = useToast();
  const savedAddress = user?.addresses?.find((address) => address.isDefault) || user?.addresses?.[0];
  const expressWeekend = isExpressDeliveryAvailable();
  const expressCart = cartExpressEligibility(items.map(item => item.product));
  const expressSelectable = expressWeekend && expressCart.eligible;
  const expressUnavailableReason = !expressWeekend
    ? 'Express Delivery is available Saturday and Sunday in Neemuch for every product.'
    : '';
  const allIndia = allIndiaCartEligibility(items);

  const [deliveryScope, setDeliveryScope] = useState<'local' | 'all_india'>('local');
  const [name, setName] = useState(savedAddress?.name || user?.name || '');
  const [phone, setPhone] = useState(savedAddress?.phone || user?.phone || '');
  const [street, setStreet] = useState(savedAddress?.street || '');
  const [indiaCity, setIndiaCity] = useState(savedAddress?.city || '');
  const [indiaState, setIndiaState] = useState(savedAddress?.state || '');
  const [indiaPincode, setIndiaPincode] = useState(savedAddress?.pincode || '');
  const [paymentMethod, setPaymentMethod] = useState<'cod' | 'upi' | 'card'>('cod');
  const [placing, setPlacing] = useState(false);
  const [checkoutError, setCheckoutError] = useState('');
  const [deliveryCoordinates, setDeliveryCoordinates] = useState<DeliveryCoordinates | null>(null);
  const [serviceArea, setServiceArea] = useState<ServiceArea | null>(null);

  const isAllIndia = deliveryScope === 'all_india' && allIndia.eligible;
  const localCity = CONFIG.SERVICE_CITY;
  const localPincode = CONFIG.DEFAULT_PINCODE;

  useEffect(() => {
    let cancelled = false;
    serviceAreaRepository.checkPincode(localPincode)
      .then(result => { if (!cancelled) setServiceArea(result); })
      .catch(() => { if (!cancelled) setServiceArea(null); });
    return () => { cancelled = true; };
  }, [localPincode]);

  useEffect(() => {
    if (deliveryScope === 'all_india' && !allIndia.eligible) setDeliveryScope('local');
  }, [allIndia.eligible, deliveryScope]);

  const polygonDeliveryRequired = !isAllIndia && serviceArea?.enforcementMode === 'polygon';

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

    if (isAllIndia) {
      setPlacing(true);
      setCheckoutError('');
      try {
        const result = await mediatorOrderApi.place(
          {
            items: items.map(item => ({
              productId: item.productId,
              variantId: item.variantId,
              quantity: item.quantity,
            })),
            address: {
              name,
              phone,
              street,
              city: indiaCity,
              state: indiaState,
              pincode: indiaPincode,
            },
          },
          makeIdempotencyKey(),
        );
        clearCart();
        showToast('Order request sent to the shop. The shop will contact you directly.', 'success');
        navigate(`/mediator-order-success/${encodeURIComponent(result.order.id)}`);
      } catch (cause) {
        const message = cause instanceof ApiError || cause instanceof Error
          ? cause.message
          : 'The All India order request could not be sent.';
        setCheckoutError(message);
        showToast(message, 'error');
      } finally {
        setPlacing(false);
      }
      return;
    }

    if (polygonDeliveryRequired && (!deliveryCoordinates || serviceArea?.serviceable !== true)) {
      const message = 'Confirm that your delivery pin is inside the Vibe4You delivery area before placing the order.';
      setCheckoutError(message);
      showToast(message, 'info');
      return;
    }
    setPlacing(true);
    setCheckoutError('');

    const cartSnapshot = [...items];
    const intent = {
      items: cartSnapshot.map((item) => ({
        productId: item.productId,
        variantId: item.variantId,
        quantity: item.quantity,
        ...(item.tryAtHomeVariantIds?.length === 2 ? {
          tryAtHomeVariantIds: item.tryAtHomeVariantIds,
          tryAtHomeTermsAccepted: item.tryAtHomeTermsAccepted === true,
        } : {}),
      })),
      address: {
        name,
        phone,
        street,
        city: localCity,
        pincode: localPincode,
        ...(polygonDeliveryRequired && deliveryCoordinates ? deliveryCoordinates : {}),
      },
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
      <h1 className="text-2xl sm:text-3xl font-black text-neutral-900 dark:text-white">
        {isAllIndia ? 'All India Order Request' : 'Secure Checkout'}
      </h1>

      {allIndia.eligible && (
        <section className="rounded-3xl border border-lime-300 bg-lime-50/60 p-5 dark:border-lime-900 dark:bg-lime-950/20">
          <div className="flex items-start gap-3">
            <Globe2 className="mt-0.5 h-5 w-5 shrink-0 text-lime-700 dark:text-lime-300" />
            <div className="flex-1">
              <h2 className="font-black">Delivery coverage</h2>
              <p className="mt-1 text-xs text-neutral-600 dark:text-neutral-400">
                This shop also accepts All India order requests. Local Neemuch checkout remains available normally.
              </p>
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                <label className={`rounded-2xl border p-4 cursor-pointer ${deliveryScope === 'local' ? 'border-neutral-950 bg-white dark:border-lime-400 dark:bg-neutral-900' : 'border-neutral-200 dark:border-neutral-800'}`}>
                  <input type="radio" name="delivery-scope" checked={deliveryScope === 'local'} onChange={() => setDeliveryScope('local')} className="mr-2 accent-lime-500" />
                  <strong className="text-sm">Neemuch delivery</strong>
                  <span className="mt-1 block text-[11px] text-neutral-500">Existing Vibe4You delivery and payment flow.</span>
                </label>
                <label className={`rounded-2xl border p-4 cursor-pointer ${deliveryScope === 'all_india' ? 'border-lime-500 bg-white dark:border-lime-400 dark:bg-neutral-900' : 'border-neutral-200 dark:border-neutral-800'}`}>
                  <input type="radio" name="delivery-scope" checked={deliveryScope === 'all_india'} onChange={() => setDeliveryScope('all_india')} className="mr-2 accent-lime-500" />
                  <strong className="text-sm">All India</strong>
                  <span className="mt-1 block text-[11px] text-neutral-500">Vibe4You forwards the order request to the shop.</span>
                </label>
              </div>
            </div>
          </div>
        </section>
      )}

      <form onSubmit={handlePlaceOrder} className="grid md:grid-cols-3 gap-8">
        <div className="md:col-span-2 space-y-6">
          <div className="bg-white dark:bg-neutral-900 p-6 rounded-3xl border border-neutral-200 dark:border-neutral-800 space-y-4 shadow-sm">
            <h3 className="font-extrabold text-base text-neutral-900 dark:text-white">
              1. Delivery Address {isAllIndia ? '(All India)' : `(${CONFIG.SERVICE_CITY})`}
            </h3>
            <p className="text-xs text-neutral-500">
              {isAllIndia
                ? 'Enter the address where the shop should arrange courier delivery.'
                : `Vibe4You currently delivers only in ${CONFIG.SERVICE_CITY} (${CONFIG.DEFAULT_PINCODE}).`}
            </p>
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
              {isAllIndia ? (
                <>
                  <div>
                    <label className="block font-bold text-neutral-600 dark:text-neutral-400 mb-1" htmlFor="checkout-city">City</label>
                    <input id="checkout-city" required minLength={2} maxLength={80} type="text" value={indiaCity} onChange={(event) => setIndiaCity(event.target.value)} className="w-full p-2.5 rounded-xl border border-neutral-300 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-800 font-bold" />
                  </div>
                  <div>
                    <label className="block font-bold text-neutral-600 dark:text-neutral-400 mb-1" htmlFor="checkout-state">State</label>
                    <input id="checkout-state" required minLength={2} maxLength={80} type="text" value={indiaState} onChange={(event) => setIndiaState(event.target.value)} className="w-full p-2.5 rounded-xl border border-neutral-300 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-800 font-bold" />
                  </div>
                  <div>
                    <label className="block font-bold text-neutral-600 dark:text-neutral-400 mb-1" htmlFor="checkout-pincode">Pincode</label>
                    <input id="checkout-pincode" required inputMode="numeric" pattern="[0-9]{6}" maxLength={6} type="text" value={indiaPincode} onChange={(event) => setIndiaPincode(event.target.value.replace(/\D/g, ''))} className="w-full p-2.5 rounded-xl border border-neutral-300 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-800 font-bold" />
                  </div>
                </>
              ) : (
                <>
                  <div>
                    <label className="block font-bold text-neutral-600 dark:text-neutral-400 mb-1" htmlFor="checkout-city">City</label>
                    <input id="checkout-city" readOnly type="text" value={localCity} className="w-full p-2.5 rounded-xl border border-neutral-200 dark:border-neutral-800 bg-neutral-100 dark:bg-neutral-900 font-bold text-neutral-500" />
                  </div>
                  <div>
                    <label className="block font-bold text-neutral-600 dark:text-neutral-400 mb-1" htmlFor="checkout-pincode">Pincode</label>
                    <input id="checkout-pincode" readOnly type="text" value={localPincode} className="w-full p-2.5 rounded-xl border border-neutral-200 dark:border-neutral-800 bg-neutral-100 dark:bg-neutral-900 font-bold text-neutral-500" />
                  </div>
                </>
              )}
            </div>
            {polygonDeliveryRequired && (
              <DeliveryLocationCheck
                pincode={localPincode}
                coordinates={deliveryCoordinates}
                onCoordinates={setDeliveryCoordinates}
                onResult={setServiceArea}
              />
            )}
          </div>

          {isAllIndia ? (
            <div className="bg-white dark:bg-neutral-900 p-6 rounded-3xl border border-neutral-200 dark:border-neutral-800 space-y-4 shadow-sm">
              <h3 className="font-extrabold text-base text-neutral-900 dark:text-white">2. Shop-arranged delivery &amp; payment</h3>
              <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-xs leading-relaxed text-amber-900 dark:border-amber-900 dark:bg-amber-950/20 dark:text-amber-200">
                <strong>Vibe4You is the mediator only for this All India order.</strong>
                <p className="mt-2">Vibe4You will record your order request and inform the shop. The shop will contact you to confirm product availability, payment and courier arrangements.</p>
                <p className="mt-2 font-bold">
                  {allIndia.shippingPayer === 'shop'
                    ? 'The shop has chosen to pay the courier / delivery charge.'
                    : 'You will pay the courier / delivery charge. The shop will confirm the amount with you.'}
                </p>
              </div>
              {appliedCoupon && <p className="text-xs font-semibold text-neutral-500">Vibe4You coupons apply only to the normal Vibe4You checkout and are not applied to this mediator order request.</p>}
            </div>
          ) : (
            <>
              <div className="bg-white dark:bg-neutral-900 p-6 rounded-3xl border border-neutral-200 dark:border-neutral-800 space-y-4 shadow-sm">
                <h3 className="font-extrabold text-base text-neutral-900 dark:text-white">2. Delivery Method</h3>
                <div className="grid sm:grid-cols-2 gap-3">
                  <label className={`flex items-start gap-3 p-4 rounded-2xl border cursor-pointer transition-all ${deliveryMethod === 'standard' ? 'border-neutral-950 dark:border-lime-400 bg-neutral-50 dark:bg-neutral-800/80 shadow-md' : 'border-neutral-200 dark:border-neutral-800'}`}>
                    <input type="radio" name="delivery" value="standard" checked={deliveryMethod === 'standard'} onChange={() => setDeliveryMethod('standard')} className="mt-1 accent-lime-500" />
                    <Truck className="mt-0.5 h-4 w-4 shrink-0 text-neutral-500" />
                    <span>
                      <span className="font-bold text-xs text-neutral-900 dark:text-white block">Same Day Delivery</span>
                      <span className="text-[11px] text-neutral-500">{subtotal < CONFIG.FREE_DELIVERY_THRESHOLD ? '₹50 for orders below ₹300' : 'FREE on orders of ₹300+'} - delivered the same day</span>
                    </span>
                  </label>
                  <label className={`flex items-start gap-3 p-4 rounded-2xl border transition-all ${expressSelectable ? 'cursor-pointer' : 'cursor-not-allowed opacity-60'} ${deliveryMethod === 'express' ? 'border-lime-500 bg-lime-50 dark:border-lime-400 dark:bg-lime-950/20 shadow-md' : 'border-neutral-200 dark:border-neutral-800'}`}>
                    <input type="radio" name="delivery" value="express" checked={deliveryMethod === 'express'} disabled={!expressSelectable} onChange={() => setDeliveryMethod('express')} className="mt-1 accent-lime-500" />
                    <Zap className="mt-0.5 h-4 w-4 shrink-0 text-lime-600" />
                    <span>
                      <span className="font-bold text-xs text-neutral-900 dark:text-white block">Express Delivery</span>
                      <span className="text-[11px] text-neutral-500">About 60 minutes - ₹80 - Saturday &amp; Sunday</span>
                    </span>
                  </label>
                </div>
                {expressUnavailableReason && (
                  <p role="status" className="rounded-xl bg-amber-50 px-3 py-2 text-[11px] font-semibold text-amber-800 dark:bg-amber-950/30 dark:text-amber-200">{expressUnavailableReason}</p>
                )}
                {deliveryMethod === 'express' && (
                  <p className="text-[11px] font-semibold text-emerald-700 dark:text-emerald-300">Express selected. Delivery charge and estimated total have been recalculated below.</p>
                )}
              </div>

              <div className="bg-white dark:bg-neutral-900 p-6 rounded-3xl border border-neutral-200 dark:border-neutral-800 space-y-4 shadow-sm">
                <h3 className="font-extrabold text-base text-neutral-900 dark:text-white">3. Select Payment Method</h3>
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
            </>
          )}
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
            {isAllIndia ? (
              <>
                <div className="flex justify-between"><span>Courier charge</span><span>{allIndia.shippingPayer === 'shop' ? 'Paid by shop' : 'Confirmed by shop'}</span></div>
                <div className="flex justify-between pt-2 border-t border-neutral-200 dark:border-neutral-800 text-sm font-black text-neutral-900 dark:text-white">
                  <span>Merchandise total</span><span className="text-lime-600 dark:text-lime-400">₹{subtotal}</span>
                </div>
                <p className="rounded-xl border border-neutral-200 p-3 text-[10px] leading-relaxed text-neutral-500 dark:border-neutral-800">
                  No payment is collected by Vibe4You for this All India mediator order. The shop will contact you directly.
                </p>
              </>
            ) : (
              <>
                <div className="flex justify-between"><span>{deliveryMethod === 'express' ? 'Express Delivery' : 'Same Day Delivery'}</span><span>{deliveryFee === 0 ? 'FREE' : `₹${deliveryFee}`}</span></div>
                <div className="flex justify-between"><span>Delivery ETA</span><span>{deliveryMethod === 'express' ? 'About 60 minutes' : 'Same day'}</span></div>
                {tryAtHomeFee > 0 && <div className="flex justify-between"><span>Try at Home fee</span><span>₹{tryAtHomeFee}</span></div>}
                <div className="flex justify-between pt-2 border-t border-neutral-200 dark:border-neutral-800 text-sm font-black text-neutral-900 dark:text-white">
                  <span>Estimated Total</span><span className="text-lime-600 dark:text-lime-400">₹{grandTotal}</span>
                </div>
                <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 p-3 text-[10px] leading-relaxed text-neutral-500">
                  <p className="font-bold text-neutral-700 dark:text-neutral-300">Billing details</p>
                  <p>Vibe4You | GSTIN: 23JVZPM8734E1ZT</p>
                </div>
                <p className="text-[10px] leading-relaxed text-neutral-500">Inventory, coupon eligibility and the final payable amount are recalculated securely by the server.</p>
              </>
            )}
          </div>
          {checkoutError && <p role="alert" className="text-xs font-semibold text-red-600 dark:text-red-400">{checkoutError}</p>}
          <button type="submit" disabled={placing} className="w-full py-4 bg-neutral-950 dark:bg-lime-400 text-white dark:text-neutral-950 font-black text-sm rounded-xl shadow-xl hover:bg-neutral-800 dark:hover:bg-lime-300 transition-all flex items-center justify-center gap-2 disabled:cursor-not-allowed disabled:opacity-60">
            <span>{placing
              ? 'Processing securely...'
              : isAllIndia
                ? 'Send Order Request to Shop'
                : paymentMethod === 'cod'
                  ? 'Place COD Order'
                  : `Pay ₹${grandTotal}`}</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </form>
    </div>
  );
};
