import { CONFIG } from '../config';

export type AnalyticsConsent = 'accepted' | 'declined' | null;
type GoogleTag = (...args: unknown[]) => void;
type GoogleTagCommand = IArguments | unknown[];
type MetaPixel = ((...args: unknown[]) => void) & { callMethod?: (...args: unknown[]) => void; loaded: boolean; push: MetaPixel; queue: unknown[][]; version: string };

declare global { interface Window { dataLayer?: GoogleTagCommand[]; gtag?: GoogleTag; fbq?: MetaPixel; _fbq?: MetaPixel; } }

export const ANALYTICS_CONSENT_STORAGE_KEY = 'vibe4you_analytics_consent_v1';
export const ANALYTICS_PREFERENCES_EVENT = 'vibe4you:open-analytics-preferences';
const GOOGLE_SCRIPT_ID = 'vibe4you-google-analytics';
const META_SCRIPT_ID = 'vibe4you-meta-pixel';
const GOOGLE_ID_PATTERN = /^(?:G|GT)-[A-Z0-9]+$/i;
const META_ID_PATTERN = /^\d{5,30}$/;
const SENSITIVE_ROUTE_PATTERNS = [/^\/order-success\/[^/]+\/?$/i, /^\/orders\/[^/]+\/track\/?$/i, /^\/reset-password\/?$/i];
let googleInitialized = false;
let metaInitialized = false;
let lastTrackedPath = '';
const canUseBrowserApis = () => typeof window !== 'undefined' && typeof document !== 'undefined';

export const readAnalyticsConsent = (): AnalyticsConsent => {
  if (!canUseBrowserApis()) return null;
  try { const value = window.localStorage.getItem(ANALYTICS_CONSENT_STORAGE_KEY); return value === 'accepted' || value === 'declined' ? value : null; } catch { return null; }
};
const writeAnalyticsConsent = (consent: Exclude<AnalyticsConsent, null>) => { try { window.localStorage.setItem(ANALYTICS_CONSENT_STORAGE_KEY, consent); } catch { /* choice still applies for this page */ } };
const appendScript = (id: string, src: string) => { if (document.getElementById(id)) return; const script = document.createElement('script'); script.id = id; script.async = true; script.src = src; document.head.appendChild(script); };

const initializeGoogleAnalytics = () => {
  const measurementId = CONFIG.ANALYTICS.GOOGLE_MEASUREMENT_ID;
  if (!GOOGLE_ID_PATTERN.test(measurementId)) return;
  window.dataLayer = window.dataLayer || [];
  // gtag's Consent Mode parser requires the standard `arguments` object, not
  // a rest-parameter Array. The latter accepts config/event commands but
  // silently ignores consent commands, preventing GA4 collection.
  window.gtag = window.gtag || function gtag() {
    // eslint-disable-next-line prefer-rest-params -- Google requires the actual arguments object.
    window.dataLayer?.push(arguments);
  };
  if (googleInitialized) { window.gtag('consent', 'update', { analytics_storage: 'granted' }); return; }
  window.gtag('consent', 'default', { analytics_storage: 'denied', ad_storage: 'denied', ad_user_data: 'denied', ad_personalization: 'denied' });
  window.gtag('consent', 'update', { analytics_storage: 'granted', ad_storage: 'denied', ad_user_data: 'denied', ad_personalization: 'denied' });
  window.gtag('js', new Date());
  window.gtag('config', measurementId, { send_page_view: false });
  appendScript(GOOGLE_SCRIPT_ID, `https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(measurementId)}`);
  googleInitialized = true;
};
const initializeMetaPixel = () => {
  const pixelId = CONFIG.ANALYTICS.META_PIXEL_ID;
  if (!META_ID_PATTERN.test(pixelId)) return;
  if (metaInitialized) { window.fbq?.('consent', 'grant'); return; }
  if (!window.fbq) {
    const pixel = ((...args: unknown[]) => { if (pixel.callMethod) pixel.callMethod(...args); else pixel.queue.push(args); }) as MetaPixel;
    pixel.loaded = true; pixel.version = '2.0'; pixel.queue = []; pixel.push = pixel; window.fbq = pixel; window._fbq = pixel;
  }
  window.fbq('consent', 'grant'); window.fbq('init', pixelId);
  appendScript(META_SCRIPT_ID, 'https://connect.facebook.net/en_US/fbevents.js'); metaInitialized = true;
};
const expireCookie = (name: string) => {
  const expires = 'expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/; SameSite=Lax';
  document.cookie = `${name}=; ${expires}`; document.cookie = `${name}=; ${expires}; domain=${window.location.hostname}`; document.cookie = `${name}=; ${expires}; domain=.${window.location.hostname}`;
};
export const revokeAnalyticsConsent = () => {
  if (!canUseBrowserApis()) return;
  window.gtag?.('consent', 'update', { analytics_storage: 'denied', ad_storage: 'denied', ad_user_data: 'denied', ad_personalization: 'denied' });
  window.fbq?.('consent', 'revoke');
  document.cookie.split(';').map(cookie => cookie.trim().split('=', 1)[0]).filter(name => name === '_fbp' || name === '_fbc' || name === '_ga' || name.startsWith('_ga_')).forEach(expireCookie);
  lastTrackedPath = '';
};
export const setAnalyticsConsent = (consent: Exclude<AnalyticsConsent, null>) => { if (!canUseBrowserApis()) return; writeAnalyticsConsent(consent); if (consent === 'declined') revokeAnalyticsConsent(); };
export const safeAnalyticsPath = (pathname: string): string | null => {
  const normalizedPath = pathname.startsWith('/') ? pathname : '/';
  return SENSITIVE_ROUTE_PATTERNS.some(pattern => pattern.test(normalizedPath)) ? null : normalizedPath;
};
export const trackPageView = (pathname: string) => {
  if (!canUseBrowserApis() || readAnalyticsConsent() !== 'accepted') return;
  const safePath = safeAnalyticsPath(pathname); if (!safePath || safePath === lastTrackedPath) return;
  initializeGoogleAnalytics();
  window.gtag?.('event', 'page_view', { page_path: safePath, page_location: `${window.location.origin}${safePath}`, page_title: CONFIG.BRAND_NAME, page_referrer: '' });
  if (!window.location.search && !window.location.hash) { initializeMetaPixel(); window.fbq?.('track', 'PageView'); }
  lastTrackedPath = safePath;
};
export const trackEvent = (eventName: string, eventParams?: Record<string, unknown>) => {
  if (!canUseBrowserApis() || readAnalyticsConsent() !== 'accepted') return;
  const safePath = safeAnalyticsPath(window.location.pathname); if (!safePath) return;
  initializeGoogleAnalytics();
  window.gtag?.('event', eventName, { ...(eventParams || {}), page_location: `${window.location.origin}${safePath}`, page_title: CONFIG.BRAND_NAME, page_referrer: '' });
};
