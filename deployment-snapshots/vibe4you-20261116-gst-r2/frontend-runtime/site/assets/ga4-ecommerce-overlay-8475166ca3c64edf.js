/* Vibe4You GA4 ecommerce compatibility overlay: 2026-10-19.
 * Read-only storefront instrumentation. No checkout/payment/order mutations.
 * This overlay intentionally does not replace the immutable application bundles.
 */
(() => {
  'use strict';
  if (window.__v4yGA4OverlayVersion) return;
  window.__v4yGA4OverlayVersion = '2026-10-19-candidate-1';

  const consentKey = 'vibe4you_analytics_consent_v1';
  const publicOrigin = 'https://vibe4you.in';
  const countedViews = new Set();
  const attemptedOrders = new Set();
  let checkoutCounted = false;
  let lastPath = '';
  let pendingCheck = false;

  const hasConsent = () => {
    try { return window.localStorage.getItem(consentKey) === 'accepted'; }
    catch { return false; }
  };

  const safeLocation = path => publicOrigin + path;
  const send = (name, payload, path) => {
    if (!hasConsent() || typeof window.gtag !== 'function') return false;
    if (!['view_item', 'begin_checkout', 'purchase'].includes(name)) return false;
    window.gtag('event', name, {
      ...payload,
      page_location: safeLocation(path),
      page_title: 'Vibe4You',
    });
    return true;
  };

  const productView = () => {
    const path = window.location.pathname;
    if (!/^\/product\/[a-zA-Z0-9_-]+\/?$/.test(path)) return;
    const element = document.getElementById('styledash-seo-jsonld');
    if (!element || element.type !== 'application/ld+json') return;
    let p;
    try { p = JSON.parse(element.textContent || '{}'); } catch { return; }
    if (p['@type'] !== 'Product' || typeof p.name !== 'string' || typeof p.sku !== 'string') return;
    if (!document.title.includes(p.name)) return;
    const price = Number(p.offers && p.offers.price);
    if (!Number.isFinite(price) || price < 0 || !p.sku || !p.name) return;
    const key = path + '|' + p.sku;
    if (countedViews.has(key)) return;
    if (send('view_item', {
      currency: 'INR',
      value: price,
      items: [{
        item_id: p.sku,
        item_name: p.name.substring(0, 150),
        price,
        quantity: 1,
      }],
    }, path)) countedViews.add(key);
  };

  const checkoutBegin = () => {
    if (window.location.pathname !== '/checkout' || checkoutCounted) return;
    const heading = document.querySelector('h1');
    if (!heading || !/secure checkout/i.test(heading.textContent || '')) return;
    // Current production build does not expose canonical cart item values here.
    // This event is intentionally limited to the confirmed arrival at checkout.
    if (send('begin_checkout', { currency: 'INR' }, '/checkout')) checkoutCounted = true;
  };

  const validPurchase = order => order && typeof order === 'object'
    && typeof order.id === 'string'
    && Array.isArray(order.items) && order.items.length > 0
    && order.isPaymentTestOrder !== true
    && order.status !== 'payment_review_required'
    && (order.paymentStatus === 'paid'
      || (order.paymentMethod === 'cod' && order.codAdvancePaid === true));

  const digestOrder = async orderId => {
    if (!window.crypto || !window.crypto.subtle) return null;
    const data = new TextEncoder().encode(orderId);
    const bytes = new Uint8Array(await window.crypto.subtle.digest('SHA-256', data));
    return 'v4y_' + Array.from(bytes, x => x.toString(16).padStart(2, '0')).join('');
  };

  const purchaseCheck = async () => {
    const match = /^\/order-success\/([a-zA-Z0-9_-]{8,100})\/?$/.exec(window.location.pathname);
    if (!match || !hasConsent() || typeof window.gtag !== 'function') return;
    if (!Array.from(document.querySelectorAll('h1')).some(x => /order confirmed/i.test(x.textContent || ''))) return;
    const orderId = match[1];
    if (attemptedOrders.has(orderId)) return;
    attemptedOrders.add(orderId);
    try {
      const response = await fetch('/api/orders/' + encodeURIComponent(orderId), {
        method: 'GET',
        credentials: 'include',
        headers: { Accept: 'application/json' },
      });
      if (!response.ok) return;
      const payload = await response.json();
      const order = payload && payload.order;
      if (!validPurchase(order) || order.id !== orderId) return;
      const transactionId = await digestOrder(orderId);
      if (!transactionId) return;
      const guardKey = 'vibe4you_ga4_purchase_' + transactionId;
      try {
        if (window.localStorage.getItem(guardKey) === '1') return;
      } catch { /* Tracking still deduplicates by transaction ID in GA4. */ }
      const value = Number(order.grandTotal);
      const shipping = Number(order.deliveryFee);
      if (!Number.isFinite(value) || value < 0) return;
      const items = order.items.map(item => ({
        item_id: String(item.productId || '').substring(0, 120),
        item_name: String(item.productName || '').substring(0, 150),
        item_variant: String(item.sku || item.variantId || '').substring(0, 120),
        price: Number(item.unitPrice) || 0,
        quantity: Math.max(1, Number(item.quantity) || 1),
      })).filter(item => item.item_id && item.item_name);
      if (!items.length || !hasConsent()) return;
      if (send('purchase', {
        transaction_id: transactionId,
        currency: 'INR',
        value,
        shipping: Number.isFinite(shipping) ? Math.max(0, shipping) : 0,
        items,
      }, '/order-success')) {
        try { window.localStorage.setItem(guardKey, '1'); } catch { /* unavailable */ }
      }
    } catch {
      // Analytics failures must never affect the customer-facing checkout.
    }
  };

  const check = () => {
    pendingCheck = false;
    const path = window.location.pathname;
    if (path !== lastPath) {
      if (lastPath === '/checkout') checkoutCounted = false;
      lastPath = path;
    }
    if (!hasConsent()) return;
    try {
      if (path.startsWith('/product/')) productView();
      if (path === '/checkout') checkoutBegin();
      if (path.startsWith('/order-success/')) void purchaseCheck();
    } catch {
      // Never interfere with React rendering.
    }
  };

  const schedule = () => {
    if (pendingCheck) return;
    pendingCheck = true;
    setTimeout(check, 60);
  };

  const attach = () => {
    const observer = new MutationObserver(schedule);
    observer.observe(document.documentElement, { childList: true, subtree: true });
    document.addEventListener('click', schedule, true);
    window.addEventListener('pageshow', schedule);
    window.addEventListener('popstate', schedule);
    schedule();
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', attach, { once: true });
  else attach();
})();
