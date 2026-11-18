/* Display-only product assurances. No checkout, account or payment mutations. */
(() => {
  'use strict';
  if (window.__v4yProductAssurancesV1) return;
  window.__v4yProductAssurancesV1 = true;

  const templates = {"local":"<ul aria-label=\"Product assurances\" class=\"grid w-full max-w-[calc(100vw-2rem)] grid-cols-2 gap-x-3 gap-y-5 border-y border-neutral-200 px-1 py-6 dark:border-neutral-800 sm:grid-cols-4\"><li class=\"flex min-w-0 flex-col items-center gap-2 text-center\"><svg xmlns=\"http://www.w3.org/2000/svg\" width=\"24\" height=\"24\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\" stroke-linecap=\"round\" stroke-linejoin=\"round\" class=\"lucide lucide-badge-check h-8 w-8 shrink-0 text-neutral-950 dark:text-white\" aria-hidden=\"true\"><path d=\"M3.85 8.62a4 4 0 0 1 4.78-4.77 4 4 0 0 1 6.74 0 4 4 0 0 1 4.78 4.78 4 4 0 0 1 0 6.74 4 4 0 0 1-4.77 4.78 4 4 0 0 1-6.75 0 4 4 0 0 1-4.78-4.77 4 4 0 0 1 0-6.76Z\"></path><path d=\"m9 12 2 2 4-4\"></path></svg><div class=\"space-y-1\"><p class=\"text-xs font-bold leading-4 text-neutral-950 dark:text-white\">100% Genuine</p><p class=\"text-[11px] leading-4 text-neutral-600 dark:text-neutral-400\">Products</p></div></li><li class=\"flex min-w-0 flex-col items-center gap-2 text-center\"><svg xmlns=\"http://www.w3.org/2000/svg\" width=\"24\" height=\"24\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\" stroke-linecap=\"round\" stroke-linejoin=\"round\" class=\"lucide lucide-truck h-8 w-8 shrink-0 text-neutral-950 dark:text-white\" aria-hidden=\"true\"><path d=\"M14 18V6a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v11a1 1 0 0 0 1 1h2\"></path><path d=\"M15 18H9\"></path><path d=\"M19 18h2a1 1 0 0 0 1-1v-3.65a1 1 0 0 0-.22-.624l-3.48-4.35A1 1 0 0 0 17.52 8H14\"></path><circle cx=\"17\" cy=\"18\" r=\"2\"></circle><circle cx=\"7\" cy=\"18\" r=\"2\"></circle></svg><div class=\"space-y-1\"><p class=\"text-xs font-bold leading-4 text-neutral-950 dark:text-white\">Local Delivery</p><p class=\"text-[11px] leading-4 text-neutral-600 dark:text-neutral-400\">In supported areas</p></div></li><li class=\"flex min-w-0 flex-col items-center gap-2 text-center\"><svg xmlns=\"http://www.w3.org/2000/svg\" width=\"24\" height=\"24\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\" stroke-linecap=\"round\" stroke-linejoin=\"round\" class=\"lucide lucide-receipt-text h-8 w-8 shrink-0 text-neutral-950 dark:text-white\" aria-hidden=\"true\"><path d=\"M4 2v20l2-1 2 1 2-1 2 1 2-1 2 1 2-1 2 1V2l-2 1-2-1-2 1-2-1-2 1-2-1-2 1Z\"></path><path d=\"M14 8H8\"></path><path d=\"M16 12H8\"></path><path d=\"M13 16H8\"></path></svg><div class=\"space-y-1\"><p class=\"text-xs font-bold leading-4 text-neutral-950 dark:text-white\">GST Invoice</p><p class=\"text-[11px] leading-4 text-neutral-600 dark:text-neutral-400\">Where applicable</p></div></li><li class=\"flex min-w-0 flex-col items-center gap-2 text-center\"><svg xmlns=\"http://www.w3.org/2000/svg\" width=\"24\" height=\"24\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\" stroke-linecap=\"round\" stroke-linejoin=\"round\" class=\"lucide lucide-video h-8 w-8 shrink-0 text-neutral-950 dark:text-white\" aria-hidden=\"true\"><path d=\"m16 13 5.223 3.482a.5.5 0 0 0 .777-.416V7.87a.5.5 0 0 0-.752-.432L16 10.5\"></path><rect x=\"2\" y=\"6\" width=\"14\" height=\"12\" rx=\"2\"></rect></svg><div class=\"space-y-1\"><p class=\"text-xs font-bold leading-4 text-neutral-950 dark:text-white\">Product Video</p><p class=\"text-[11px] leading-4 text-neutral-600 dark:text-neutral-400\">Shared at dispatch</p></div></li></ul>","outside":"<ul aria-label=\"Product assurances\" class=\"grid w-full max-w-[calc(100vw-2rem)] grid-cols-2 gap-x-3 gap-y-5 border-y border-neutral-200 px-1 py-6 dark:border-neutral-800 sm:grid-cols-4\"><li class=\"flex min-w-0 flex-col items-center gap-2 text-center\"><svg xmlns=\"http://www.w3.org/2000/svg\" width=\"24\" height=\"24\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\" stroke-linecap=\"round\" stroke-linejoin=\"round\" class=\"lucide lucide-badge-check h-8 w-8 shrink-0 text-neutral-950 dark:text-white\" aria-hidden=\"true\"><path d=\"M3.85 8.62a4 4 0 0 1 4.78-4.77 4 4 0 0 1 6.74 0 4 4 0 0 1 4.78 4.78 4 4 0 0 1 0 6.74 4 4 0 0 1-4.77 4.78 4 4 0 0 1-6.75 0 4 4 0 0 1-4.78-4.77 4 4 0 0 1 0-6.76Z\"></path><path d=\"m9 12 2 2 4-4\"></path></svg><div class=\"space-y-1\"><p class=\"text-xs font-bold leading-4 text-neutral-950 dark:text-white\">100% Genuine</p><p class=\"text-[11px] leading-4 text-neutral-600 dark:text-neutral-400\">Products</p></div></li><li class=\"flex min-w-0 flex-col items-center gap-2 text-center\"><svg xmlns=\"http://www.w3.org/2000/svg\" width=\"24\" height=\"24\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\" stroke-linecap=\"round\" stroke-linejoin=\"round\" class=\"lucide lucide-truck h-8 w-8 shrink-0 text-neutral-950 dark:text-white\" aria-hidden=\"true\"><path d=\"M14 18V6a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v11a1 1 0 0 0 1 1h2\"></path><path d=\"M15 18H9\"></path><path d=\"M19 18h2a1 1 0 0 0 1-1v-3.65a1 1 0 0 0-.22-.624l-3.48-4.35A1 1 0 0 0 17.52 8H14\"></path><circle cx=\"17\" cy=\"18\" r=\"2\"></circle><circle cx=\"7\" cy=\"18\" r=\"2\"></circle></svg><div class=\"space-y-1\"><p class=\"text-xs font-bold leading-4 text-neutral-950 dark:text-white\">Pan-India Shipping</p><p class=\"text-[11px] leading-4 text-neutral-600 dark:text-neutral-400\">By delivery request</p></div></li><li class=\"flex min-w-0 flex-col items-center gap-2 text-center\"><svg xmlns=\"http://www.w3.org/2000/svg\" width=\"24\" height=\"24\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\" stroke-linecap=\"round\" stroke-linejoin=\"round\" class=\"lucide lucide-receipt-text h-8 w-8 shrink-0 text-neutral-950 dark:text-white\" aria-hidden=\"true\"><path d=\"M4 2v20l2-1 2 1 2-1 2 1 2-1 2 1 2-1 2 1V2l-2 1-2-1-2 1-2-1-2 1-2-1-2 1Z\"></path><path d=\"M14 8H8\"></path><path d=\"M16 12H8\"></path><path d=\"M13 16H8\"></path></svg><div class=\"space-y-1\"><p class=\"text-xs font-bold leading-4 text-neutral-950 dark:text-white\">GST Invoice</p><p class=\"text-[11px] leading-4 text-neutral-600 dark:text-neutral-400\">Where applicable</p></div></li><li class=\"flex min-w-0 flex-col items-center gap-2 text-center\"><svg xmlns=\"http://www.w3.org/2000/svg\" width=\"24\" height=\"24\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\" stroke-linecap=\"round\" stroke-linejoin=\"round\" class=\"lucide lucide-video h-8 w-8 shrink-0 text-neutral-950 dark:text-white\" aria-hidden=\"true\"><path d=\"m16 13 5.223 3.482a.5.5 0 0 0 .777-.416V7.87a.5.5 0 0 0-.752-.432L16 10.5\"></path><rect x=\"2\" y=\"6\" width=\"14\" height=\"12\" rx=\"2\"></rect></svg><div class=\"space-y-1\"><p class=\"text-xs font-bold leading-4 text-neutral-950 dark:text-white\">Product Video</p><p class=\"text-[11px] leading-4 text-neutral-600 dark:text-neutral-400\">Shared at dispatch</p></div></li></ul>"};
  const marker = 'data-v4y-product-assurances';
  let currentPath = '';
  let outsideDelivery = false;
  let request = null;
  let scheduled = false;

  function makeRow() {
    const template = document.createElement('template');
    template.innerHTML = outsideDelivery ? templates.outside : templates.local;
    const row = template.content.firstElementChild;
    row.setAttribute(marker, '');
    row.dataset.shipping = outsideDelivery ? 'request' : 'local';
    return row;
  }

  function render() {
    scheduled = false;
    const path = window.location.pathname;
    const match = /^\/product\/([^/]+)\/?$/.exec(path);
    if (path !== currentPath) {
      currentPath = path;
      outsideDelivery = false;
      if (request) request.abort();
      request = null;
      document.querySelectorAll('[' + marker + ']').forEach(row => row.remove());
      if (match) {
        let slug;
        try { slug = decodeURIComponent(match[1]); } catch { return; }
        const controller = new AbortController();
        request = controller;
        const timeout = window.setTimeout(() => controller.abort(), 10000);
        fetch('/api/shop-products/published?slug=' + encodeURIComponent(slug), {
          method: 'GET', credentials: 'same-origin', signal: controller.signal,
        })
          .then(response => response.ok ? response.json() : null)
          .then(payload => {
            if (window.location.pathname !== path || request !== controller) return;
            outsideDelivery = payload?.success === true
              && payload.product?.active === true
              && payload.product?.outsideNeemuchDeliveryAvailable === true;
            schedule();
          })
          .catch(() => { /* Retain the conservative local-delivery label. */ })
          .finally(() => window.clearTimeout(timeout));
      }
    }
    if (!match) return;

    const root = document.getElementById('root');
    if (!root) return;
    // A future native component takes precedence over this compatibility asset.
    const native = root.querySelector('ul[aria-label="Product assurances"]:not([' + marker + '])');
    if (native) {
      root.querySelectorAll('[' + marker + ']').forEach(row => row.remove());
      return;
    }
    const label = Array.from(root.querySelectorAll('span')).find(
      node => node.textContent.trim() === 'Dispatched from Neemuch Partner Boutique',
    );
    const delivery = label?.closest('div.rounded-2xl');
    if (!delivery?.parentElement) return;
    let row = root.querySelector('[' + marker + ']');
    const mode = outsideDelivery ? 'request' : 'local';
    if (!row || row.dataset.shipping !== mode) {
      const replacement = makeRow();
      if (row) row.replaceWith(replacement);
      row = replacement;
    }
    if (delivery.nextElementSibling !== row) delivery.insertAdjacentElement('afterend', row);
  }

  function schedule() {
    if (scheduled) return;
    scheduled = true;
    window.requestAnimationFrame(render);
  }

  function start() {
    new MutationObserver(schedule).observe(document.body, {
      childList: true, subtree: true,
    });
    window.addEventListener('popstate', schedule);
    schedule();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, { once: true });
  else start();
})();
