import { describe, expect, it } from 'vitest';
import { androidChromeIntentUrl, customerBrowserUrl, isAndroidInstagramInAppBrowser } from '../utils/inAppBrowser';

describe('Android Instagram browser safety', () => {
  it('detects Android Instagram without treating normal Android Chrome as embedded', () => {
    expect(isAndroidInstagramInAppBrowser('Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Instagram 400.0 Android')).toBe(true);
    expect(isAndroidInstagramInAppBrowser('Mozilla/5.0 (Linux; Android 14) Chrome/140.0 Mobile Safari/537.36')).toBe(false);
    expect(isAndroidInstagramInAppBrowser('Mozilla/5.0 (iPhone; CPU iPhone OS 18_6) Instagram 400.0')).toBe(false);
  });

  it('keeps browser handoff on the secure public origin and protected route', () => {
    const browserUrl = customerBrowserUrl('https://vibe4you.in', '/partner?step=application');
    expect(browserUrl).toBe('https://vibe4you.in/partner?step=application');
    expect(androidChromeIntentUrl(browserUrl)).toContain('intent://vibe4you.in/partner?step=application#Intent;scheme=https;package=com.android.chrome;');
  });

  it('rejects an insecure origin', () => {
    expect(() => customerBrowserUrl('http://vibe4you.in', '/partner')).toThrow('secure public origin');
  });

  it('rejects a backslash return path that URL parsing would otherwise turn into another origin', () => {
    expect(() => customerBrowserUrl('https://vibe4you.in', '/\\attacker.example/')).toThrow('remain on the public origin');
  });
});
