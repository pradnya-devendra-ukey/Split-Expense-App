const CACHE_NAME = 'split-expense-v1';

self.addEventListener('install', (e) => {
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(clients.claim());
});

self.addEventListener('fetch', (e) => {
  // Let network handle dynamic API requests
  e.respondWith(fetch(e.request).catch(() => caches.match(e.request)));
});
