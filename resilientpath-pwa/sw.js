/**
 * ============================================================================
 * DisasterLens AI — Service Worker (sw.js)
 * NDMA Flood Reporting PWA | Phase 1: Offline-First Caching
 * ============================================================================
 *
 * PURPOSE:
 * Provides offline-first capability for field agents operating in flood zones
 * with unreliable 2G/3G connectivity. Caches the app shell (HTML, CSS, JS,
 * map tiles, fonts) so the PWA loads instantly even with zero connectivity.
 *
 * ARCHITECTURE NOTES:
 * - Phase 2 (NLP Backend): This SW will also handle background sync for
 *   queued reports, POSTing them to the FastAPI endpoint when online.
 * - Phase 3 (NEOC Dashboard): Cache strategies may be extended to support
 *   dashboard tiles and real-time WebSocket reconnection logic.
 * ============================================================================
 */

const CACHE_NAME = 'disasterlens-v2';

// Core app shell assets to pre-cache on install
// These are the minimum resources needed for the app to function offline
const APP_SHELL_ASSETS = [
  '/',
  '/index.html',
  '/style.css',
  '/app.js',
  '/manifest.json',
  '/icons/icon-192.png',
  '/icons/icon-512.png',
  // Leaflet CSS & JS (pinned versions for reliability)
  'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',
  'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js',
  // Leaflet default marker icons (required for offline marker rendering)
  'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
  // Google Fonts for bilingual support (Inter + Noto Nastaliq Urdu)
  'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Noto+Nastaliq+Urdu:wght@400;600;700&display=swap'
];

/**
 * INSTALL EVENT
 * Pre-caches all app shell assets. Uses skipWaiting() to activate immediately
 * so field agents don't need to close/reopen the app to get updates.
 */
self.addEventListener('install', (event) => {
  console.log('[SW] Installing DisasterLens Service Worker v1...');
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        console.log('[SW] Pre-caching app shell assets');
        return cache.addAll(APP_SHELL_ASSETS);
      })
      .then(() => {
        console.log('[SW] App shell cached successfully');
        return self.skipWaiting();
      })
      .catch((err) => {
        console.error('[SW] Failed to cache app shell:', err);
      })
  );
});

/**
 * ACTIVATE EVENT
 * Cleans up old caches from previous versions. Claims all clients immediately
 * so the new SW takes control without requiring a page reload.
 */
self.addEventListener('activate', (event) => {
  console.log('[SW] Activating DisasterLens Service Worker v1...');
  event.waitUntil(
    caches.keys()
      .then((cacheNames) => {
        return Promise.all(
          cacheNames
            .filter((name) => name !== CACHE_NAME)
            .map((name) => {
              console.log('[SW] Purging old cache:', name);
              return caches.delete(name);
            })
        );
      })
      .then(() => {
        console.log('[SW] Claiming all clients');
        return self.clients.claim();
      })
  );
});

/**
 * FETCH EVENT
 * Strategy:
 * - App shell (HTML, CSS, JS, icons): Cache-first, fallback to network
 * - OSM map tiles: Network-first with cache fallback (tiles update frequently)
 * - API calls (/api/*): Network-only (handled by IndexedDB queue in app.js)
 * - Google Fonts: Cache-first (fonts rarely change)
 * - Everything else: Network-first with cache fallback
 */
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Skip non-GET requests (POST reports are handled by IndexedDB in app.js)
  if (event.request.method !== 'GET') return;

  // Skip API calls — these are managed by the IndexedDB sync queue
  if (url.pathname.startsWith('/api/')) return;

  // OSM tile requests — network-first to get fresh tiles, cache fallback
  if (url.hostname.includes('tile.openstreetmap.org')) {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
          return response;
        })
        .catch(() => caches.match(event.request))
    );
    return;
  }

  // Default: Cache-first for app shell and static assets
  event.respondWith(
    caches.match(event.request)
      .then((cachedResponse) => {
        if (cachedResponse) {
          return cachedResponse;
        }
        // Not in cache — fetch from network and cache for next time
        return fetch(event.request)
          .then((networkResponse) => {
            // Only cache successful responses
            if (networkResponse && networkResponse.status === 200) {
              const clone = networkResponse.clone();
              caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
            }
            return networkResponse;
          });
      })
      .catch(() => {
        // Ultimate fallback for navigation requests — serve cached index.html
        if (event.request.mode === 'navigate') {
          return caches.match('/index.html');
        }
      })
  );
});

/**
 * BACKGROUND SYNC EVENT (Phase 2 Integration Point)
 * ============================================================================
 * When the browser regains connectivity, this event fires for any registered
 * sync tags. In Phase 2, the FastAPI backend will accept POSTed reports, and
 * this handler will read from IndexedDB and flush the queue.
 *
 * Registration happens in app.js:
 *   navigator.serviceWorker.ready.then(reg => reg.sync.register('sync-reports'));
 * ============================================================================
 */
self.addEventListener('sync', (event) => {
  if (event.tag === 'sync-reports') {
    console.log('[SW] Background sync triggered for pending reports');
    // Phase 2: event.waitUntil(flushPendingReports());
    // For now, the sync is handled by the online event listener in app.js
  }
});
