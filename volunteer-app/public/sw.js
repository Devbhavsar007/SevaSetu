// SevaSetu Service Worker — Offline-first caching (Task 2.4)
const CACHE_NAME = 'sevasetu-v1';
const STATIC_ASSETS = [
  '/',
  '/LOGO.png',
  '/manifest.json',
];

// Install — cache static assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS);
    })
  );
  self.skipWaiting();
});

// Activate — clean old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
      );
    })
  );
  self.clients.claim();
});

// Fetch — network-first with cache fallback
self.addEventListener('fetch', (event) => {
  // Skip non-GET and API requests
  if (event.request.method !== 'GET') return;
  if (event.request.url.includes('/api/')) return;
  if (event.request.url.includes('/ws/')) return;

  event.respondWith(
    fetch(event.request)
      .then((response) => {
        // Clone and cache successful responses
        if (response.status === 200) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, clone);
          });
        }
        return response;
      })
      .catch(() => {
        // Offline — serve from cache
        return caches.match(event.request).then((cached) => {
          return cached || caches.match('/');
        });
      })
  );
});

// Background sync for offline-queued reports
self.addEventListener('sync', (event) => {
  if (event.tag === 'sync-needs') {
    event.waitUntil(syncQueuedNeeds());
  }
});

async function syncQueuedNeeds() {
  try {
    const db = await openIDB();
    const queue = await db.getAll('offline-queue');
    for (const item of queue) {
      try {
        await fetch(item.url, item.options);
        await db.delete('offline-queue', item.id);
      } catch (e) {
        // Will retry on next sync
      }
    }
  } catch (e) {
    console.error('Sync failed:', e);
  }
}
