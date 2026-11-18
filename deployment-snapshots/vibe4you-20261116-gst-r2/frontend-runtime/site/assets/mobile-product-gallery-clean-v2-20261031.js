(() => {
  const HERO_SELECTOR = 'button[aria-label^="Open full screen image of"]';
  const LEGACY_CONTROLS_ID = 'v4y-mobile-product-gallery-controls';
  let framePending = false;

  const galleryParts = () => {
    const hero = document.querySelector(HERO_SELECTOR);
    if (!(hero instanceof HTMLButtonElement)) return null;
    const gallery = hero.parentElement;
    if (!gallery) return null;
    const rail = Array.from(gallery.children).find((child) => (
      child !== hero
      && child instanceof HTMLElement
      && child.querySelectorAll('button img').length > 0
    ));
    return rail instanceof HTMLElement ? { hero, rail } : null;
  };

  const syncGallery = () => {
    framePending = false;
    document.getElementById(LEGACY_CONTROLS_ID)?.remove();
    const parts = galleryParts();
    if (!parts) return;

    const mobile = window.matchMedia('(max-width: 639px)').matches;
    parts.hero.style.aspectRatio = mobile ? '1 / 1' : '';
    parts.rail.style.display = mobile ? 'none' : '';
  };

  const scheduleSync = () => {
    if (framePending) return;
    framePending = true;
    window.requestAnimationFrame(syncGallery);
  };

  new MutationObserver(scheduleSync).observe(document.documentElement, {
    childList: true,
    subtree: true,
  });
  window.addEventListener('resize', scheduleSync, { passive: true });
  window.addEventListener('popstate', scheduleSync);
  scheduleSync();
})();
