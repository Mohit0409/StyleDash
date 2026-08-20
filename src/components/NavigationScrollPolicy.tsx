import { useEffect, useLayoutEffect, useRef } from 'react';
import { useLocation, useNavigationType } from 'react-router-dom';

export const decodeNavigationFragment = (hash: string): string => {
  try {
    return decodeURIComponent(hash.slice(1));
  } catch {
    return '';
  }
};

const scrollToFragment = (hash: string): boolean => {
  const fragment = decodeNavigationFragment(hash);
  if (!fragment) return false;
  const target = document.getElementById(fragment) || document.getElementsByName(fragment)[0];
  if (!target) return false;
  target.scrollIntoView({ block: 'start' });
  return true;
};

/**
 * One route-level scroll policy for the persistent SPA layout.
 * Push/replace navigations open at the requested fragment or the page top.
 * Pop navigations are left to the browser's native history restoration.
 */
export const NavigationScrollPolicy: React.FC = () => {
  const location = useLocation();
  const navigationType = useNavigationType();
  const positions = useRef(new Map<string, { x: number; y: number }>());

  useEffect(() => {
    const previous = window.history.scrollRestoration;
    window.history.scrollRestoration = 'manual';
    return () => { window.history.scrollRestoration = previous; };
  }, []);

  useLayoutEffect(() => {
    const restore = navigationType === 'POP' ? positions.current.get(location.key) : undefined;
    let frame = 0;
    let timeout = 0;
    let observer: MutationObserver | null = null;

    const observeUntil = (attempt: () => boolean) => {
      if (attempt()) return;
      frame = window.requestAnimationFrame(attempt);
      observer = new MutationObserver(() => {
        if (attempt()) observer?.disconnect();
      });
      observer.observe(document.body, { childList: true, subtree: true });
      timeout = window.setTimeout(() => observer?.disconnect(), 5000);
    };

    if (restore) {
      observeUntil(() => {
        window.scrollTo(restore.x, restore.y);
        return Math.abs(window.scrollY - restore.y) <= 2;
      });
    } else if (navigationType === 'POP') {
      if (location.hash) observeUntil(() => scrollToFragment(location.hash));
    } else if (!location.hash || !decodeNavigationFragment(location.hash)) {
      window.scrollTo({ top: 0, left: 0, behavior: 'auto' });
    } else {
      observeUntil(() => scrollToFragment(location.hash));
    }

    return () => {
      positions.current.set(location.key, { x: window.scrollX, y: window.scrollY });
      if (positions.current.size > 100) positions.current.delete(positions.current.keys().next().value as string);
      window.cancelAnimationFrame(frame);
      window.clearTimeout(timeout);
      observer?.disconnect();
    };
  }, [location.hash, location.key, navigationType]);

  return null;
};
