const CACHE_NAME = 'futures-grano-v2.5';
const ASSETS_TO_CACHE = [
  './',
  './index.html',
  './css/style.css?v=2.5',
  './js/app.js?v=2.5',
  './manifest.json',
  './favicon.ico',
  './favicon.png',
  './icon-180.png',
  './icon-192.png',
  './icon-512.png',
  './icon-maskable-512.png',
  './logo_optimized.webp',
  'https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js',
  'https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@500;600;700;800&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Space+Grotesk:wght@600;700;800&display=swap'
];

self.addEventListener('install', (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(ASSETS_TO_CACHE).catch((err) => console.warn('PWA Cache install warning:', err));
    })
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cache) => {
          if (cache !== CACHE_NAME) {
            console.log('Eliminazione vecchia cache PWA:', cache);
            return caches.delete(cache);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

// Strategia differenziata: Dati SEMPRE live da rete (zero cache), Asset statici Network First
self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET' || !event.request.url.startsWith('http')) {
    return;
  }

  const url = event.request.url;

  // I dati dinamici (JSON, CSV, chiamate API) NON devono MAI essere bloccati da cache SW
  if (url.includes('storico_prezzi') || url.includes('/api/') || url.includes('raw.githubusercontent.com') || url.includes('api.github.com')) {
    event.respondWith(
      fetch(event.request, { cache: 'no-store' })
        .catch(() => caches.match(event.request))
    );
    return;
  }

  // Risorse statiche: Network First con fallback cache per funzionamento offline
  event.respondWith(
    fetch(event.request)
      .then((networkResponse) => {
        if (networkResponse && networkResponse.status === 200) {
          const respClone = networkResponse.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, respClone));
        }
        return networkResponse;
      })
      .catch(() => caches.match(event.request))
  );
});
