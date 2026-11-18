/* Vibe4You floating WhatsApp and Instagram buttons - 2026-10-24.
   Presentation only. No changes to product data, cart, checkout or payments. */
(() => {
  "use strict";
  if (window.__v4ySocial20261024) return;
  window.__v4ySocial20261024 = true;

  const WHATSAPP_NUMBER = "918085810758";
  const WHATSAPP_TEXT = "Hi Vibe4You, I need help with ";
  const INSTAGRAM_URL = "https://www.instagram.com/vibe44you/";
  const WHATSAPP_URL = "https://wa.me/" + WHATSAPP_NUMBER + "?text=" + encodeURIComponent(WHATSAPP_TEXT);
  // Pages where a floating button could get in the way of paying or of staff tools.
  const HIDDEN_PREFIXES = ["/checkout", "/admin", "/vendor"];

  const style = document.createElement("style");
  style.id = "v4y-social-20261024-style";
  style.textContent = [
    ".v4y-social{position:fixed;left:12px;bottom:calc(20px + env(safe-area-inset-bottom));z-index:45;display:flex;flex-direction:column;gap:10px;margin:0;padding:0}",
    ".v4y-social[hidden]{display:none!important}",
    ".v4y-social a{display:flex;align-items:center;justify-content:center;width:48px;height:48px;border-radius:9999px;color:#fff;box-shadow:0 4px 14px rgba(0,0,0,.28);text-decoration:none;transition:transform .15s ease,box-shadow .15s ease;-webkit-tap-highlight-color:transparent}",
    ".v4y-social a:hover,.v4y-social a:focus-visible{transform:scale(1.08);box-shadow:0 6px 18px rgba(0,0,0,.34)}",
    ".v4y-social a:focus-visible{outline:3px solid #a3e635;outline-offset:2px}",
    ".v4y-social svg{width:26px;height:26px;fill:currentColor;display:block}",
    ".v4y-social .v4y-wa{background:#25d366}",
    ".v4y-social .v4y-ig{background:radial-gradient(circle at 30% 107%,#fdf497 0,#fdf497 5%,#fd5949 45%,#d6249f 60%,#285aeb 90%)}",
    "@media (prefers-reduced-motion:reduce){.v4y-social a{transition:none}}",
    "@media print{.v4y-social{display:none!important}}",
    'body:has([data-testid="mobile-filter-backdrop"]) .v4y-social{display:none!important}'
  ].join("\n");
  document.head.appendChild(style);

  const WA_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M12.04 2C6.58 2 2.13 6.45 2.13 11.91c0 1.75.46 3.45 1.32 4.95L2.05 22l5.25-1.38a9.9 9.9 0 0 0 4.74 1.21c5.46 0 9.91-4.45 9.91-9.91S17.5 2 12.04 2zm0 18.15c-1.48 0-2.93-.4-4.2-1.15l-.3-.18-3.12.82.83-3.04-.2-.31a8.2 8.2 0 0 1-1.26-4.38c0-4.54 3.7-8.24 8.25-8.24 4.54 0 8.24 3.7 8.24 8.24s-3.7 8.24-8.24 8.24zm4.52-6.17c-.25-.12-1.47-.72-1.69-.81-.23-.08-.39-.12-.56.12-.17.25-.64.81-.78.97-.14.17-.29.19-.54.06-.25-.12-1.05-.39-1.99-1.23-.74-.66-1.23-1.47-1.38-1.72-.14-.25-.02-.38.11-.51.11-.11.25-.29.37-.43.12-.14.17-.25.25-.41.08-.17.04-.31-.02-.43-.06-.12-.56-1.34-.76-1.84-.2-.48-.4-.42-.56-.43h-.48c-.17 0-.43.06-.66.31-.22.25-.86.85-.86 2.07s.89 2.4 1.01 2.56c.12.17 1.75 2.67 4.23 3.74.59.26 1.05.41 1.41.52.59.19 1.13.16 1.56.1.48-.07 1.47-.6 1.67-1.18.21-.58.21-1.07.14-1.18-.06-.1-.23-.17-.48-.29z"/></svg>';
  const IG_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M7.8 2h8.4A5.8 5.8 0 0 1 22 7.8v8.4a5.8 5.8 0 0 1-5.8 5.8H7.8A5.8 5.8 0 0 1 2 16.2V7.8A5.8 5.8 0 0 1 7.8 2zm-.2 2A3.6 3.6 0 0 0 4 7.6v8.8A3.6 3.6 0 0 0 7.6 20h8.8a3.6 3.6 0 0 0 3.6-3.6V7.6A3.6 3.6 0 0 0 16.4 4H7.6zm9.65 1.5a1.25 1.25 0 1 1 0 2.5 1.25 1.25 0 0 1 0-2.5zM12 7a5 5 0 1 1 0 10 5 5 0 0 1 0-10zm0 2a3 3 0 1 0 0 6 3 3 0 0 0 0-6z"/></svg>';

  function link(cls, href, label, icon) {
    const a = document.createElement("a");
    a.className = cls;
    a.href = href;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    a.setAttribute("aria-label", label);
    a.title = label;
    a.innerHTML = icon;
    return a;
  }

  let box = null;
  function build() {
    if (box || !document.body) return;
    box = document.createElement("div");
    box.className = "v4y-social";
    box.setAttribute("data-v4y-social", "1");
    box.hidden = true;
    box.appendChild(link("v4y-wa", WHATSAPP_URL, "Chat with Vibe4You on WhatsApp", WA_ICON));
    box.appendChild(link("v4y-ig", INSTAGRAM_URL, "Vibe4You on Instagram", IG_ICON));
    document.body.appendChild(box);
  }

  function update() {
    build();
    if (!box) return;
    const path = location.pathname || "/";
    const hide = HIDDEN_PREFIXES.some(p => path === p || path.indexOf(p + "/") === 0);
    box.hidden = hide;
    if (hide) return;
    // Sit above the mobile bottom navigation when it is on screen.
    const nav = document.querySelector("[data-mobile-bottom-nav]");
    let lift = 0;
    if (nav) {
      const r = nav.getBoundingClientRect();
      if (r.height > 0 && r.top < window.innerHeight) lift = Math.max(0, window.innerHeight - r.top);
    }
    const bottom = lift > 0 ? "calc(" + Math.round(lift + 12) + "px)" : "calc(20px + env(safe-area-inset-bottom))";
    if (box.style.bottom !== bottom) box.style.bottom = bottom;
  }

  function start() {
    update();
    setInterval(update, 700);
    window.addEventListener("popstate", update);
    window.addEventListener("resize", update);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
