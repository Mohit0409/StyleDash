/* Vibe4You Google Ads base destination; does not create conversion events.
   Reuses the existing consent-gated GA4 gtag.js installation. */
(function () {
  'use strict';
  var KEY = '__v4yGoogleAdsBase20261026';
  var DESTINATION = 'AW-18534915701';
  var CONSENT_KEY = 'vibe4you_analytics_consent_v1';
  if (window[KEY]) return;
  window[KEY] = true;

  var configured = false;
  var pollCount = 0;
  var pollTimer;
  function consented() {
    try {
      return window.localStorage.getItem(CONSENT_KEY) === 'accepted';
    } catch (_) {
      return false;
    }
  }
  function configure() {
    if (configured || !consented()) return;
    // The application's analytics module must initialize consent mode first.
    if (!document.getElementById('vibe4you-google-analytics') || typeof window.gtag !== 'function') return;
    // Do not grant ad_storage, ad_user_data, or ad_personalization here.
    // The existing consent handler controls those settings.
    window.gtag('config', DESTINATION);
    configured = true;
    if (pollTimer !== undefined) window.clearInterval(pollTimer);
  }
  pollTimer = window.setInterval(function () {
    configure();
    if (++pollCount >= 200) window.clearInterval(pollTimer);
  }, 300);
  configure();

  // React initializes its Google tag inside the consent button's click event.
  // Check after that handler has run without intercepting or modifying it.
  document.addEventListener('click', function () {
    window.setTimeout(configure, 0);
  }, true);
  window.addEventListener('storage', configure);
  window.addEventListener('pageshow', configure);
})();
