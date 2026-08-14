export const trackEvent = (eventName: string, eventParams?: Record<string, unknown>) => {
  if (import.meta.env.DEV) {
    console.debug(`[Analytics] ${eventName}`, eventParams ?? {});
  }
};
