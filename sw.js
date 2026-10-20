const CACHE_NAME = "pushkinskaya-v3";
const APP_SHELL = [
  "/app",
  "/app/static/leaflet/leaflet.js",
  "/app/static/leaflet/leaflet.css",
  "/app/static/favicon.svg",
  "/app/manifest.json",
];
const LANDMARKS_CACHE = "pushkinskaya-data-v1";

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) =>
      Promise.all(
        APP_SHELL.map((url) =>
          cache.add(url).catch((err) => {
            // One missing asset must not abort the whole service worker
            // install — cache the rest and try this URL again at runtime.
            console.warn("Precache failed:", url, err);
          })
        )
      )
    )
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((k) => k !== CACHE_NAME && k !== LANDMARKS_CACHE)
          .map((k) => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

function fetchWithTimeout(request, ms) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("timeout")), ms);
    fetch(request).then(
      (response) => { clearTimeout(timer); resolve(response); },
      (err) => { clearTimeout(timer); reject(err); }
    );
  });
}

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // Only handle same-origin requests
  if (url.origin !== self.location.origin) return;

  // App shell — network first, cache fallback. Serving the shell
  // cache-first would pin users to the old HTML after a deploy. The
  // 3 s timeout keeps weak connections from waiting on a dead request
  // before the cached copy is shown.
  if (url.pathname === "/app" || url.pathname === "/app/") {
    event.respondWith(
      fetchWithTimeout(event.request, 3000).then((response) => {
        if (response.ok) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((c) => c.put(event.request, clone));
        }
        return response;
      }).catch(() =>
        caches.match(event.request).then((cached) => cached || Response.error())
      )
    );
    return;
  }

  // Landmarks API — cache first, network fallback, persist to data cache
  if (url.pathname === "/landmarks") {
    event.respondWith(
      caches.open(LANDMARKS_CACHE).then((cache) =>
        cache.match(event.request).then((cached) => {
          const fetched = fetch(event.request).then((response) => {
            if (response.ok) {
              cache.put(event.request, response.clone());
            }
            return response;
          }).catch(() => cached);
          return cached || fetched;
        })
      )
    );
    return;
  }

  // Photos — cache first (aggressive, these don't change)
  if (url.pathname.startsWith("/photo/")) {
    event.respondWith(
      caches.open(LANDMARKS_CACHE).then((cache) =>
        cache.match(event.request).then((cached) => {
          if (cached) return cached;
          return fetch(event.request).then((response) => {
            if (response.ok) {
              cache.put(event.request, response.clone());
            }
            return response;
          });
        })
      )
    );
    return;
  }

  // Photos available list — cache first
  if (url.pathname === "/photos/available") {
    event.respondWith(
      caches.open(LANDMARKS_CACHE).then((cache) =>
        cache.match(event.request).then((cached) => {
          const fetched = fetch(event.request).then((response) => {
            if (response.ok) {
              cache.put(event.request, response.clone());
            }
            return response;
          }).catch(() => cached);
          return cached || fetched;
        })
      )
    );
    return;
  }

  // Everything else — network first, cache fallback
  event.respondWith(
    fetch(event.request).catch(() => caches.match(event.request))
  );
});
