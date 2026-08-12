import { analytics } from './config';
import { logEvent } from 'firebase/analytics';

export const trackEvent = (eventName: string, eventParams?: Record<string, any>) => {
  if (analytics) {
    try {
      logEvent(analytics, eventName, eventParams);
    } catch (e) {
      console.warn('Analytics event tracking error:', e);
    }
  } else {
    // In demo/local mode, log to console in dev
    if (import.meta.env.DEV) {
      console.log('[Analytics Demo] ' + eventName + ':', eventParams);
    }
  }
};
