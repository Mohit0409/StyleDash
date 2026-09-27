import React, { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  ANALYTICS_PREFERENCES_EVENT,
  AnalyticsConsent as AnalyticsConsentValue,
  readAnalyticsConsent,
  setAnalyticsConsent,
  trackPageView,
} from '../services/analytics';

export const AnalyticsRouteTracker: React.FC = () => {
  const location = useLocation();

  useEffect(() => {
    // Query strings and fragments may contain customer-provided sensitive values.
    trackPageView(location.pathname);
  }, [location.pathname]);

  return null;
};

export const AnalyticsConsent: React.FC = () => {
  const [consent, setConsent] = useState<AnalyticsConsentValue>(() => readAnalyticsConsent());
  const [editing, setEditing] = useState(false);

  useEffect(() => {
    const openPreferences = () => setEditing(true);
    window.addEventListener(ANALYTICS_PREFERENCES_EVENT, openPreferences);
    return () => window.removeEventListener(ANALYTICS_PREFERENCES_EVENT, openPreferences);
  }, []);

  const choose = (value: Exclude<AnalyticsConsentValue, null>) => {
    setAnalyticsConsent(value);
    if (value === 'accepted') trackPageView(window.location.pathname);
    setConsent(value);
    setEditing(false);
  };

  if (consent !== null && !editing) return null;

  return (
    <section
      aria-label="Analytics preferences"
      className="fixed inset-x-3 bottom-3 z-[120] mx-auto max-w-3xl rounded-2xl border border-neutral-700 bg-neutral-950 p-5 text-white shadow-2xl sm:inset-x-6"
      role="dialog"
    >
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="max-w-xl space-y-2">
          <h2 className="font-black">Your analytics choice</h2>
          <p className="text-xs leading-5 text-neutral-300">
            With your permission, Google Analytics measures site usage and Meta Pixel measures visits for advertising attribution. These providers may use cookies. Choosing only necessary keeps both trackers off. Read our{' '}
            <Link className="font-bold text-lime-400 underline" to="/privacy">privacy notice</Link>.
          </p>
          {consent !== null && (
            <p className="text-xs font-bold text-neutral-200">
              Current choice: {consent === 'accepted' ? 'analytics allowed' : 'only necessary'}.
            </p>
          )}
        </div>
        <div className="flex flex-wrap gap-2 sm:justify-end">
          {editing && (
            <button className="min-h-11 rounded-xl border border-neutral-600 px-4 py-2 text-xs font-bold" onClick={() => setEditing(false)} type="button">
              Close
            </button>
          )}
          <button className="min-h-11 rounded-xl border border-neutral-500 px-4 py-2 text-xs font-bold" onClick={() => choose('declined')} type="button">
            Only necessary
          </button>
          <button className="min-h-11 rounded-xl bg-lime-400 px-4 py-2 text-xs font-black text-neutral-950" onClick={() => choose('accepted')} type="button">
            Allow analytics
          </button>
        </div>
      </div>
    </section>
  );
};
