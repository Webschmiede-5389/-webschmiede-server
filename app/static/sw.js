/* Minimaler Service Worker: macht die Startseite installierbar.
   start_url bleibt /. Bestellportal wird nicht als App-Einstieg genutzt. */
const CACHE = "shy-shell-v5";
const PRECACHE = ["/manifest.webmanifest", "/favicon-192.png", "/apple-touch-icon.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(PRECACHE)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  // API und Bestellportal nicht aus dem Cache bedienen
  if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/bestellen")) return;

  event.respondWith(
    fetch(req)
      .then((res) => {
        const copy = res.clone();
        if (res.ok && (url.pathname.endsWith(".png") || url.pathname.endsWith(".webmanifest"))) {
          caches.open(CACHE).then((cache) => cache.put(req, copy)).catch(() => {});
        }
        return res;
      })
      .catch(() => caches.match(req).then((hit) => hit || caches.match("/")))
  );
});
