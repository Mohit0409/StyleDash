const ANDROID_INSTAGRAM = /\bInstagram\b/i;
const ANDROID = /\bAndroid\b/i;

/**
 * Instagram's Android WebView can refuse to retain a secure HttpOnly customer
 * session.  Do not attempt a weaker, JavaScript-visible authentication fallback:
 * send the customer to the device browser instead.
 */
export const isAndroidInstagramInAppBrowser = (userAgent: string): boolean =>
  ANDROID.test(userAgent) && ANDROID_INSTAGRAM.test(userAgent);

export const customerBrowserUrl = (origin: string, returnPath: string): string => {
  const publicOrigin = new URL(origin);
  if (publicOrigin.protocol !== 'https:') throw new Error('A secure public origin is required.');
  const safePath = returnPath.startsWith('/') ? returnPath : '/';
  const destination = new URL(safePath, publicOrigin);
  if (destination.origin !== publicOrigin.origin) throw new Error('The return path must remain on the public origin.');
  return destination.toString();
};

/**
 * Android intent links ask the operating system to leave the embedded WebView
 * and open the canonical URL in Chrome. The HTTPS fallback still gives users a
 * usable link on devices where Chrome is unavailable.
 */
export const androidChromeIntentUrl = (browserUrl: string): string => {
  const target = new URL(browserUrl);
  if (target.protocol !== 'https:') throw new Error('A secure browser URL is required.');
  const targetPath = `${target.host}${target.pathname}${target.search}${target.hash}`;
  return `intent://${targetPath}#Intent;scheme=https;package=com.android.chrome;S.browser_fallback_url=${encodeURIComponent(target.toString())};end`;
};
