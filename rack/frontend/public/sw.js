/* Service Worker: haelt die Huelle der App offline verfuegbar.

   Bewusst schlank. Die Programmhuelle wird vorgehalten, Bilder werden
   nachtraeglich gecacht, API-Antworten nie. Ein veralteter Vorschlag
   waere schlimmer als gar keiner. */

const SHELL = "rack-shell-v1";
const IMAGES = "rack-images-v1";
const SHELL_FILES = [
  "/",
  "/manifest.webmanifest",
  "/apple-touch-icon.png",
  "/icon-192.png",
  "/icon-512.png",
  "/favicon-32.png",
  "/fonts/fonts.css",
];

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(SHELL).then((c) => c.addAll(SHELL_FILES)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((k) => k !== SHELL && k !== IMAGES).map((k) => caches.delete(k)))
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const { request } = e;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  /* Bilder aendern sich unter derselben ID nie: erst Cache, dann Netz. */
  if (url.pathname.startsWith("/api/images/")) {
    e.respondWith(
      caches.open(IMAGES).then(async (cache) => {
        const hit = await cache.match(request);
        if (hit) return hit;
        const res = await fetch(request);
        if (res.ok) cache.put(request, res.clone());
        return res;
      })
    );
    return;
  }

  /* Alles andere unter /api bleibt ungecacht. */
  if (url.pathname.startsWith("/api/")) return;

  /* Navigation: Netz zuerst, bei Ausfall die gecachte Huelle. */
  if (request.mode === "navigate") {
    e.respondWith(fetch(request).catch(() => caches.match("/")));
    return;
  }

  e.respondWith(
    caches.match(request).then(
      (hit) =>
        hit ||
        fetch(request).then((res) => {
          if (res.ok && (url.pathname.startsWith("/assets/") || url.pathname.startsWith("/fonts/"))) {
            caches.open(SHELL).then((c) => c.put(request, res.clone()));
          }
          return res;
        })
    )
  );
});
