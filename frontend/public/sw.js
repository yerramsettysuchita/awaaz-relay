/**
 * Awaaz Relay Service Worker — Offline-First
 * Caches: app shell, static assets, knowledge base
 * Strategy: Cache-first for assets, Network-first for KB, Skip for /analyze
 */

const CACHE_NAME = "awaaz-relay-v2";

const SHELL_URLS = ["/", "/index.html"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(SHELL_URLS).catch(() => {
        // Shell caching is best-effort — don't fail install
      });
    })
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((k) => k !== CACHE_NAME)
          .map((k) => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Never intercept POST /analyze — requires live server
  if (url.pathname === "/analyze" && request.method === "POST") {
    return;
  }

  // Knowledge base: network-first, cache as fallback
  if (url.pathname === "/knowledge-base") {
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
          }
          return response;
        })
        .catch(() => caches.match(request))
    );
    return;
  }

  // Health check — network only
  if (url.pathname === "/health") {
    return;
  }

  // Static assets (JS, CSS, fonts): stale-while-revalidate
  if (
    url.pathname.startsWith("/assets/") ||
    url.pathname.endsWith(".js") ||
    url.pathname.endsWith(".css") ||
    url.pathname.endsWith(".woff2") ||
    url.pathname.endsWith(".woff")
  ) {
    event.respondWith(
      caches.match(request).then((cached) => {
        const networkFetch = fetch(request).then((response) => {
          if (response.ok) {
            caches.open(CACHE_NAME).then((cache) => cache.put(request, response.clone()));
          }
          return response;
        });
        return cached || networkFetch;
      })
    );
    return;
  }

  // App shell (HTML navigation): cache-first
  if (request.mode === "navigate") {
    event.respondWith(
      caches.match("/index.html").then((cached) => cached || fetch(request))
    );
  }
});
