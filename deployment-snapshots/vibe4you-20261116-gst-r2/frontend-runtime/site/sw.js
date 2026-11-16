/* Vibe4You: static offline page only. Customer data and commerce stay network-only. */
const CACHE_NAME = 'vibe4you-live-pwa-v2';
const STATIC_ASSETS = ['/vibe4you-app/offline.html', '/vibe4you-app/icons/icon-192.png', '/vibe4you-app/icons/icon-512.png', '/vibe4you-app/icons/icon-maskable-512.png', '/vibe4you-app/icons/apple-touch-icon.png'];

self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE_NAME);
    for (const path of STATIC_ASSETS) {
      const request = new Request(new URL(path, self.location.origin), { credentials: 'omit', cache: 'reload' });
      const response = await fetch(request);
      if (!response.ok || response.type !== 'basic' || response.redirected) {
        throw new Error('Offline asset could not be safely cached.');
      }
      await cache.put(path, response);
    }
  })());
  // Do not skip waiting: never reload or interrupt an active checkout.
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const names = await caches.keys();
    await Promise.all(names.filter((name) => name.startsWith('vibe4you-live-pwa-') && name !== CACHE_NAME).map((name) => caches.delete(name)));
  })());
});

self.addEventListener('fetch', (event) => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== 'GET' || url.origin !== self.location.origin || request.mode !== 'navigate') return;
  if (/^\/(?:api|admin)(?:\/|$)/i.test(url.pathname)) return;
  event.respondWith((async () => {
    try {
      return await fetch(request);
    } catch {
      const cache = await caches.open(CACHE_NAME);
      const offline = await cache.match('/vibe4you-app/offline.html');
      return offline || new Response('You are offline. Reconnect to browse Vibe4You and manage your orders.', {
        status: 503,
        headers: { 'Content-Type': 'text/plain; charset=utf-8', 'Cache-Control': 'no-store' },
      });
    }
  })());
});
