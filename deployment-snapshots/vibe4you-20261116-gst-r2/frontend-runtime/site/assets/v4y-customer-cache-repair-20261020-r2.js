/* Vibe4You customer delivery address release: one-time stale JS cache repair.
 * Runs only after detecting a legacy profile or product page. Does not send
 * customer data, change app state, or initiate payment/order operations.
 */
(() => {
  "use strict";
  const release = "v4y-customer-panindia-20261020-r2";
  const assets = [
    "/assets/index-MMTPd8z_-v4y044-pr150-review-r5.js",
    "/assets/Profile-B5Zhrhx3-v4y044-pr150-review-r5.js",
    "/assets/ProductDetail-CvQ_LhJ--v4y044-pr150-review-r5.js",
    "/assets/Checkout-DmmfmeKk-v4y044-pr150-review-r5.js"
  ];
  let working = false;
  let pending = false;
  let observer;

  function oldScreenVisible() {
    const path = location.pathname;
    if (path === "/profile") {
      return document.body?.textContent?.includes("Current delivery area: Neemuch (458441).") === true;
    }
    if (path.startsWith("/product/")) {
      return document.body?.textContent?.includes("For addresses outside 458441, do not pay at normal checkout.") === true;
    }
    return false;
  }

  async function refreshLegacyCache() {
    if (working || !oldScreenVisible()) return;
    try {
      if (sessionStorage.getItem(release) === "done") return;
    } catch { /* Storage not available: proceed once per page */ }
    working = true;
    observer?.disconnect();
    try {
      const responses = await Promise.all(assets.map(async (path) => {
        const response = await fetch(path, { cache: "reload", credentials: "same-origin" });
        if (!response.ok) throw new Error("Frontend asset refresh failed");
        return response.text();
      }));
      if (!responses[1].includes("Customers across India can save") ||
          !responses[2].includes("We will get back to you within 1 hour") ||
          !responses[3].includes("Direct checkout is available only for Neemuch")) {
        throw new Error("Updated website assets have not reached the client yet");
      }
      try { sessionStorage.setItem(release, "done"); } catch { /* noncritical */ }
      location.reload();
    } catch (err) {
      console.warn("Vibe4You frontend refresh needs a hard reload:", err);
      working = false;
    }
  }

  function scheduleCheck() {
    if (pending || working) return;
    pending = true;
    setTimeout(() => {
      pending = false;
      void refreshLegacyCache();
    }, 220);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", scheduleCheck, { once: true });
  } else {
    scheduleCheck();
  }
  observer = new MutationObserver(scheduleCheck);
  observer.observe(document.documentElement, { subtree: true, childList: true });
  addEventListener("popstate", scheduleCheck);
})();
