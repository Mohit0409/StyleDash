/* Vibe4You mobile storefront UI fix - 2026-10-21.
   Presentation only. No changes to product data or shopping logic. */
(() => {
  "use strict";
  if (window.__v4yMobileUi20261021) return;
  window.__v4yMobileUi20261021 = true;

  const style = document.createElement("style");
  style.id = "v4y-mobile-ui-20261021-style";
  style.textContent = [
    '[data-testid="mobile-filter-backdrop"] { z-index: 1010 !important; height: 100dvh !important; max-height: 100dvh !important; overflow: hidden !important; }',
    '[data-testid="mobile-filter-backdrop"] [role="dialog"] { height: 100dvh !important; max-height: 100dvh !important; min-height: 0 !important; display: flex !important; flex-direction: column !important; box-sizing: border-box !important; }',
    '[data-testid="mobile-filter-backdrop"] [role="dialog"] > :first-child { min-height: 0 !important; overflow-y: auto !important; -webkit-overflow-scrolling: touch !important; }',
    '[data-testid="mobile-filter-backdrop"] [role="dialog"] > :last-child { flex-shrink: 0 !important; position: relative !important; z-index: 1 !important; padding-bottom: max(1rem, env(safe-area-inset-bottom)) !important; background: inherit; }',
    'body:has([data-testid="mobile-filter-backdrop"]) [data-mobile-bottom-nav] { visibility: hidden !important; pointer-events: none !important; }',
    'nav[aria-label="Browse departments"] .v4y-added-category-circle { background-image: none !important; background-size: cover !important; background-position: center !important; display: flex !important; align-items: center !important; justify-content: center !important; font-size: 1.7rem !important; }'
  ].join("\n");
  document.head.appendChild(style);

  const additions = [
    { label: "Watches", href: "/products?search=watch", icon: "⌚", color: "#eaf1ff" },
    { label: "Groceries", href: "/products?category=Groceries", icon: "🛒", color: "#e8f7e5" },
    { label: "Nutrition", href: "/products?category=Health%20%26%20Nutrition", icon: "\u{1F34E}", color: "#e5f6ee" }
  ];
  let updating = false;
  function updateShortcuts() {
    if (updating) return;
    updating = true;
    try {
      const nav = document.querySelector('nav[aria-label="Browse departments"]');
      const rail = nav && nav.querySelector(":scope > div");
      if (!rail) return;
      const existing = Array.from(rail.querySelectorAll(":scope > a"));
      const template = existing.find(a => a.textContent.trim() === "Footwear") || existing[0];
      if (!template) return;
      const before = existing.find(a => a.textContent.trim() === "Beauty") || null;
      for (const category of additions) {
        if (existing.some(a =>
          a.getAttribute("href") === category.href ||
          a.dataset.v4yShortcut === category.label.toLowerCase()
        )) continue;
        const link = template.cloneNode(true);
        link.href = category.href;
        link.setAttribute("aria-label", "Shop " + category.label);
        link.dataset.v4yShortcut = category.label.toLowerCase();
        link.querySelectorAll("[id]").forEach(el => el.removeAttribute("id"));
        const spans = link.querySelectorAll("span");
        if (spans[0]) {
          spans[0].classList.add("v4y-added-category-circle");
          spans[0].style.backgroundImage = "none";
          spans[0].style.backgroundColor = category.color;
          spans[0].textContent = category.icon;
        }
        const label = spans[1] || link.lastElementChild;
        if (label) label.textContent = category.label;
        if (before) rail.insertBefore(link, before);
        else rail.appendChild(link);
      }
    } finally {
      updating = false;
    }
  }
  let pending = false;
  function schedule() {
    if (pending) return;
    pending = true;
    queueMicrotask(() => {
      pending = false;
      updateShortcuts();
    });
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", schedule, { once: true });
  } else {
    schedule();
  }
  const observer = new MutationObserver(records => {
    if (records.some(r => Array.from(r.addedNodes).some(n =>
      n.nodeType === 1 && (
        n.matches?.('nav[aria-label="Browse departments"]') ||
        n.querySelector?.('nav[aria-label="Browse departments"]') ||
        n.matches?.('a[href*="/products?"]')
      )
    ))) schedule();
  });
  observer.observe(document.documentElement, { childList: true, subtree: true });
})();
